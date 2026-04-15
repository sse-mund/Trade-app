"""
Training Data Generator for Fine-Tuning LLM on Stock Patterns.

For each ticker and each trading day, computes technical indicators,
then looks ahead 5 trading days to capture the ACTUAL outcome.
Produces instruction/output pairs in JSONL format for LoRA fine-tuning.

Usage:
    python generate_training_data.py
    python generate_training_data.py --tickers AAPL MSFT --years 3
    python generate_training_data.py --output my_data.jsonl
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf


# ─── Constants ───────────────────────────────────────────────────────────────

LOOKAHEAD_DAYS = 5  # How many trading days ahead to check outcome
MIN_DATA_POINTS = 80  # Minimum days needed for Ichimoku (52+26 lookback)
DEFAULT_YEARS = 5
DEFAULT_OUTPUT = "training_data.jsonl"
TICKERS_FILE = Path(__file__).parent / "tickers.txt"

SYSTEM_PROMPT = (
    "You are an expert stock market analyst. Given technical indicators "
    "for a stock on a specific date, predict the most likely outcome and "
    "provide your analysis as a JSON object with recommendation, confidence, "
    "target_price, stop_loss, time_horizon, risk_level, and reasoning."
)


# ─── Technical Indicator Computation ──────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all technical indicators for a DataFrame of OHLCV data."""
    df = df.copy()

    # Moving Averages
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['SMA_200'] = df['Close'].rolling(200).mean()

    # RSI (14-period)
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # Bollinger Bands
    bb_sma = df['Close'].rolling(20).mean()
    bb_std = df['Close'].rolling(20).std()
    df['BB_Upper'] = bb_sma + 2 * bb_std
    df['BB_Lower'] = bb_sma - 2 * bb_std
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / bb_sma

    # Volume
    df['Volume_MA'] = df['Volume'].rolling(20).mean()
    df['Relative_Volume'] = df['Volume'] / df['Volume_MA']

    # Price position relative to Bollinger Bands
    df['BB_Position'] = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])

    # ── Ichimoku Cloud ───────────────────────────────────────────────────
    # Tenkan-sen (Conversion Line) — 9-period
    high_9 = df['High'].rolling(9).max()
    low_9 = df['Low'].rolling(9).min()
    df['Ichimoku_Tenkan'] = (high_9 + low_9) / 2

    # Kijun-sen (Base Line) — 26-period
    high_26 = df['High'].rolling(26).max()
    low_26 = df['Low'].rolling(26).min()
    df['Ichimoku_Kijun'] = (high_26 + low_26) / 2

    # Senkou Span A (Leading Span A) — shifted forward 26 periods
    df['Ichimoku_SpanA'] = ((df['Ichimoku_Tenkan'] + df['Ichimoku_Kijun']) / 2).shift(26)

    # Senkou Span B (Leading Span B) — 52-period, shifted forward 26
    high_52 = df['High'].rolling(52).max()
    low_52 = df['Low'].rolling(52).min()
    df['Ichimoku_SpanB'] = ((high_52 + low_52) / 2).shift(26)

    return df


def detect_trend(row: pd.Series) -> str:
    """Classify trend from indicator values."""
    price = row['Close']
    sma50 = row.get('SMA_50')
    sma200 = row.get('SMA_200')

    if pd.isna(sma50) or pd.isna(sma200):
        if pd.notna(sma50):
            return "uptrend" if price > sma50 * 1.02 else ("downtrend" if price < sma50 * 0.98 else "neutral")
        return "neutral"

    if price > sma50 > sma200:
        return "uptrend"
    elif price < sma50 < sma200:
        return "downtrend"
    else:
        return "neutral"


def classify_rsi(rsi: float) -> str:
    """Classify RSI into zones."""
    if pd.isna(rsi):
        return "unknown"
    if rsi >= 70:
        return "overbought"
    elif rsi >= 60:
        return "moderately_bullish"
    elif rsi >= 40:
        return "neutral"
    elif rsi >= 30:
        return "moderately_bearish"
    else:
        return "oversold"


def classify_ichimoku(row: pd.Series) -> str:
    """Classify Ichimoku Cloud status into a compact summary string."""
    close = row['Close']
    span_a = row.get('Ichimoku_SpanA')
    span_b = row.get('Ichimoku_SpanB')
    tenkan = row.get('Ichimoku_Tenkan')
    kijun = row.get('Ichimoku_Kijun')

    if any(pd.isna(v) for v in [span_a, span_b, tenkan, kijun]):
        return None  # Not enough data

    cloud_top = max(span_a, span_b)
    cloud_bottom = min(span_a, span_b)

    if close > cloud_top:
        trend = "bullish"
    elif close < cloud_bottom:
        trend = "bearish"
    else:
        trend = "inside cloud"

    if tenkan > kijun:
        tk = "bullish"
    elif tenkan < kijun:
        tk = "bearish"
    else:
        tk = "flat"

    return f"{trend}, TK cross: {tk}"


# ─── Outcome Computation ─────────────────────────────────────────────────────

