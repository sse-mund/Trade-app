
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pydantic import BaseModel
from typing import List, Optional, Dict
import uvicorn
import pandas as pd
import json
import logging
import time
from datetime import datetime

# Import backend modules
from database import StockDatabase
from chart_generator import ChartGenerator
from data_collector import DataCollector
from cache_manager import CacheManager
from data.ingestion.finnhub_connector import FinnhubConnector
from data.ingestion.reddit_connector import RedditConnector
from data.ingestion.twitter_scraper import TwitterConnector
from data.ingestion.newsapi_connector import NewsAPIConnector

# Import NEW Agent Modules
from agents.analyst_orchestrator import AnalystOrchestrator
from fundamentals_collector import FundamentalsCollector

# Import Backtesting Modules
from backtesting.backtester import Backtester
from backtesting.metrics import compute_metrics
from backtesting.optimizer import Optimizer
from backtesting.walk_forward_optimizer import WalkForwardOptimizer
from config import OPTIMIZER_TICKERS
from market_hours import is_data_fresh
import yfinance as yf

from logger_config import setup_logging

# Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)
logger = setup_logging()

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
db = StockDatabase()
chart_gen = ChartGenerator()
data_collector = DataCollector()
cache = CacheManager(ttl_seconds=300) # 5-minute cache

# Initialize Agents
orchestrator = AnalystOrchestrator()
fundamentals_collector = FundamentalsCollector()

import os

# Initialize Connectors (loads from env vars)
finnhub_key = os.getenv('FINNHUB_API_KEY')
if finnhub_key:
    logger.info(f"Main: Found Finnhub Key: {finnhub_key[:4]}...{finnhub_key[-4:]}")
else:
    logger.error("Main: Finnhub Key NOT found in env")

finnhub = FinnhubConnector(api_key=finnhub_key)
reddit = RedditConnector()
newsapi = NewsAPIConnector()  # Initializes from NEWSAPI_KEY env var
twitter_enabled = os.getenv('TWITTER_ENABLED', 'true').lower() == 'true'
twitter = TwitterConnector(enabled=twitter_enabled)  # Initializes from TWITTER_BEARER_TOKEN env var

class StrategyRequest(BaseModel):
    ticker: str
    selected_strategies: List[str]

class AnalyzeRequest(BaseModel):
    ticker: str
    period_days: int = 365
    interval: str = None   # None = daily; '5m' | '15m' | '1h' = intraday
    quant_weights: dict = None  # Optional: {"momentum": 0.30, "ichimoku": 0.25, "volume": 0.25, "volatility": 0.20}

class BacktestRequest(BaseModel):
    ticker: str = "NVDA"

class OptimizeRequest(BaseModel):
    ticker: str = "NVDA"

class WalkForwardRequest(BaseModel):
    tickers: List[str] = OPTIMIZER_TICKERS
    train_ratio: float = 0.6


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"Request: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.4f}s")
    return response

def _inject_live_price(df: pd.DataFrame, live_price: float) -> pd.DataFrame:
    """
    Append a synthetic 'now' row to the dataframe if the last bar is not from today.
    This ensures technical indicators factor in the current live price.
    """
    if df.empty or live_price is None:
        return df
        
    last_date = df.index.max()
    now = pd.Timestamp.now(tz=last_date.tz) if last_date.tz else pd.Timestamp.now()
    
    # If the last bar is from a previous day, append a partial 'today' bar
    if last_date.date() < now.date():
        new_row = pd.DataFrame({
            'Open': [live_price],
            'High': [live_price],
            'Low': [live_price],
            'Close': [live_price],
            'Volume': [0] # Volume unknown
        }, index=[now])
        df = pd.concat([df, new_row])
        logger.info(f"Injected live price ${live_price} as synthetic bar for {now.date()}")
    else:
        # If we already have a bar for today, update its Close to the live price
        df.iloc[-1, df.columns.get_loc('Close')] = live_price
        logger.info(f"Updated today's bar Close to live price ${live_price}")
        
    return df

@app.get("/")
def read_root():
    return {"message": "Trade Strategy App API is running"}

@app.get("/optimizer_tickers")
def get_optimizer_tickers():
    """Return the default ticker universe for walk-forward optimization."""
    return {"tickers": OPTIMIZER_TICKERS}

