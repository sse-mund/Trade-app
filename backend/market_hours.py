import pandas as pd
from datetime import datetime, time, timedelta
import pytz
import logging

logger = logging.getLogger(__name__)

# Constants
MARKET_TZ = pytz.timezone("America/New_York")
MARKET_CLOSE_HOUR = 16  # 4:00 PM


def get_last_friday(today: datetime.date) -> datetime.date:
    """Return the most recent Friday on or before the given date."""
    weekday = today.weekday()
    if weekday == 5:  # Saturday
        return today - timedelta(days=1)
    elif weekday == 6:  # Sunday
        return today - timedelta(days=2)
    else:
        # Weekday: go back to last Friday
        return today - timedelta(days=(weekday + 3) % 7)


def get_expected_last_trading_date() -> datetime.date:
    """
    Returns the date of the most recent completed market session.
    
    - Weekday after 4 PM ET: today
    - Weekday before 4 PM ET: previous trading day (market still open/hasn't closed)
    - Saturday/Sunday: most recent Friday
    """
    now_et = datetime.now(MARKET_TZ)
    today_et = now_et.date()
    weekday = today_et.weekday()
    
    # Weekend → last Friday
    if weekday >= 5:
        return get_last_friday(today_et)
    
    # Weekday, after 4 PM ET → today's session is complete
    if now_et.hour >= MARKET_CLOSE_HOUR:
        return today_et
    
    # Weekday, before 4 PM ET → last completed session
    if weekday == 0:  # Monday before 4 PM → Friday
        return today_et - timedelta(days=3)
    else:
        return today_et - timedelta(days=1)


def is_data_fresh(last_bar_date: pd.Timestamp) -> bool:
    """
    Determines if historical data needs refreshing.
    
    Rules:
    - Weekday after 4 PM ET:  Fresh if last bar >= today
    - Weekday before 4 PM ET: ALWAYS stale (fetch latest intraday bar)
    - Saturday/Sunday:         Fresh if last bar >= last Friday
    """
    if last_bar_date is None:
        return False
    
    now_et = datetime.now(MARKET_TZ)
    today_et = now_et.date()
    weekday = today_et.weekday()
    last_date = last_bar_date.date()
    
    # Weekend → fresh if we have Friday's data
    if weekday >= 5:
        expected = get_last_friday(today_et)
        is_fresh = last_date >= expected
        logger.info(f"Freshness check (weekend): Last bar={last_date}, Expected={expected} -> Fresh={is_fresh}")
        return is_fresh
    
    # Weekday, after 4 PM → fresh if we have today's data
    if now_et.hour >= MARKET_CLOSE_HOUR:
        is_fresh = last_date >= today_et
        logger.info(f"Freshness check (after close): Last bar={last_date}, Expected={today_et} -> Fresh={is_fresh}")
        return is_fresh
    
    # Weekday, before 4 PM → ALWAYS stale to get latest intraday data
    logger.info(f"Freshness check (market hours): Last bar={last_date} -> Always stale during market hours")
    return False
