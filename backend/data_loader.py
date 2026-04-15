import yfinance as yf
import pandas as pd
import logger_config
from database import StockDatabase

logger = logger_config.get_logger(__name__)

# Initialize database connection
db = StockDatabase()

def fetch_stock_data(ticker: str, period: str = "1y", use_cache: bool = True) -> pd.DataFrame:
    """
    Fetches historical stock data for a given ticker.
    First checks local database, then falls back to API if needed.
    
    Args:
        ticker (str): Stock symbol (e.g., 'AAPL').
        period (str): Data period to download (default: '1y').
        use_cache (bool): Whether to use cached data from database (default: True).
    Returns:
        pd.DataFrame: DataFrame containing Open, High, Low, Close, Volume.
    """
    logger.info(f"Fetching stock data for ticker: {ticker}, period: {period}, use_cache: {use_cache}")
    
    # Try to get data from local database first if cache is enabled
    if use_cache:
        try:
            logger.info(f"Checking local database for {ticker}")
            df_cached = db.get_historical_data(ticker)
            
            if not df_cached.empty:
                # Filter by period if needed
                if period:
                    # Convert period to number of days
                    period_days = _period_to_days(period)
                    if period_days:
                        cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=period_days)
                        df_cached = df_cached[df_cached.index >= cutoff_date]
                
                if not df_cached.empty:
                    logger.info(f"Retrieved {len(df_cached)} records from local database for {ticker}")
                    # Rename columns to match expected format
                    df_result = df_cached.rename(columns={
                        'open': 'Open',
                        'high': 'High',
                        'low': 'Low',
                        'close': 'Close',
                        'volume': 'Volume'
                    })
                    return df_result[['Open', 'High', 'Low', 'Close', 'Volume']]
        except Exception as e:
            logger.warning(f"Could not retrieve from database for {ticker}: {str(e)}")
    
    # Fallback to API if cache is disabled or no data found
    logger.info(f"Fetching from yfinance API for {ticker}")
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        
        if df.empty:
            logger.warning(f"No data returned for ticker: {ticker}")
            return pd.DataFrame()
        
        logger.info(f"Successfully fetched {len(df)} records for {ticker}")
        
        # Ensure index is datetime
        df.index = pd.to_datetime(df.index)
        result_df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        logger.info(f"Data range for {ticker}: {df.index[0]} to {df.index[-1]}")
        return result_df
        
    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {str(e)}", exc_info=True)
        return pd.DataFrame()

def _period_to_days(period: str) -> int:
    """Convert period string to number of days."""
    period_map = {
        '1d': 1,
        '5d': 5,
        '1mo': 30,
        '3mo': 90,
        '6mo': 180,
        '1y': 365,
        '2y': 730,
        '5y': 1825,
        '10y': 3650,
        'ytd': 365,
        'max': 36500
    }
    return period_map.get(period, 365)
