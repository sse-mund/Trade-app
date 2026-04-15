"""
Backtester — Walk-forward simulation engine.

Strategy:
  - Long-only: enter on BUY signal, exit on SELL signal.
  - No fixed hold period — hold until the model says SELL.
  - Signals are computed day-by-day using vectorised pre-computed indicators
    (RSI, SMA, Bollinger, Volume) to avoid look-ahead bias after the warm-up.
  - Warm-up window: first 60 trading days (needed for SMA50 to stabilise).
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Indicator computation (vectorised — run once on full history)
# ──────────────────────────────────────────────────────────────────────────────

def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with all technical indicators appended."""
    d = df.copy()

    # RSI (14)
    delta = d["Close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    d["RSI"] = 100 - (100 / (1 + rs))

    # SMAs
    d["SMA_20"] = d["Close"].rolling(20).mean()
    d["SMA_50"] = d["Close"].rolling(50).mean()

    # Bollinger Band width
    std20 = d["Close"].rolling(20).std()
    bb_upper = d["SMA_20"] + 2 * std20
    bb_lower = d["SMA_20"] - 2 * std20
    d["BB_width"] = (bb_upper - bb_lower) / d["SMA_20"].replace(0, np.nan)
    d["BB_width_ma"] = d["BB_width"].rolling(20).mean()

    # Volume relative strength
    d["Volume_MA"] = d["Volume"].rolling(20).mean()
    d["Rel_Volume"] = d["Volume"] / d["Volume_MA"].replace(0, np.nan)

    # MACD
    ema12 = d["Close"].ewm(span=12, adjust=False).mean()
    ema26 = d["Close"].ewm(span=26, adjust=False).mean()
    d["MACD"] = ema12 - ema26
    d["MACD_signal"] = d["MACD"].ewm(span=9, adjust=False).mean()
    d["MACD_hist"] = d["MACD"] - d["MACD_signal"]

    return d


# ──────────────────────────────────────────────────────────────────────────────
# Per-bar signal logic
# ──────────────────────────────────────────────────────────────────────────────

def _signal_at(row: pd.Series, params: Dict[str, Any]) -> tuple[str, float, float, float]:
    """
    Compute BUY/SELL/HOLD for a single bar using pre-computed indicators.

    Returns: (signal, combined_score, pattern_raw, quant_raw)
    """
    pw = params.get("pattern_weight", 0.5)
    qw = params.get("quant_weight", 0.5)
    rsi_lo = params.get("rsi_oversold", 30)
    rsi_hi = params.get("rsi_overbought", 70)
    threshold = params.get("signal_threshold", 0.15)

    # ── Pattern signal (trend based on SMA50) ─────────────────────────────
    pattern_signal = 0.0
    pattern_conf = 0.5
    if not pd.isna(row.get("SMA_50")):
        if row["Close"] > row["SMA_50"] * 1.02:
            pattern_signal = 0.5   # uptrend
        elif row["Close"] < row["SMA_50"] * 0.98:
            pattern_signal = -0.5  # downtrend

    # Breakout boost: if price just crossed SMA50 (SMA_50 used as proxy)
    if not pd.isna(row.get("MACD_hist")):
        if row["MACD_hist"] > 0 and pattern_signal >= 0:
            pattern_signal += 0.2
        elif row["MACD_hist"] < 0 and pattern_signal <= 0:
            pattern_signal -= 0.2

    # ── Quant signal (RSI + volume) ────────────────────────────────────────
    quant_signal = 0.0
    if not pd.isna(row.get("RSI")):
        if row["RSI"] < rsi_lo:
            quant_signal += 0.8   # oversold → bullish
        elif row["RSI"] > rsi_hi:
            quant_signal -= 0.8   # overbought → bearish

    # Volume confirmation
    rel_vol = row.get("Rel_Volume", 1.0)
    if not pd.isna(rel_vol) and rel_vol > 1.5:
        price_change = row["Close"] - row.get("Open", row["Close"])
        if price_change > 0:
            quant_signal += 0.25
        elif price_change < 0:
            quant_signal -= 0.25

    quant_conf = min(1.0, abs(quant_signal) * 0.8 + 0.2)

    # ── Combine ────────────────────────────────────────────────────────────
    combined = (pattern_signal * pattern_conf * pw +
                quant_signal  * quant_conf  * qw)

    if combined > threshold:
        return "BUY", combined, pattern_signal, quant_signal
    elif combined < -threshold:
        return "SELL", combined, pattern_signal, quant_signal
    else:
        return "HOLD", combined, pattern_signal, quant_signal


# ──────────────────────────────────────────────────────────────────────────────
# Backtester class
# ──────────────────────────────────────────────────────────────────────────────

WARMUP = 60  # trading days before we start placing trades


class Backtester:
    """
    Walk-forward backtester for the rule-based agent model.

    Usage:
        bt = Backtester(db)
        result = bt.run("NVDA")
    """

    def __init__(self, db):
        self.db = db

    def _load_and_prepare(self, ticker: str) -> pd.DataFrame:
        """Load historical data, compute indicators, strip timezones.
        Returns a DataFrame ready for simulation (warm-up rows already removed).
        """
        df = self.db.get_historical_data(ticker)
        if df.empty or len(df) < WARMUP + 10:
            raise ValueError(f"Not enough historical data for {ticker} (got {len(df)} rows)")

        logger.info(f"Backtester: loaded {len(df)} bars for {ticker}")

        # Compute indicators on full history (vectorised, no look-ahead after warmup)
        df = _compute_indicators(df)
        df = df.iloc[WARMUP:].copy()   # discard warm-up rows

        # Force-strip timezone from every timestamp (handles mixed tz-aware/tz-naive indexes)
        df.index = pd.DatetimeIndex([t.tz_localize(None) if t.tzinfo is not None else t for t in df.index])

        return df

    # ── Public API ─────────────────────────────────────────────────────────

    def run(
        self,
        ticker: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run the full 5-year walk-forward backtest for *ticker*.

        Returns a dict with keys:
            ticker, start_date, end_date, params,
            trade_log (list of trade dicts),
            equity_curve (list of {date, equity}),
            buy_hold_curve (list of {date, value})
        """
        params = params or {}
        logger.info(f"Backtester: starting run for {ticker} with params={params}")

        df = self._load_and_prepare(ticker)

        # Walk-forward simulation
        trade_log, equity_curve = self._simulate(df, params)

        # Build buy-and-hold reference curve
        start_price = df["Close"].iloc[0]
        buy_hold_curve = [
            {"date": str(idx.date()), "value": round(row["Close"] / start_price * 100, 2)}
            for idx, row in df.iterrows()
        ]

        return {
            "ticker": ticker,
            "start_date": str(df.index[0].date()),
            "end_date": str(df.index[-1].date()),
            "params": params,
            "trade_log": trade_log,
            "equity_curve": equity_curve,
            "buy_hold_curve": buy_hold_curve,
            "bar_count": len(df),
        }

    def run_on_range(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run backtest on a specific date range (for train/test splitting).

        Args:
            ticker:     Stock ticker
            start_date: ISO date string (inclusive), e.g. '2021-06-01'
            end_date:   ISO date string (inclusive), e.g. '2024-06-01'
            params:     Model parameter overrides

        Returns: same structure as run()
        """
        params = params or {}

        df = self._load_and_prepare(ticker)

        # Slice to requested range
        df = df.loc[start_date:end_date]
        if len(df) < 20:
            raise ValueError(f"Not enough data for {ticker} in {start_date}–{end_date} (got {len(df)} rows)")

        trade_log, equity_curve = self._simulate(df, params)

        start_price = df["Close"].iloc[0]
        buy_hold_curve = [
            {"date": str(idx.date()), "value": round(row["Close"] / start_price * 100, 2)}
            for idx, row in df.iterrows()
        ]

        return {
            "ticker": ticker,
            "start_date": str(df.index[0].date()),
            "end_date": str(df.index[-1].date()),
            "params": params,
            "trade_log": trade_log,
            "equity_curve": equity_curve,
            "buy_hold_curve": buy_hold_curve,
            "bar_count": len(df),
        }

    # ── Internal simulation loop ───────────────────────────────────────────

    def _simulate(
        self,
        df: pd.DataFrame,
        params: Dict[str, Any],
    ) -> tuple[List[Dict], List[Dict]]:
        """State-machine walk-forward. Returns (trade_log, equity_curve)."""

        trade_log: List[Dict] = []
        equity_curve: List[Dict] = []

        in_trade = False
        entry_date = None      # stored as pd.Timestamp (same tz as index)
        entry_price = None
        entry_pattern = 0.0
        entry_quant = 0.0
        cash = 100.0          # start with $100 notional
        equity = 100.0

        for idx, row in df.iterrows():
            signal, score, pat_raw, qnt_raw = _signal_at(row, params)
            date_str = str(idx.date()) if hasattr(idx, 'date') else str(idx)

            if not in_trade:
                if signal == "BUY":
                    in_trade = True
                    entry_date = idx            # keep as Timestamp
                    entry_price = row["Close"]
                    entry_pattern = pat_raw
                    entry_quant = qnt_raw
            else:  # currently in a trade
                if signal == "SELL":
                    exit_price = row["Close"]
                    pnl_pct = (exit_price - entry_price) / entry_price * 100
                    days_held = (idx - entry_date).days

                    trade_log.append({
                        "entry_date": str(entry_date.date()) if hasattr(entry_date, 'date') else str(entry_date),
                        "exit_date": date_str,
                        "entry_price": round(float(entry_price), 2),
                        "exit_price": round(float(exit_price), 2),
                        "pnl_pct": round(float(pnl_pct), 2),
                        "days_held": days_held,
                        "entry_pattern_signal": round(float(entry_pattern), 3),
                        "entry_quant_signal": round(float(entry_quant), 3),
                        "exit_score": round(float(score), 3),
                    })

                    cash *= (1 + pnl_pct / 100)
                    in_trade = False
                    entry_date = entry_price = None

            equity = cash if not in_trade else cash * (row["Close"] / entry_price if entry_price else 1)
            equity_curve.append({"date": date_str, "equity": round(equity, 2)})

        # Close any open trade at end of data
        if in_trade and entry_price is not None:
            last_row = df.iloc[-1]
            exit_price = last_row["Close"]
            pnl_pct = (exit_price - entry_price) / entry_price * 100
            last_idx = df.index[-1]
            trade_log.append({
                "entry_date": str(entry_date.date()) if hasattr(entry_date, 'date') else str(entry_date),
                "exit_date": str(last_idx.date()) if hasattr(last_idx, 'date') else str(last_idx),
                "entry_price": round(float(entry_price), 2),
                "exit_price": round(float(exit_price), 2),
                "pnl_pct": round(float(pnl_pct), 2),
                "days_held": (last_idx - entry_date).days,
                "entry_pattern_signal": round(float(entry_pattern), 3),
                "entry_quant_signal": round(float(entry_quant), 3),
                "exit_score": 0.0,
                "note": "open_at_end",
            })

        return trade_log, equity_curve