def compute_outcome(
    df: pd.DataFrame, idx: int, lookahead: int = LOOKAHEAD_DAYS
) -> Optional[Dict]:
    """
    Compute what ACTUALLY happened in the next `lookahead` trading days.
    Returns None if not enough future data.
    """
    if idx + lookahead >= len(df):
        return None

    entry_price = df['Close'].iloc[idx]
    future_slice = df.iloc[idx + 1: idx + lookahead + 1]

    if len(future_slice) < lookahead:
        return None

    exit_price = future_slice['Close'].iloc[-1]
    max_price = future_slice['High'].max()
    min_price = future_slice['Low'].min()

    price_change_pct = (exit_price - entry_price) / entry_price * 100
    max_gain_pct = (max_price - entry_price) / entry_price * 100
    max_loss_pct = (min_price - entry_price) / entry_price * 100

    # Classify outcome
    if price_change_pct > 3:
        recommendation = "BUY"
        confidence = min(0.95, 0.5 + abs(price_change_pct) / 20)
    elif price_change_pct < -3:
        recommendation = "SELL"
        confidence = min(0.95, 0.5 + abs(price_change_pct) / 20)
    elif price_change_pct > 1:
        recommendation = "BUY"
        confidence = 0.4 + abs(price_change_pct) / 20
    elif price_change_pct < -1:
        recommendation = "SELL"
        confidence = 0.4 + abs(price_change_pct) / 20
    else:
        recommendation = "HOLD"
        confidence = 0.5

    # Determine risk level
    volatility = max_gain_pct - max_loss_pct
    if volatility > 10:
        risk_level = "High"
    elif volatility > 5:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return {
        "recommendation": recommendation,
        "confidence": round(confidence, 2),
        "risk_level": risk_level,
        "target_price": round(max_price, 2) if recommendation == "BUY" else round(min_price, 2),
        "stop_loss": round(min_price * 0.98, 2) if recommendation == "BUY" else round(max_price * 1.02, 2),
        "time_horizon": "1-3 days" if volatility > 8 else ("1-2 weeks" if volatility > 4 else "2-4 weeks"),
        "price_change_pct": round(price_change_pct, 2),
        "max_gain_pct": round(max_gain_pct, 2),
        "max_loss_pct": round(max_loss_pct, 2),
        "entry_price": round(entry_price, 2),
        "exit_price": round(exit_price, 2),
    }


# ─── Training Example Generation ─────────────────────────────────────────────

def build_instruction(ticker: str, date: str, row: pd.Series) -> str:
    """Build the instruction (prompt) for one training example."""
    trend = detect_trend(row)
    rsi_zone = classify_rsi(row.get('RSI'))

    parts = [
        f"Analyze {ticker} on {date}.",
        f"Price: ${row['Close']:.2f}",
        f"Trend: {trend}",
    ]

    if pd.notna(row.get('RSI')):
        parts.append(f"RSI: {row['RSI']:.1f} ({rsi_zone})")
    if pd.notna(row.get('MACD')):
        parts.append(f"MACD: {row['MACD']:.4f}")
    if pd.notna(row.get('MACD_Signal')):
        parts.append(f"MACD Signal: {row['MACD_Signal']:.4f}")
    if pd.notna(row.get('SMA_20')):
        parts.append(f"SMA20: ${row['SMA_20']:.2f}")
    if pd.notna(row.get('SMA_50')):
        parts.append(f"SMA50: ${row['SMA_50']:.2f}")
    if pd.notna(row.get('Relative_Volume')):
        parts.append(f"Volume: {row['Relative_Volume']:.2f}x average")
    if pd.notna(row.get('BB_Width')):
        parts.append(f"BB Width: {row['BB_Width']:.4f}")
    if pd.notna(row.get('BB_Position')):
        parts.append(f"BB Position: {row['BB_Position']:.2f}")

    # Ichimoku Cloud summary
    ichimoku_status = classify_ichimoku(row)
    if ichimoku_status:
        parts.append(f"Ichimoku: {ichimoku_status}")
        span_a = row.get('Ichimoku_SpanA')
        span_b = row.get('Ichimoku_SpanB')
        if pd.notna(span_a) and pd.notna(span_b):
            cloud_top = max(span_a, span_b)
            cloud_bot = min(span_a, span_b)
            parts.append(f"Cloud: ${cloud_bot:.2f}-${cloud_top:.2f}")

    return " | ".join(parts)


