import pandas as pd
from datetime import datetime, time
import pytz
import logging

logger = logging.getLogger(__name__)

# Constants
MARKET_TZ = pytz.timezone("America/New_York")
MARKET_CLOSE_HOUR = 16  # 4:00 PM

def get_expected_last_trading_date() -> datetime.date:
    """
    Returns the date of the most recent market close.
    
    If it's a weekday and after 4 PM ET, returns today.
    If it's a weekday and before 4 PM ET, returns yesterday's logic.
    If it's a weekend, returns the most recent Friday.
    """
    now_et = datetime.now(MARKET_TZ)
    today_et = now_et.date()
    
    # If today is a weekend
    # 5 = Saturday, 6 = Sunday
    weekday = today_et.weekday()
    
    if weekday == 5: # Saturday
        return today_et - pd.Timedelta(days=1)
    if weekday == 6: # Sunday
        return today_et - pd.Timedelta(days=2)
        
    # It's a weekday. Did the market close yet?
    if now_et.hour < MARKET_CLOSE_HOUR:
        # Before 4 PM ET. 
        # If it's Monday, expected is Friday (3 days ago)
        if weekday == 0:
            return today_et - pd.Timedelta(days=3)
        else:
            return today_et - pd.Timedelta(days=1)
    
    # After 4 PM ET on a weekday - today is the expected last date
    return today_et

def is_data_fresh(last_bar_date: pd.Timestamp) -> bool:
    """
    Compares the last bar in the database to the expected last trading date.
    Returns True if no refresh is needed.
    """
    if last_bar_date is None:
        return False
        
    expected_date = get_expected_last_trading_date()
    last_date = last_bar_date.date()
    
    # If last_date is today or the expected date, we are fresh.
    # Note: Sometimes yfinance gives a partial bar for 'today' if run 
    # slightly before 4PM or during holidays, so >= is safer.
    is_fresh = last_date >= expected_date
    
    logger.info(f"Freshness check: Last bar={last_date}, Expected={expected_date} -> Fresh={is_fresh}")
    return is_fresh