@app.get("/top_stocks")
def get_top_stocks():
    """Return the full TOP_50 stock universe from config."""
    from config import TOP_50_STOCKS
    return {"tickers": TOP_50_STOCKS}

@app.get("/tickers")
def get_tickers():
    """Get list of available tickers."""
    tickers = db.get_all_tickers()
    return {"tickers": [t[0] for t in tickers]}

@app.post("/analyze_charts")
async def analyze_charts(request: AnalyzeRequest):
    """
    Generate comprehensive chart data for a ticker.
    Now includes caching and multi-agent analysis.
    """
    ticker = request.ticker.upper()
    period_days = request.period_days
    interval = request.interval  # None for daily, '5m'/'15m'/'1h' for intraday
    logger.info(f"Analyzing charts for {ticker}, period={period_days}d, interval={interval}")

    # ── Intraday fast path ─────────────────────────────────────────────────
    # For intraday requests: fetch from yfinance directly, skip agents/fundamentals,
    # cache for a short TTL (15 min) since prices change rapidly.
    INTRADAY_INTERVALS = {'5m', '15m', '1h'}
    if interval in INTRADAY_INTERVALS:
        intraday_cache_key = f"intraday_{ticker}_{interval}"
        cached = cache.get(intraday_cache_key)
        if cached:
            logger.info(f"Serving intraday {ticker} @ {interval} from cache")
            return cached

        chart_data = chart_gen.generate_intraday_chart_data(ticker, interval)
        if "error" in chart_data:
            raise HTTPException(status_code=404, detail=chart_data["error"])

        response = {
            **chart_data,
            "analysis":     None,
            "news":         [],
            "fundamentals": None,
            "is_intraday":  True,
        }
        cache.set(intraday_cache_key, response)   # 5-min default TTL
        return response
    # ── End intraday fast path ─────────────────────────────────────────────

    logger.info(f"Analyzing charts for {ticker} with period={period_days} days")
    
    # 1. Fetch/Update Data first to verify freshness
    # We check DB first. If data is stale, we update it.
    # Only if data is fresh do we consider checking the cache.
    
    try:
        # Check if we have recent data, if not update it
        df = db.get_historical_data(ticker)
        is_stale = False
        last_bar_date = None
        
        if not df.empty:
            last_date = df.index.max()
            last_bar_date = last_date.date()
            
            # Use market_hours helper to see if we truly need a refresh
            if not is_data_fresh(last_date):
                logger.info(f"Data for {ticker} is stale (Last: {last_bar_date}). Refreshing...")
                is_stale = True
        else:
            is_stale = True
                
        if is_stale:
             logger.info(f"Data for {ticker} is stale or missing. Fetching fresh data...")
             try:
                # Pass last_bar_date for incremental fetch (None = full 5yr fetch)
                data_collector.update_stock_data(ticker, last_bar_date=last_bar_date)
                # Re-fetch after update
                df = db.get_historical_data(ticker)
                # We updated data, so we should NOT use the old cache
                # Invalidate cache implicitly by not checking it yet
                cache.delete(f"analysis_{ticker}_{period_days}") 
             except Exception as fetch_error:
                logger.error(f"Failed to update data for {ticker}: {fetch_error}")
                # Continue with existing data if possible
                
        # 2. Check Cache (Only if we didn't just determine it was stale/updated)
        # If we just updated, we want to regenerate analysis to include new data.
        cache_key = f"analysis_{ticker}_{period_days}"
        
        # If we didn't just update (is_stale=False), try cache
        if not is_stale:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Serving {ticker} from cache")
                return cached_data

        # 3. Generate Chart Data (Visuals)
        # If we are here, it means either cache miss OR we updated data
        chart_data = chart_gen.generate_chart_data(ticker, period_days=period_days)
        
        # 4. Perform Analysis (Agents)
        # ... rest of the code as is ...
        if "error" in chart_data:
             if "No data" in chart_data["error"] and df.empty:
                 raise HTTPException(status_code=404, detail="Stock data not found and could not be fetched.")
             # If just period error, might be fine to return what we have or error out
             # raise HTTPException(status_code=404, detail=chart_data["error"])

        # 4. Multi-Agent Analysis (The Brains)
        # News is fetched FIRST so the SentimentAgent can use it in the orchestrator.

        # 4a. Fetch News (Context) - Multi-source with fallback
        news_items = []
        twitter_items = []
        try:
            logger.info(f"Attempting to fetch news for {ticker}")

            # Try News API first (extensive sources, 150k+ outlets)
            if newsapi.enabled:
                logger.info("News API is enabled, fetching news...")
                news_items = newsapi.fetch_company_news(ticker, hours_back=48)
                logger.info(f"Fetched {len(news_items)} news items from News API")
            else:
                logger.warning("News API not enabled (missing API key)")

            # Fallback to Finnhub if News API returned no results
            if not news_items and finnhub.client:
                logger.info("Falling back to Finnhub...")
                news_items = finnhub.fetch_company_news(ticker, hours_back=24)
                logger.info(f"Fetched {len(news_items)} news items from Finnhub")
            elif not news_items:
                logger.info("Finnhub client not initialized")

            # Fallback to Reddit if still no news
            if not news_items and reddit.reddit:
                logger.info("Falling back to Reddit mentions...")
                news_items = reddit.search_ticker_mentions(ticker)
                logger.info(f"Fetched {len(news_items)} items from Reddit")

            # GET LIVE PRICE QUOTE (for absolute latest price)
            live_price = None
            try:
                # 1. Try Finnhub quote first
                quote_data = finnhub.get_quote(ticker)
                if quote_data and quote_data.get('price'):
                    live_price = quote_data['price']
                    logger.info(f"Fetched live price from Finnhub: ${live_price}")
                
                # 2. Fallback to yfinance fast_info
                if not live_price:
                    live_price = float(yf.Ticker(ticker).fast_info['lastPrice'])
                    logger.info(f"Fetched live price from yfinance fast_info: ${live_price}")
            except Exception as quote_err:
                logger.warning(f"Could not fetch live quote: {quote_err}")

            # Twitter: always fetch independently and merge (not a fallback)
            if twitter.client:
                logger.info("Fetching Twitter mentions...")
                twitter_items = twitter.search_ticker(ticker, limit=10)
                logger.info(f"Fetched {len(twitter_items)} tweets for {ticker}")
            else:
                logger.info("Twitter connector not initialized (no credentials)")

        except Exception as e:
            logger.warning(f"News fetch error: {e}")

        # DEBUG LOGGING
        logger.info(f"DEBUG: news_items count: {len(news_items)}, twitter_items count: {len(twitter_items)}")
        logger.info(f"DEBUG: finnhub.client is {finnhub.client}")
        logger.info(f"DEBUG: newsapi.enabled is {newsapi.enabled}")
        logger.info(f"DEBUG: reddit.reddit is {reddit.reddit}")
        logger.info(f"DEBUG: twitter.client is {twitter.client}")

        # MOCK DATA FALLBACK (Only if NO API clients are configured)
        should_mock = not news_items and not twitter_items and (not finnhub.client and not newsapi.enabled and not reddit.reddit)
        logger.info(f"DEBUG: Should use mock data? {should_mock}")

        if should_mock:
            logger.info("Generating mock news data for UI verification (APIs not configured)")
            import time
            current_time = int(time.time())
            news_items = [
                {
                    "headline": f"MOCK: Analysts Upgrade {ticker} to Buy",
                    "summary": f"Top analysts have upgraded {ticker} citing strong earnings potential and market growth.",
                    "source": "MarketWatch",
                    "datetime": current_time - 3600,
                    "url": "https://marketwatch.com",
                    "sentiment_score": 0.65
                },
                {
                    "headline": f"{ticker} Releases New Product Line",
                    "summary": "The company announced a new line of AI-driven tools expected to boost Q3 revenue.",
                    "source": "Bloomberg",
                    "datetime": current_time - 7200,
                    "url": "https://bloomberg.com",
                    "sentiment_score": 0.8
                },
                {
                    "headline": f"Market Volatility Impacts {ticker}",
                    "summary": "Broader market concerns over interest rates have led to slight pullback in tech stocks.",
                    "source": "TechCrunch",
                    "datetime": current_time - 18000,
                    "url": "https://techcrunch.com",
                    "sentiment_score": -0.2
                }
            ]

        # Score articles that don't already have a sentiment_score
        news_items = orchestrator.sentiment_agent.analyze_articles(news_items)
        twitter_items = orchestrator.sentiment_agent.analyze_articles(twitter_items)

        # 4a-ii. Try Finnhub aggregate /news-sentiment (premium — graceful fallback)
        finnhub_sentiment_data = None
        try:
            if finnhub.client:
                finnhub_sentiment_data = finnhub.fetch_news_sentiment(ticker)
                if finnhub_sentiment_data:
                    logger.info(
                        f"Finnhub aggregate sentiment for {ticker}: "
                        f"compound={finnhub_sentiment_data.get('compound_score', 'N/A')}"
                    )
                else:
                    logger.info(f"Finnhub aggregate sentiment unavailable for {ticker} (free tier or no data)")
        except Exception as fh_sent_err:
            logger.warning(f"Could not fetch Finnhub aggregate sentiment for {ticker}: {fh_sent_err}")

        # 4b. Prepare data package for agents (includes news for SentimentAgent)
        df = db.get_historical_data(ticker) # Re-fetch to be sure
        
        # INJECT LIVE PRICE FOR SIGNAL ANALYSIS
        if live_price:
            df = _inject_live_price(df, live_price)

        all_articles = news_items + twitter_items
        analysis_data = {
            "historical_df":    df,
            "news_articles":    all_articles,          # ← SentimentAgent VADER fallback
            "finnhub_sentiment": finnhub_sentiment_data, # ← SentimentAgent priority-1
            "quant_weights":    request.quant_weights,  # User-configurable weights
        }

        # 4c. Run Multi-Agent Orchestration (Pattern + Quant + Sentiment)
        agent_results = orchestrator.analyze(ticker, analysis_data)

        # 5. Fetch Company Fundamentals (DB-cached, 10-day TTL)
        fundamentals = {}
        try:
            fundamentals = fundamentals_collector.get_fundamentals(ticker)
        except Exception as fe:
            logger.warning(f"Could not fetch fundamentals for {ticker}: {fe}")

        # 6. Construct Final Response
        all_news = news_items + twitter_items
        all_news.sort(key=lambda x: x.get("datetime", 0), reverse=True)

        response = {
            **chart_data, # Contains 'charts', 'levels', 'indicators', 'current_price'
            "analysis": agent_results, # Contains recommendation, confidence, reasoning
            "news": all_news[:10] if all_news else [],
            "fundamentals": fundamentals,
        }

        # Override current_price if we got a live quote
        if live_price:
            response['current_price'] = live_price
            # Also update indicators if available
            if 'indicators' in response:
                response['indicators']['current_price'] = live_price

        # Cache the result
        cache.set(cache_key, response)
        
        return response

    except Exception as e:
        logger.error(f"Error in analyze_charts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


# ──────────────────────────────────────────────────────────────────────────────
# Backtesting endpoints
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/backtest")
async def run_backtest(request: BacktestRequest):
    """
    Run a 5-year walk-forward backtest on the given ticker.
    Exit strategy: exit position when model generates opposite signal.
    """
    ticker = request.ticker.upper()
    logger.info(f"Backtest requested for {ticker}")
    try:
        try:
            data_collector.update_stock_data(ticker)
        except Exception as e:
            logger.warning(f"Data update for {ticker} failed, using cached: {e}")

        backtester = Backtester(db)
        result = backtester.run(ticker)
        metrics = compute_metrics(
            result["trade_log"],
            result["equity_curve"],
            result["buy_hold_curve"],
        )
        return {
            "ticker":         ticker,
            "start_date":     result["start_date"],
            "end_date":       result["end_date"],
            "bar_count":      result["bar_count"],
            "metrics":        metrics,
            "trade_log":      result["trade_log"],
            "equity_curve":   result["equity_curve"],
            "buy_hold_curve": result["buy_hold_curve"],
        }
    except Exception as e:
        logger.error(f"Backtest error for {ticker}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize")
async def run_optimize(request: OptimizeRequest):
    """
    Grid-search optimizer. Saves best params to agents/tuned_params.json
    and reloads the orchestrator immediately.
    """
    ticker = request.ticker.upper()
    logger.info(f"Optimizer requested for {ticker}")
    try:
        try:
            data_collector.update_stock_data(ticker)
        except Exception as e:
            logger.warning(f"Data update for {ticker} failed, using cached: {e}")

        optimizer = Optimizer(db)
        result = optimizer.optimize(ticker)

        # Reload orchestrator so new params take effect immediately
        global orchestrator
        orchestrator = AnalystOrchestrator()
        logger.info("Orchestrator reloaded with optimized parameters")

        return result
    except Exception as e:
        logger.error(f"Optimizer error for {ticker}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/optimize_wf")
async def run_walk_forward_optimize(request: WalkForwardRequest):
    """
    Multi-ticker walk-forward optimizer with overfitting detection.
    Trains on first 60% of data, validates on last 40%.
    """
    tickers = [t.upper() for t in request.tickers]
    logger.info(f"Walk-forward optimizer requested for {tickers}, train_ratio={request.train_ratio}")
    try:
        wfo = WalkForwardOptimizer(db, data_collector)
        result = wfo.optimize(tickers=tickers, train_ratio=request.train_ratio)

        if "error" not in result:
            # Reload orchestrator so new params take effect immediately
            global orchestrator
            orchestrator = AnalystOrchestrator()
            logger.info("Orchestrator reloaded with walk-forward optimized parameters")

        return result
    except Exception as e:
        logger.error(f"Walk-forward optimizer error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Batch Scan — lightweight recommendations for watchlist
# ──────────────────────────────────────────────────────────────────────────────

class BatchScanRequest(BaseModel):
    tickers: List[str]

@app.post("/batch_scan")
async def batch_scan(request: BatchScanRequest):
    """
    Batch scan for watchlist tickers.
    Uses the SAME orchestrator + synthesis pipeline as /analyze_charts
    to ensure consistent recommendations.
    """
    tickers = [t.upper() for t in request.tickers]
    logger.info(f"Batch scan requested for {tickers}")

    results = []
    for t in tickers:
        try:
            # 1. Refresh data if stale (incremental fetch)
            df = db.get_historical_data(t)
            if not df.empty:
                last_bar = df.index.max()
                if not is_data_fresh(last_bar):
                    logger.info(f"Batch scan refreshing stale ticker: {t}")
                    data_collector.update_stock_data(t, last_bar_date=last_bar.date())
                    df = db.get_historical_data(t)
            else:
                data_collector.update_stock_data(t)  # Full fetch — no prior data
                df = db.get_historical_data(t)

            if df.empty or len(df) < 30:
                results.append({
                    "ticker": t,
                    "recommendation": "N/A",
                    "confidence": 0,
                    "current_price": None,
                    "change_pct": None,
                    "market_regime": "",
                    "risk_level": "Unknown",
                    "key_insight": "Insufficient data — run a full analysis first",
                })
                continue

            current_price = float(df['Close'].iloc[-1])
            prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else current_price

            # 2. Inject live price (same as analyze_charts)
            try:
                quote_data = finnhub.get_quote(t)
                if quote_data and quote_data.get('price'):
                    live_price_batch = quote_data['price']
                    df = _inject_live_price(df, live_price_batch)
                    current_price = live_price_batch
            except Exception:
                pass

            change_pct = round((current_price - prev_close) / prev_close * 100, 2)

            # 3. Fetch news for sentiment (same sources as analyze_charts)
            news_items = []
            try:
                if newsapi.enabled:
                    news_items = newsapi.fetch_company_news(t, hours_back=48) or []
            except Exception:
                pass
            try:
                if not news_items and finnhub.client:
                    news_items = finnhub.fetch_company_news(t, hours_back=24) or []
            except Exception:
                pass

            # 3b. Finnhub aggregate sentiment (premium; graceful fallback)
            finnhub_sent = None
            try:
                if finnhub.client:
                    finnhub_sent = finnhub.fetch_news_sentiment(t)
            except Exception:
                pass

            # 4. Use the SAME orchestrator as the detailed analysis
            data_payload = {
                'historical_df':    df,
                'news_articles':    news_items,
                'finnhub_sentiment': finnhub_sent,
            }

            synthesis = orchestrator.analyze(t, data_payload)

            results.append({
                "ticker": t,
                "recommendation": synthesis["recommendation"],
                "confidence": synthesis["confidence"],
                "current_price": round(current_price, 2),
                "change_pct": change_pct,
                "market_regime": synthesis.get("market_regime", ""),
                "risk_level": synthesis.get("risk_level", "Medium"),
                "key_insight": synthesis.get("key_insight", ""),
                "target_price": synthesis.get("target_price"),
                "stop_loss": synthesis.get("stop_loss"),
                "time_horizon": synthesis.get("time_horizon", ""),
                "trade_reasoning": synthesis.get("trade_reasoning", ""),
                "signal_strength": synthesis.get("signal", 0),
            })

        except Exception as e:
            logger.warning(f"Batch scan failed for {t}: {e}")
            results.append({
                "ticker": t,
                "recommendation": "ERROR",
                "confidence": 0,
                "current_price": None,
                "change_pct": None,
                "market_regime": "",
                "risk_level": "Unknown",
                "key_insight": str(e),
            })

    return {"results": results}


# ──────────────────────────────────────────────────────────────────────────────
# Streaming Batch Scan — SSE endpoint that sends results as each ticker completes
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/batch_scan_stream")
async def batch_scan_stream(request: BatchScanRequest):
    """
    Streaming batch scan using Server-Sent Events.
    Sends each ticker result as an SSE event the moment it's ready,
    so the frontend can render progressively instead of waiting for all.
    """
    tickers = [t.upper() for t in request.tickers]
    logger.info(f"Streaming batch scan requested for {len(tickers)} tickers")

    def generate():
        # Send total count first so frontend can show progress
        yield f"data: {json.dumps({'type': 'start', 'total': len(tickers)})}\n\n"

        for idx, t in enumerate(tickers):
            try:
                # 1. Refresh data if stale (incremental fetch)
                df = db.get_historical_data(t)
                if not df.empty:
                    last_bar = df.index.max()
                    if not is_data_fresh(last_bar):
                        logger.info(f"Stream scan refreshing stale ticker: {t}")
                        data_collector.update_stock_data(t, last_bar_date=last_bar.date())
                        df = db.get_historical_data(t)
                else:
                    data_collector.update_stock_data(t)
                    df = db.get_historical_data(t)

                if df.empty or len(df) < 30:
                    result = {
                        "type": "result",
                        "index": idx,
                        "ticker": t,
                        "recommendation": "N/A",
                        "confidence": 0,
                        "current_price": None,
                        "change_pct": None,
                        "market_regime": "",
                        "risk_level": "Unknown",
                        "key_insight": "Insufficient data",
                    }
                    yield f"data: {json.dumps(result)}\n\n"
                    continue

                current_price = float(df['Close'].iloc[-1])
                prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else current_price

                # 2. Inject live price
                try:
                    quote_data = finnhub.get_quote(t)
                    if quote_data and quote_data.get('price'):
                        live_price_batch = quote_data['price']
                        df = _inject_live_price(df, live_price_batch)
                        current_price = live_price_batch
                except Exception:
                    pass

                change_pct = round((current_price - prev_close) / prev_close * 100, 2)

                # 3. Fetch news
                news_items = []
                try:
                    if newsapi.enabled:
                        news_items = newsapi.fetch_company_news(t, hours_back=48) or []
                except Exception:
                    pass
                try:
                    if not news_items and finnhub.client:
                        news_items = finnhub.fetch_company_news(t, hours_back=24) or []
                except Exception:
                    pass

                # 3b. Finnhub aggregate sentiment (premium; graceful fallback)
                finnhub_sent = None
                try:
                    if finnhub.client:
                        finnhub_sent = finnhub.fetch_news_sentiment(t)
                except Exception:
                    pass

                # 4. Run orchestrator
                data_payload = {
                    'historical_df':    df,
                    'news_articles':    news_items,
                    'finnhub_sentiment': finnhub_sent,
                }
                synthesis = orchestrator.analyze(t, data_payload)

                result = {
                    "type": "result",
                    "index": idx,
                    "ticker": t,
                    "recommendation": synthesis["recommendation"],
                    "confidence": synthesis["confidence"],
                    "current_price": round(current_price, 2),
                    "change_pct": change_pct,
                    "market_regime": synthesis.get("market_regime", ""),
                    "risk_level": synthesis.get("risk_level", "Medium"),
                    "key_insight": synthesis.get("key_insight", ""),
                    "target_price": synthesis.get("target_price"),
                    "stop_loss": synthesis.get("stop_loss"),
                    "time_horizon": synthesis.get("time_horizon", ""),
                    "trade_reasoning": synthesis.get("trade_reasoning", ""),
                    "signal_strength": synthesis.get("signal", 0),
                }
                yield f"data: {json.dumps(result)}\n\n"

            except Exception as e:
                logger.warning(f"Stream scan failed for {t}: {e}")
                result = {
                    "type": "result",
                    "index": idx,
                    "ticker": t,
                    "recommendation": "ERROR",
                    "confidence": 0,
                    "current_price": None,
                    "change_pct": None,
                    "market_regime": "",
                    "risk_level": "Unknown",
                    "key_insight": str(e),
                }
                yield f"data: {json.dumps(result)}\n\n"

        # Signal completion
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Log Viewer Endpoints ──────────────────────────────────────────────────

import os as _os
import re as _re
import asyncio as _asyncio
from agents.log_watcher import LogWatcherAgent

_log_watcher = LogWatcherAgent(log_dir=_os.path.join(_os.path.dirname(__file__), 'logs'))


@app.get("/logs/analysis")
async def analyze_logs():
    """
    Run the Log Watcher Agent to analyze today's logs.
    Returns health score, categorized issues, and actionable recommendations.
    """
    try:
        report = _log_watcher.analyze()
        return report
    except Exception as e:
        logger.error(f"Log analysis failed: {e}")
        return {"error": str(e), "health_score": -1, "issues": [], "recommendations": []}


def _get_log_path():
    """Get path to today's log file."""
    log_dir = _os.path.join(_os.path.dirname(__file__), 'logs')
    today = datetime.now().strftime('%Y-%m-%d')
    return _os.path.join(log_dir, f"trade_app_{today}.log")


def _parse_log_line(line: str) -> dict:
    """Parse a log line into a structured dict."""
    line = line.strip()
    if not line:
        return None

    # Format: 2026-04-15 12:52:27 - agents.langgraph_brain - WARNING - message
    pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - ([\w.]+) - (\w+) - (.+)$'
    match = _re.match(pattern, line)

    if match:
        timestamp, source, level, message = match.groups()
        return {
            "timestamp": timestamp,
            "source": source,
            "level": level,
            "message": message,
        }
    else:
        # Non-standard line (traceback continuation, etc.)
        return {
            "timestamp": "",
            "source": "",
            "level": "DEBUG",
            "message": line,
        }


@app.get("/logs/recent")
async def get_recent_logs(lines: int = 200, level: str = ""):
    """
    Get the most recent log lines from today's log file.
    Optional level filter: INFO, WARNING, ERROR
    """
    log_path = _get_log_path()

    if not _os.path.exists(log_path):
        return {"logs": [], "file": log_path, "error": "No log file for today"}

    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()

        # Parse all lines
        parsed = []
        for raw_line in all_lines:
            entry = _parse_log_line(raw_line)
            if entry is None:
                continue

            # Level filter
            if level and entry["level"] != level.upper():
                continue

            # Skip noisy httpx / uvicorn access logs
            if entry["source"] in ("httpx", "uvicorn.access"):
                continue

            parsed.append(entry)

        # Return last N
        recent = parsed[-lines:] if len(parsed) > lines else parsed

        return {
            "logs": recent,
            "total": len(parsed),
            "file": _os.path.basename(log_path),
        }
    except Exception as e:
        return {"logs": [], "error": str(e)}


@app.get("/logs/stream")
async def stream_logs(request: Request):
    """
    SSE endpoint that tails the log file in real-time.
    Frontend connects via EventSource.
    """
    log_path = _get_log_path()

    async def event_generator():
        if not _os.path.exists(log_path):
            yield f"data: {json.dumps({'error': 'No log file'})}\n\n"
            return

        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            # Seek to end
            f.seek(0, 2)

            while True:
                if await request.is_disconnected():
                    break

                line = f.readline()
                if line:
                    entry = _parse_log_line(line)
                    if entry and entry["source"] not in ("httpx", "uvicorn.access"):
                        yield f"data: {json.dumps(entry)}\n\n"
                else:
                    await _asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
