"""
Ichimoku Cloud Calculator

Computes all five Ichimoku Kinko Hyo components and derives
actionable signals for trend direction, momentum, and dynamic support/resistance.

Components:
  - Tenkan-sen (Conversion Line):  (9-period high + 9-period low) / 2
  - Kijun-sen  (Base Line):        (26-period high + 26-period low) / 2
  - Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2, plotted 26 periods ahead
  - Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2, plotted 26 periods ahead
  - Chikou Span  (Lagging Span):    Close price plotted 26 periods behind
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple, List

logger = logging.getLogger(__name__)


def compute_ichimoku(df: pd.DataFrame,
                     tenkan_period: int = 9,
                     kijun_period: int = 26,
                     senkou_b_period: int = 52,
                     displacement: int = 26) -> pd.DataFrame:
    """
    Compute all Ichimoku Cloud components and add them as columns.

    Args:
        df: DataFrame with 'High', 'Low', 'Close' columns.
        tenkan_period: Lookback for Tenkan-sen (default 9).
        kijun_period: Lookback for Kijun-sen (default 26).
        senkou_b_period: Lookback for Senkou Span B (default 52).
        displacement: Forward shift for Senkou spans (default 26).

    Returns:
        DataFrame with new columns:
        Ichimoku_Tenkan, Ichimoku_Kijun,
        Ichimoku_SpanA, Ichimoku_SpanB, Ichimoku_Chikou
    """
    df = df.copy()

    # Tenkan-sen (Conversion Line)
    high_tenkan = df['High'].rolling(window=tenkan_period).max()
    low_tenkan = df['Low'].rolling(window=tenkan_period).min()
    df['Ichimoku_Tenkan'] = (high_tenkan + low_tenkan) / 2

    # Kijun-sen (Base Line)
    high_kijun = df['High'].rolling(window=kijun_period).max()
    low_kijun = df['Low'].rolling(window=kijun_period).min()
    df['Ichimoku_Kijun'] = (high_kijun + low_kijun) / 2

    # Senkou Span A (Leading Span A) — shifted forward
    df['Ichimoku_SpanA'] = ((df['Ichimoku_Tenkan'] + df['Ichimoku_Kijun']) / 2).shift(displacement)

    # Senkou Span B (Leading Span B) — shifted forward
    high_senkou = df['High'].rolling(window=senkou_b_period).max()
    low_senkou = df['Low'].rolling(window=senkou_b_period).min()
    df['Ichimoku_SpanB'] = ((high_senkou + low_senkou) / 2).shift(displacement)

    # Chikou Span (Lagging Span) — shifted backward
    df['Ichimoku_Chikou'] = df['Close'].shift(-displacement)

    return df


def analyze_ichimoku(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute Ichimoku Cloud and derive trading signals.

    Returns a dict with:
        signal: float from -1.0 (strong sell) to 1.0 (strong buy)
        trend: str ('bullish', 'bearish', 'neutral')
        momentum: str ('strong', 'weak', 'neutral')
        cloud_support: float | None (top of cloud when price is above)
        cloud_resistance: float | None (bottom of cloud when price is below)
        metrics: dict of raw indicator values
        reasoning: str (human-readable analysis)
    """
    if len(df) < 52:
        return {
            "signal": 0.0,
            "trend": "neutral",
            "momentum": "neutral",
            "cloud_support": None,
            "cloud_resistance": None,
            "metrics": {},
            "reasoning": "Insufficient data for Ichimoku calculation (need 52+ bars)",
        }

    df = compute_ichimoku(df)

    # Current values (last row)
    close = float(df['Close'].iloc[-1])
    tenkan = df['Ichimoku_Tenkan'].iloc[-1]
    kijun = df['Ichimoku_Kijun'].iloc[-1]
    span_a = df['Ichimoku_SpanA'].iloc[-1]
    span_b = df['Ichimoku_SpanB'].iloc[-1]

    # Handle NaN gracefully
    if any(pd.isna(v) for v in [tenkan, kijun, span_a, span_b]):
        return {
            "signal": 0.0,
            "trend": "neutral",
            "momentum": "neutral",
            "cloud_support": None,
            "cloud_resistance": None,
            "metrics": {},
            "reasoning": "Ichimoku values are NaN — insufficient history",
        }

    tenkan = float(tenkan)
    kijun = float(kijun)
    span_a = float(span_a)
    span_b = float(span_b)

    cloud_top = max(span_a, span_b)
    cloud_bottom = min(span_a, span_b)

    # ─── 1. Trend Direction (Price vs Cloud) ─────────────────────────────

    signal = 0.0
    reasoning_parts = []

    if close > cloud_top:
        trend = "bullish"
        signal += 0.4
        reasoning_parts.append(
            f"Price ${close:.2f} is above the Kumo cloud (top ${cloud_top:.2f}), confirming bullish trend"
        )
    elif close < cloud_bottom:
        trend = "bearish"
        signal -= 0.4
        reasoning_parts.append(
            f"Price ${close:.2f} is below the Kumo cloud (bottom ${cloud_bottom:.2f}), confirming bearish trend"
        )
    else:
        trend = "neutral"
        reasoning_parts.append(
            f"Price ${close:.2f} is inside the Kumo cloud (${cloud_bottom:.2f}–${cloud_top:.2f}), trend is uncertain"
        )

    # ─── 2. Momentum (Tenkan vs Kijun Cross) ─────────────────────────────

    if tenkan > kijun:
        momentum = "strong"
        signal += 0.3
        reasoning_parts.append(
            f"Tenkan-sen (${tenkan:.2f}) > Kijun-sen (${kijun:.2f}) — bullish TK cross"
        )
    elif tenkan < kijun:
        momentum = "weak"
        signal -= 0.3
        reasoning_parts.append(
            f"Tenkan-sen (${tenkan:.2f}) < Kijun-sen (${kijun:.2f}) — bearish TK cross"
        )
    else:
        momentum = "neutral"
        reasoning_parts.append("Tenkan-sen equals Kijun-sen — momentum is flat")

    # ─── 3. Cloud Color (future bias) ────────────────────────────────────

    if span_a > span_b:
        signal += 0.1
        reasoning_parts.append("Cloud is green (Span A > Span B) — future bias is bullish")
    elif span_a < span_b:
        signal -= 0.1
        reasoning_parts.append("Cloud is red (Span A < Span B) — future bias is bearish")

    # ─── 4. Price vs Kijun (key support/resistance) ──────────────────────

    if close > kijun:
        signal += 0.1
        reasoning_parts.append(f"Price above Kijun-sen (${kijun:.2f}) — acts as dynamic support")
    elif close < kijun:
        signal -= 0.1
        reasoning_parts.append(f"Price below Kijun-sen (${kijun:.2f}) — acts as dynamic resistance")

    # ─── 5. Chikou Span confirmation ─────────────────────────────────────
    # Check if Chikou (26 bars ago) was above/below the price at that time
    if len(df) > 52:
        chikou_val = df['Ichimoku_Chikou'].iloc[-27]  # 26 bars back
        price_at_chikou = df['Close'].iloc[-27]
        if not pd.isna(chikou_val) and not pd.isna(price_at_chikou):
            chikou_val = float(chikou_val)
            price_at_chikou = float(price_at_chikou)
            if chikou_val > price_at_chikou:
                signal += 0.1
                reasoning_parts.append("Chikou Span is above past price — bullish confirmation")
            elif chikou_val < price_at_chikou:
                signal -= 0.1
                reasoning_parts.append("Chikou Span is below past price — bearish confirmation")

    # Clamp signal
    signal = max(-1.0, min(1.0, signal))

    # ─── Dynamic Support/Resistance from Cloud ───────────────────────────

    cloud_support = None
    cloud_resistance = None

    if close > cloud_top:
        cloud_support = round(cloud_top, 2)   # Cloud top acts as support
    elif close < cloud_bottom:
        cloud_resistance = round(cloud_bottom, 2)  # Cloud bottom acts as resistance
    else:
        # Inside the cloud — both edges are relevant
        cloud_support = round(cloud_bottom, 2)
        cloud_resistance = round(cloud_top, 2)

    metrics = {
        "tenkan_sen": round(tenkan, 2),
        "kijun_sen": round(kijun, 2),
        "senkou_span_a": round(span_a, 2),
        "senkou_span_b": round(span_b, 2),
        "cloud_top": round(cloud_top, 2),
        "cloud_bottom": round(cloud_bottom, 2),
        "price_vs_cloud": trend,
        "tk_cross": "bullish" if tenkan > kijun else "bearish" if tenkan < kijun else "neutral",
        "cloud_color": "green" if span_a > span_b else "red" if span_a < span_b else "neutral",
    }

    return {
        "signal": round(signal, 4),
        "trend": trend,
        "momentum": momentum,
        "cloud_support": cloud_support,
        "cloud_resistance": cloud_resistance,
        "metrics": metrics,
        "reasoning": "; ".join(reasoning_parts),
    }
