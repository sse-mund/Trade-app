"""
Fundamentals Collector — fetches company fundamental data via yfinance
and caches the results in the local SQLite database for 10 days.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import yfinance as yf

from database import StockDatabase

logger = logging.getLogger(__name__)

STALENESS_DAYS = 10


class FundamentalsCollector:
    """
    Retrieves company fundamental data (Revenue, P/E, Debt, Earnings).

    Caching strategy:
    - On each request we first check the local DB.
    - If the record is missing OR older than STALENESS_DAYS, we call yfinance
      and upsert the fresh data.
    - All downstream callers receive a plain dict (JSON-serialisable).
    """

    def __init__(self):
        self.db = StockDatabase()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def get_fundamentals(self, ticker: str) -> Dict:
        """
        Return fundamental data for *ticker*, refreshing from yfinance
        if the cached copy is missing or older than STALENESS_DAYS.
        """
        cached = self.db.get_fundamentals(ticker)

        if cached and not self._is_stale(cached.get('fetched_at')):
            logger.info(f"[Fundamentals] Serving {ticker} from cache (fetched {cached['fetched_at']})")
            cached.pop('fetched_at', None)
            return cached

        logger.info(f"[Fundamentals] Cache miss/stale for {ticker} — fetching from yfinance")
        fresh = self._fetch_from_yfinance(ticker)

        if fresh:
            self.db.upsert_fundamentals(ticker, fresh)
            logger.info(f"[Fundamentals] Stored fresh data for {ticker} in DB")

        return fresh or {}

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_stale(fetched_at_str: Optional[str]) -> bool:
        """Return True if fetched_at is older than STALENESS_DAYS."""
        if not fetched_at_str:
            return True
        try:
            # SQLite stores timestamps as strings like '2026-02-20 12:00:00.123456'
            fetched_at = datetime.fromisoformat(str(fetched_at_str))
            return datetime.now() - fetched_at > timedelta(days=STALENESS_DAYS)
        except Exception:
            return True

    @staticmethod
    def _safe(value, cast=float):
        """Return cast(value) or None if the value is missing/invalid."""
        if value is None:
            return None
        try:
            return cast(value)
        except (TypeError, ValueError):
            return None

    def _fetch_from_yfinance(self, ticker: str) -> Optional[Dict]:
        """Call yfinance and return a normalised fundamentals dict."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info  # single dict with 100+ fields

            # --- Earnings / Calendar ----------------------------------------
            next_earnings_date = None
            try:
                cal = stock.calendar
                if cal is not None and not cal.empty:
                    # calendar is a DataFrame with dates as column labels
                    dates = cal.columns.tolist()
                    if dates:
                        next_earnings_date = str(dates[0].date()) if hasattr(dates[0], 'date') else str(dates[0])
            except Exception:
                pass  # not critical

            data = {
                # Valuation
                'market_cap':    self._safe(info.get('marketCap')),
                'pe_ratio':      self._safe(info.get('trailingPE')),
                'forward_pe':    self._safe(info.get('forwardPE')),
                'price_to_book': self._safe(info.get('priceToBook')),

                # Revenue & Earnings
                'revenue_ttm':   self._safe(info.get('totalRevenue')),
                'gross_profit':  self._safe(info.get('grossProfits')),
                'net_income':    self._safe(info.get('netIncomeToCommon')),
                'eps':           self._safe(info.get('trailingEps')),

                # Debt / Liquidity
                'total_debt':    self._safe(info.get('totalDebt')),
                'debt_to_equity':self._safe(info.get('debtToEquity')),
                'current_ratio': self._safe(info.get('currentRatio')),

                # Profitability
                'free_cash_flow':   self._safe(info.get('freeCashflow')),
                'return_on_equity': self._safe(info.get('returnOnEquity')),

                # Growth
                'earnings_growth': self._safe(info.get('earningsGrowth')),
                'revenue_growth':  self._safe(info.get('revenueGrowth')),

                # Upcoming earnings
                'next_earnings_date': next_earnings_date,
            }

            logger.info(f"[Fundamentals] Fetched {sum(1 for v in data.values() if v is not None)} fields for {ticker}")
            return data

        except Exception as e:
            logger.error(f"[Fundamentals] Error fetching yfinance data for {ticker}: {e}")
            return None
