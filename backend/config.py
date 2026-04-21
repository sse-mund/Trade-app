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

