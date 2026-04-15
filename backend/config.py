# Configuration for Trade Strategy App

# NASDAQ-100 Index Stocks (101 tickers, 100 companies)
# Used by /top_stocks endpoint and Buy Recommendations scanner
TOP_50_STOCKS = [
    # ─── Mega Cap Tech ────────────────────────────
    'NVDA',   # NVIDIA Corp
    'GOOG',   # Alphabet Inc (Class C)
    'GOOGL',  # Alphabet Inc (Class A)
    'AAPL',   # Apple Inc
    'MSFT',   # Microsoft Corp
    'AMZN',   # Amazon.com Inc
    'AVGO',   # Broadcom Inc
    'META',   # Meta Platforms Inc
    'TSLA',   # Tesla Inc
    # ─── Consumer / Retail ────────────────────────
    'WMT',    # Walmart Inc
    'COST',   # Costco Wholesale
    'NFLX',   # Netflix Inc
    'BKNG',   # Booking Holdings
    'SBUX',   # Starbucks Corp
    'ORLY',   # O'Reilly Automotive
    'ROST',   # Ross Stores
    'ABNB',   # Airbnb Inc
    'MNST',   # Monster Beverage
    'PEP',    # PepsiCo Inc
    'MDLZ',   # Mondelez International
    'KDP',    # Keurig Dr Pepper
    'KHC',    # Kraft Heinz
    'DASH',   # DoorDash Inc
    'CCEP',   # Coca-Cola Europacific
    # ─── Semiconductors ──────────────────────────
    'ASML',   # ASML Holding
    'MU',     # Micron Technology
    'AMD',    # Advanced Micro Devices
    'LRCX',   # Lam Research
    'AMAT',   # Applied Materials
    'INTC',   # Intel Corp
    'KLAC',   # KLA Corp
    'TXN',    # Texas Instruments
    'ADI',    # Analog Devices
    'QCOM',   # Qualcomm Inc
    'MRVL',   # Marvell Technology
    'NXPI',   # NXP Semiconductors
    'MPWR',   # Monolithic Power
    'MCHP',   # Microchip Technology
    'ARM',    # Arm Holdings
    # ─── Software / Cloud ────────────────────────
    'CSCO',   # Cisco Systems
    'PLTR',   # Palantir Technologies
    'INTU',   # Intuit Inc
    'ADBE',   # Adobe Inc
    'CRWD',   # CrowdStrike
    'PANW',   # Palo Alto Networks
    'SNPS',   # Synopsys Inc
    'CDNS',   # Cadence Design
    'FTNT',   # Fortinet Inc
    'ADSK',   # Autodesk Inc
    'WDAY',   # Workday Inc
    'DDOG',   # Datadog Inc
    'ZS',     # Zscaler Inc
    'TEAM',   # Atlassian Corp
    'PYPL',   # PayPal Holdings
    'MSTR',   # MicroStrategy
    'APP',    # AppLovin Corp
    # ─── Telecom / Media ─────────────────────────
    'TMUS',   # T-Mobile US
    'CMCSA',  # Comcast Corp
    'WBD',    # Warner Bros Discovery
    'CHTR',   # Charter Communications
    'EA',     # Electronic Arts
    'TTWO',   # Take-Two Interactive
    # ─── Biotech / Healthcare ────────────────────
    'AMGN',   # Amgen Inc
    'GILD',   # Gilead Sciences
    'ISRG',   # Intuitive Surgical
    'VRTX',   # Vertex Pharmaceuticals
    'REGN',   # Regeneron Pharma
    'IDXX',   # IDEXX Laboratories
    'ALNY',   # Alnylam Pharmaceuticals
    'DXCM',   # DexCom Inc
    'INSM',   # Insmed Inc
    'GEHC',   # GE HealthCare
    # ─── Industrial / Transport ──────────────────
    'HON',    # Honeywell International
    'CSX',    # CSX Corp
    'PCAR',   # PACCAR Inc
    'ODFL',   # Old Dominion Freight
    'FAST',   # Fastenal Co
    'CTAS',   # Cintas Corp
    'CPRT',   # Copart Inc
    'AXON',   # Axon Enterprise
    # ─── Utilities / Energy ──────────────────────
    'CEG',    # Constellation Energy
    'AEP',    # American Electric Power
    'XEL',    # Xcel Energy
    'EXC',    # Exelon Corp
    'BKR',    # Baker Hughes
    'FANG',   # Diamondback Energy
    'LIN',    # Linde plc
    # ─── Financial Services ──────────────────────
    'ADP',    # Automatic Data Processing
    'PAYX',   # Paychex Inc
    'VRSK',   # Verisk Analytics
    'ROP',    # Roper Technologies
    'CTSH',   # Cognizant Technology
    'MAR',    # Marriott International
    'CSGP',   # CoStar Group
    # ─── Other ───────────────────────────────────
    'SHOP',   # Shopify Inc
    'PDD',    # PDD Holdings
    'MELI',   # MercadoLibre Inc
    'WDC',    # Western Digital
    'STX',    # Seagate Technology
    'FER',    # Ferrovial SE
    'TRI',    # Thomson Reuters
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