def build_output(ticker: str, date: str, row: pd.Series, outcome: Dict) -> str:
    """Build the output (response) for one training example, based on actual outcome."""
    trend = detect_trend(row)
    rsi = row.get('RSI', 0)

    # Generate reasoning that explains the outcome using the indicators
    reasoning_parts = []

    if outcome['recommendation'] == 'BUY':
        reasoning_parts.append(
            f"{ticker} at ${outcome['entry_price']} presented a buying opportunity."
        )
    elif outcome['recommendation'] == 'SELL':
        reasoning_parts.append(
            f"{ticker} at ${outcome['entry_price']} showed signs of weakness."
        )
    else:
        reasoning_parts.append(
            f"{ticker} at ${outcome['entry_price']} was in a consolidation phase."
        )

    # RSI context
    if pd.notna(rsi):
        if rsi > 70:
            reasoning_parts.append(f"RSI at {rsi:.0f} was overbought.")
        elif rsi < 30:
            reasoning_parts.append(f"RSI at {rsi:.0f} was oversold, signaling potential reversal.")
        else:
            reasoning_parts.append(f"RSI at {rsi:.0f} was in neutral territory.")

    # Ichimoku context
    ichimoku_status = classify_ichimoku(row)
    if ichimoku_status:
        reasoning_parts.append(f"Ichimoku Cloud indicated {ichimoku_status}.")

    # Outcome
    change = outcome['price_change_pct']
    direction = "rose" if change > 0 else "fell"
    reasoning_parts.append(
        f"Over the next {LOOKAHEAD_DAYS} trading days, the price {direction} "
        f"{abs(change):.1f}% to ${outcome['exit_price']}."
    )

    # Risk context
    if outcome['risk_level'] == 'High':
        reasoning_parts.append(
            f"High volatility was observed with max gain {outcome['max_gain_pct']:.1f}% "
            f"and max drawdown {outcome['max_loss_pct']:.1f}%."
        )

    output_dict = {
        "recommendation": outcome['recommendation'],
        "confidence": outcome['confidence'],
        "target_price": outcome['target_price'],
        "stop_loss": outcome['stop_loss'],
        "time_horizon": outcome['time_horizon'],
        "risk_level": outcome['risk_level'],
        "reasoning": " ".join(reasoning_parts),
    }

    return json.dumps(output_dict)


def generate_examples_for_ticker(
    ticker: str, years: int = DEFAULT_YEARS
) -> List[Dict[str, str]]:
    """Generate all training examples for a single ticker."""
    print(f"  Fetching {ticker}...", end=" ", flush=True)

    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=f"{years}y")
    except Exception as e:
        print(f"ERROR: {e}")
        return []

    if df is None or len(df) < MIN_DATA_POINTS:
        print(f"SKIP (only {len(df) if df is not None else 0} rows)")
        return []

    # Strip timezone
    if df.index.tz is not None:
        df.index = df.index.tz_convert('UTC').tz_localize(None)

    # Compute indicators
    df = compute_indicators(df)

    examples = []
    # Start from row 55 (enough history for SMA50) and stop LOOKAHEAD days before end
    start_idx = max(80, MIN_DATA_POINTS)

    for i in range(start_idx, len(df)):
        outcome = compute_outcome(df, i)
        if outcome is None:
            continue

        row = df.iloc[i]
        date = df.index[i].strftime('%Y-%m-%d')

        instruction = build_instruction(ticker, date, row)
        output = build_output(ticker, date, row, outcome)

        examples.append({
            "instruction": instruction,
            "output": output,
        })

    print(f"{len(examples)} examples")
    return examples


# ─── Main ─────────────────────────────────────────────────────────────────────

def load_tickers(tickers_arg: Optional[List[str]] = None) -> List[str]:
    """Load tickers from argument or from tickers.txt."""
    if tickers_arg:
        return [t.upper() for t in tickers_arg]

    if TICKERS_FILE.exists():
        tickers = [
            line.strip().upper()
            for line in TICKERS_FILE.read_text().splitlines()
            if line.strip() and not line.startswith('#')
        ]
        return tickers

    print(f"ERROR: No tickers provided and {TICKERS_FILE} not found.")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Generate training data for LLM fine-tuning")
    parser.add_argument("--tickers", nargs="+", help="List of tickers (overrides tickers.txt)")
    parser.add_argument("--years", type=int, default=DEFAULT_YEARS, help="Years of history")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT, help="Output JSONL file")
    args = parser.parse_args()

    tickers = load_tickers(args.tickers)
    output_path = Path(__file__).parent / args.output

    print(f"Generating training data for {len(tickers)} tickers ({args.years} years each)")
    print(f"Output: {output_path}\n")

    all_examples = []
    failed = []

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}]", end=" ")
        try:
            examples = generate_examples_for_ticker(ticker, args.years)
            all_examples.extend(examples)
        except Exception as e:
            print(f"  {ticker} FAILED: {e}")
            failed.append(ticker)

        # Rate limiting — be nice to Yahoo Finance
        if i < len(tickers):
            time.sleep(1)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        for example in all_examples:
            line = json.dumps({
                "system": SYSTEM_PROMPT,
                "instruction": example["instruction"],
                "output": example["output"],
            }, ensure_ascii=False)
            f.write(line + "\n")

    file_size_mb = output_path.stat().st_size / (1024 * 1024)

    print(f"\n{'='*60}")
    print(f"Done! Generated {len(all_examples)} training examples")
    print(f"Output: {output_path} ({file_size_mb:.1f} MB)")
    if failed:
        print(f"Failed tickers: {', '.join(failed)}")
    print(f"{'='*60}")
    print(f"\nNext steps:")
    print(f"  1. Upload {args.output} to Google Drive")
    print(f"  2. Open the Colab notebook and run training")


if __name__ == "__main__":
    main()
