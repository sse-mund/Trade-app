# Configuration for Trade Strategy App

# Top 50 Stocks (by market cap, diversified across sectors)
# Used by /top_stocks endpoint and Buy Recommendations scanner
TOP_50_STOCKS = [
    # ─── Mega Cap Tech ────────────────────────────
    'NVDA',   # NVIDIA Corp
    'AAPL',   # Apple Inc
    'MSFT',   # Microsoft Corp
    'AMZN',   # Amazon.com Inc
    'GOOGL',  # Alphabet Inc
    'META',   # Meta Platforms Inc
    'AVGO',   # Broadcom Inc
    'TSLA',   # Tesla Inc
    # ─── Semiconductors ──────────────────────────
    'ASML',   # ASML Holding
    'AMD',    # Advanced Micro Devices
    'QCOM',   # Qualcomm Inc
    'MU',     # Micron Technology
    'INTC',   # Intel Corp
    'TXN',    # Texas Instruments
    'ARM',    # Arm Holdings
    # ─── Software / Cloud ────────────────────────
    'CSCO',   # Cisco Systems
    'PLTR',   # Palantir Technologies
    'ADBE',   # Adobe Inc
    'INTU',   # Intuit Inc
    'CRWD',   # CrowdStrike
    'PANW',   # Palo Alto Networks
    'PYPL',   # PayPal Holdings
    # ─── Consumer / Retail ────────────────────────
    'WMT',    # Walmart Inc
    'COST',   # Costco Wholesale
    'NFLX',   # Netflix Inc
    'PEP',    # PepsiCo Inc
    'SBUX',   # Starbucks Corp
    'BKNG',   # Booking Holdings
    'ABNB',   # Airbnb Inc
    # ─── Telecom / Media ─────────────────────────
    'TMUS',   # T-Mobile US
    'CMCSA',  # Comcast Corp
    'EA',     # Electronic Arts
    # ─── Biotech / Healthcare ────────────────────
    'AMGN',   # Amgen Inc
    'ISRG',   # Intuitive Surgical
    'VRTX',   # Vertex Pharmaceuticals
    'GILD',   # Gilead Sciences
    'REGN',   # Regeneron Pharma
    'DXCM',   # DexCom Inc
    # ─── Industrial / Transport ──────────────────
    'HON',    # Honeywell International
    'CSX',    # CSX Corp
    'CTAS',   # Cintas Corp
    'AXON',   # Axon Enterprise
    # ─── Utilities / Energy ──────────────────────
    'CEG',    # Constellation Energy
    'LIN',    # Linde plc
    'FANG',   # Diamondback Energy
    # ─── Financial / Other ───────────────────────
    'ADP',    # Automatic Data Processing
    'SHOP',   # Shopify Inc
    'MELI',   # MercadoLibre Inc
]


# Database Configuration
DATABASE_PATH = 'stock_data.db'

# Walk-Forward Optimizer — default ticker universe
# These tickers are used for multi-ticker optimization to prevent overfitting.
# Edit this list to change which stocks the optimizer trains/tests on.
OPTIMIZER_TICKERS = [
    'NVDA',   # NVIDIA Corp        — high-vol tech
    'AAPL',   # Apple Inc          — mega-cap stable
    'MSFT',   # Microsoft Corp     — mega-cap stable
    'AMZN',   # Amazon.com Inc     — e-commerce/cloud
    'GOOGL',  # Alphabet Inc       — search/ads
    'META',   # Meta Platforms Inc  — social/AI
    'TSLA',   # Tesla Inc          — high-vol EV
    'AMD',    # Advanced Micro Dev — semiconductor
]

# Data Fetch Configuration
HISTORICAL_PERIOD = '5y'  # 5 years of historical data
FETCH_INTERVAL = '1d'     # Daily data
BATCH_DELAY = 0.5         # Delay between API calls (seconds)


# ──────────────────────────────────────────────────────────────────────────────
# Watchlist Monitor Configuration
# ──────────────────────────────────────────────────────────────────────────────
import os as _os

MONITOR_INTERVAL_MINUTES = int(_os.getenv('MONITOR_INTERVAL_MINUTES', '10'))
MONITOR_RSI_OVERSOLD = 30           # RSI threshold for oversold alert
MONITOR_RSI_OVERBOUGHT = 70         # RSI threshold for overbought alert
MONITOR_VOLUME_SPIKE_THRESHOLD = 2.0  # Relative volume multiplier to trigger alert
MONITOR_SENTIMENT_FLIP_THRESHOLD = 0.10  # Min sentiment score change to flag
MONITOR_CONFIDENCE_MIN = 0.5        # Minimum confidence for recommendation flip alerts

# ──────────────────────────────────────────────────────────────────────────────
# Daily Walk-Forward Optimizer Schedule
# ──────────────────────────────────────────────────────────────────────────────
# Runs automatically once per day after market close to retune signal weights.
# Time is in US/Eastern (ET). Default: 18:15 ET (15 min after close).
# Override via env var:  OPTIMIZER_DAILY_RUN_TIME=18:15
OPTIMIZER_DAILY_RUN_TIME = _os.getenv('OPTIMIZER_DAILY_RUN_TIME', '18:15')

