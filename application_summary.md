# Trade Strategy AI — Application Summary

## Overview

Trade Strategy AI is a **multi-agent stock analysis platform** that combines technical analysis, quantitative metrics, and news sentiment to generate actionable trading recommendations. The system uses a **LangGraph-powered brain running on Ollama** (local LLM) to synthesize insights from three specialized agents — no cloud API costs required.

---

## Architecture

```
┌─────────────────── Frontend (React + Vite) ───────────────────┐
│  Candlestick Charts · Agent Insights · Brain Recommendation   │
│  Company Fundamentals · News Feed · Technical Indicators      │
└───────────────────────────┬────────────────────────────────────┘
                            │ REST API
┌───────────────────────────▼────────────────────────────────────┐
│                   FastAPI Backend                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐                   │
│  │ Pattern  │  │  Quant   │  │ Sentiment │   ← Agents        │
│  │  Agent   │  │  Agent   │  │  Agent    │                    │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘                   │
│       └──────────────┴──────────────┘                          │
│                      │                                         │
│             ┌────────▼────────┐                                │
│             │  🧠 LangGraph   │  ← Ollama LLM (local)         │
│             │     Brain       │                                │
│             └────────┬────────┘                                │
│                      │ fallback                                │
│             ┌────────▼────────┐                                │
│             │  Expert System  │  ← Rule-based (no LLM needed) │
│             └─────────────────┘                                │
│                                                                │
│  Data Sources: Finnhub · NewsAPI · yfinance · SQLite           │
└────────────────────────────────────────────────────────────────┘
```

---

## What It Can Do

### 📐 Pattern Analysis
- Detects **support and resistance** levels from local minima/maxima
- Identifies **breakouts** (bullish/bearish) through S/R levels
- Classifies **trend direction** using 50-day SMA
- Uses Ollama LLM to reason about patterns with natural-language explanations

### 📊 Quantitative Analysis
- Computes **RSI** (14-period) with overbought/oversold classification
- Measures **relative volume** against 20-day moving average
- Calculates **Bollinger Band width** for volatility squeeze detection
- Evaluates **MACD** crossovers for momentum signals

### 📰 Sentiment Analysis
- Aggregates news from **Finnhub** and **NewsAPI**
- Scores articles using **VADER sentiment** analysis
- Classifies overall sentiment as bullish/bearish/neutral
- Counts positive vs negative article ratios

### 🧠 AI Brain (LangGraph + Ollama)
- **Cross-signal confluence** — detects when all 3 agents agree or conflict
- **Contradiction analysis** — identifies bull traps, momentum divergence
- **Market regime classification** — Trending, Ranging, Volatile, Breakout, Squeeze
- **Risk factor identification** — specific risk warnings based on data
- **Natural-language reasoning** — full narrative explaining the recommendation
- **Automatic fallback** — uses rule-based expert system if Ollama is unavailable

### 📈 Charting
- **Candlestick charts** (100 candles) for all timeframes
- **Bollinger Bands** overlay chart
- **Volume** chart with 20-day moving average
- **RSI** chart with overbought/oversold zones
- **MACD** chart with signal line and histogram
- **Daily** (3M, 1Y, 5Y) and **intraday** (5M, 15M, 1H) periods

### 🏢 Company Fundamentals
- Market cap, P/E ratio, EPS, dividend yield
- Revenue, profit margins, debt-to-equity
- 52-week high/low, beta, analyst target prices
- Sector and industry classification

### 📰 News Feed
- Filterable by source (Finnhub, NewsAPI)
- Sentiment-tagged headlines (positive/negative/neutral badges)
- Direct links to full articles

### 🎯 Fine-Tuning Pipeline
- **Dataset generator** — creates 59,550 training examples from 50 tickers × 5 years
- Each example labels what **actually happened** in the next 5 trading days
- **Kaggle notebook** — fine-tunes with Kaggle on T4 GPU
- Exports GGUF model for direct import into Ollama

---

## How It Works (User Flow)

1. Enter a stock ticker (e.g., `AAPL`) and click **Analyze**
2. Backend fetches latest market data and news
3. Three agents independently analyze the data
4. LangGraph Brain sends all agent metrics to Ollama for synthesis
5. Frontend displays:
   - 🧠 **Brain Recommendation** with key insight, risk factors, and market regime
   - 📐📊📰 **Agent cards** with individual signals and confluence badge
   - 📈 **Candlestick charts** with technical indicators
   - 🏢 **Company fundamentals** and 📰 **news feed**

---

## What It Can't Do

| Limitation | Why |
|---|---|
| **Not real-time** | Data is fetched on-demand, not streaming. No live price feed or WebSocket updates. |
| **No order execution** | Analysis only — does not connect to any brokerage to place trades. |
| **No portfolio tracking** | Analyzes one ticker at a time. No watchlists, portfolios, or position management. |
| **No options/futures** | Only supports equities (stocks). No derivatives analysis. |
| **LLM hallucinations** | Ollama can occasionally generate plausible but incorrect reasoning. The expert system fallback is deterministic but less nuanced. |
| **Limited news sources** | Only Finnhub and NewsAPI. No social media sentiment (Reddit/Twitter connectors exist but are disabled). |
| **No backtesting** | Cannot simulate past trade performance against historical data. |
| **Single-user** | No authentication, user accounts, or multi-tenant support. |
| **No mobile app** | Web-only. Responsive on tablets but not optimized for phones. |

---

## Future Improvements

### Short Term (Quick Wins)
- **Enable Reddit/Twitter** sentiment — connectors already exist, just need API keys
- **Watchlist** — save and track multiple tickers
- **Alert system** — notify when a ticker hits a specific condition (RSI oversold, breakout, etc.)
- **Backtesting engine** — simulate strategy performance against historical data

### Medium Term
- **WebSocket live prices** — real-time price updates without manual refresh
- **Multi-ticker dashboard** — compare multiple stocks side-by-side
- **Sector heatmap** — visualize market-wide sentiment
- **Options chain integration** — add options flow and implied volatility
- **User authentication** — save preferences and analysis history

### Long Term
- **Brokerage integration** — connect to Alpaca, Interactive Brokers, or TD Ameritrade for paper/live trading
- **RAG system** — store and retrieve past pattern outcomes for context-aware reasoning
- **Multi-model ensemble** — run multiple fine-tuned models and aggregate their predictions
- **Mobile app** — React Native wrapper for iOS/Android
- **Custom strategy builder** — let users define their own indicator combinations and rules

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Recharts, Lucide Icons |
| Backend | Python 3, FastAPI, Uvicorn |
| AI/ML | LangGraph, Ollama (llama3.2:3b), Unsloth (fine-tuning) |
| Data | yfinance, Finnhub API, NewsAPI, VADER Sentiment |
| Database | SQLite (stock_data.db) |
| Styling | Vanilla CSS (dark theme) |
