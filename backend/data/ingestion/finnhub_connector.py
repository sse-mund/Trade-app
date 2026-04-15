import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

try:
    import finnhub
except ImportError:
    logger.warning("finnhub-python not installed. Run: pip install finnhub-python")
    finnhub = None


class FinnhubConnector:
    """
    Connector for Finnhub API to fetch real-time financial news.
    
    Features:
    - Company news fetching
    - Market news fetching
    - Rate limiting (60 calls/min on free tier)
    - Standardized output schema
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Finnhub connector.
        
        Args:
            api_key: Finnhub API key. If not provided, reads from FINNHUB_API_KEY env variable.
        """
        self.api_key = api_key or os.getenv('FINNHUB_API_KEY', '')
        
        if not self.api_key:
            logger.warning("No Finnhub API key provided. Set FINNHUB_API_KEY environment variable.")
            self.client = None
        elif finnhub is None:
            logger.error("finnhub-python package not installed")
            self.client = None
        else:
            self.client = finnhub.Client(api_key=self.api_key)
            logger.info("Finnhub connector initialized")
        
        # Rate limiting: 60 calls/min = 1 call per second
        self.last_call_time = 0
        self.min_call_interval = 1.0  # seconds
    
    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limit."""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_call_interval:
            time.sleep(self.min_call_interval - elapsed)
        self.last_call_time = time.time()
    
    def fetch_company_news(
        self, 
        ticker: str, 
        hours_back: int = 24
    ) -> List[Dict]:
        """
        Fetch company-specific news for a ticker.
        
        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            hours_back: How many hours back to fetch news (default: 24)
        
        Returns:
            List of news articles in standardized format:
            [
                {
                    'headline': str,
                    'summary': str,
                    'source': str,
                    'datetime': int,  # Unix timestamp
                    'url': str,
                    'related': str,  # Ticker symbol
                    'sentiment_score': None  # To be filled by sentiment agent
                },
                ...
            ]
        """
        if not self.client:
            logger.error("Finnhub client not initialized")
            return []
        
        try:
            # Calculate date range
            to_date = datetime.now()
            from_date = to_date - timedelta(hours=hours_back)
            
            # Format dates as YYYY-MM-DD
            from_str = from_date.strftime('%Y-%m-%d')
            to_str = to_date.strftime('%Y-%m-%d')
            
            logger.info(f"Fetching Finnhub news for {ticker} from {from_str} to {to_str}")
            
            # Rate limiting
            self._wait_for_rate_limit()
            
            # Fetch news
            news = self.client.company_news(ticker, _from=from_str, to=to_str)
            logger.info(f"news  : {news}")
            # Standardize format
            standardized = []
            for article in news:
                standardized.append({
                    'headline': article.get('headline', ''),
                    'summary': article.get('summary', ''),
                    'source': article.get('source', 'Finnhub'),
                    'datetime': article.get('datetime', 0),
                    'url': article.get('url', ''),
                    'related': ticker,
                    'sentiment_score': None  # To be filled later
                })
            
            logger.info(f"Fetched {len(standardized)} news articles for {ticker}")
            return standardized
            
        except Exception as e:
            logger.error(f"Error fetching Finnhub news for {ticker}: {str(e)}")
            return []
    
    def fetch_market_news(self, category: str = 'general') -> List[Dict]:
        """
        Fetch general market news.
        
        Args:
            category: News category ('general', 'forex', 'crypto', 'merger')
        
        Returns:
            List of news articles in standardized format
        """
        if not self.client:
            logger.error("Finnhub client not initialized")
            return []
        
        try:
            logger.info(f"Fetching Finnhub market news for category: {category}")
            
            # Rate limiting
            self._wait_for_rate_limit()
            
            # Fetch news
            news = self.client.general_news(category)
            
            # Standardize format
            standardized = []
            for article in news[:10]:  # Limit to 10 articles
                standardized.append({
                    'headline': article.get('headline', ''),
                    'summary': article.get('summary', ''),
                    'source': article.get('source', 'Finnhub'),
                    'datetime': article.get('datetime', 0),
                    'url': article.get('url', ''),
                    'related': category,
                    'sentiment_score': None
                })
            
            logger.info(f"Fetched {len(standardized)} market news articles")
            return standardized
            
        except Exception as e:
            logger.error(f"Error fetching Finnhub market news: {str(e)}")
            return []

    def get_quote(self, ticker: str) -> Dict:
        """
        Fetch real-time quote for a ticker.
        Returns: {price, high, low, open, prev_close, change, change_pct}
        """
        if not self.client:
            return {}
            
        try:
            self._wait_for_rate_limit()
            quote = self.client.quote(ticker)
            
            # Finnhub quote fields:
            # c: Current price
            # d: Change
            # dp: Percent change
            # h: High price of the day
            # l: Low price of the day
            # o: Open price of the day
            # pc: Previous close price
            
            return {
                "price": float(quote.get('c', 0)),
                "change": float(quote.get('d', 0)),
                "change_pct": float(quote.get('dp', 0)),
                "high": float(quote.get('h', 0)),
                "low": float(quote.get('l', 0)),
                "open": float(quote.get('o', 0)),
                "prev_close": float(quote.get('pc', 0)),
                "timestamp": int(time.time())
            }
        except Exception as e:
            logger.error(f"Error fetching Finnhub quote for {ticker}: {e}")
            return {}


# Convenience function
def get_recent_news(ticker: str, hours: int = 24) -> List[Dict]:
    """
    Quick helper to fetch recent news for a ticker.
    
    Args:
        ticker: Stock ticker symbol
        hours: Hours back to fetch
    
    Returns:
        List of news articles
    """
    connector = FinnhubConnector()
    return connector.fetch_company_news(ticker, hours)


if __name__ == "__main__":
    # Test the connector
    logging.basicConfig(level=logging.INFO)
    
    connector = FinnhubConnector()
    if connector.client:
        news = connector.fetch_company_news("AAPL", hours_back=24)
        print(f"\nFetched {len(news)} articles for AAPL")
        if news:
            print("\nFirst article:")
            print(f"Headline: {news[0]['headline']}")
            print(f"Source: {news[0]['source']}")
            print(f"URL: {news[0]['url']}")
    else:
        print("Finnhub connector not initialized. Set FINNHUB_API_KEY environment variable.")
