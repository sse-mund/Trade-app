
from typing import Dict, Any, List, Tuple
import json
import logging
import os
import pandas as pd
import numpy as np
from .base_agent import BaseAgent
from indicators.ichimoku import analyze_ichimoku

logger = logging.getLogger(__name__)


class PatternAgent(BaseAgent):
    """
    Agent responsible for identifying technical chart patterns.
    Computes metrics (support/resistance, breakouts, trend) then uses
    Ollama LLM to reason about them. Falls back to rule-based logic
    if Ollama is unavailable.

    Key responsibilities:
    - Support & Resistance levels
    - Breakout detection
    - Trend analysis
    - LLM-powered pattern interpretation
    """

    SYSTEM_PROMPT = (
        "You are a technical chart pattern analyst. Given price data metrics, "
        "analyze the chart patterns and respond ONLY with a JSON object (no markdown, no code fences):\n"
        "{\n"
        '  "signal": number from -1.0 (strong sell) to 1.0 (strong buy),\n'
        '  "confidence": number from 0.0 to 1.0,\n'
        '  "reasoning": a 2-3 sentence analysis referencing specific price levels and patterns\n'
        "}\n"
        "Be concise. Reference actual numbers. No text outside the JSON."
    )

    def __init__(self, name: str):
        super().__init__(name)
        self._llm = None
        self._llm_checked = False

    def _get_llm(self):
        """Lazy-load the Ollama LLM. Returns None if unavailable."""
        if self._llm_checked:
            return self._llm
        self._llm_checked = True
        try:
            from langchain_ollama import ChatOllama
            model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
            self._llm = ChatOllama(
                model=model,
                temperature=0.2,
                num_predict=300,
                format="json",
            )
            logger.info(f"PatternAgent: Ollama LLM loaded ({model})")
        except Exception as e:
            logger.warning(f"PatternAgent: Ollama unavailable, using rules: {e}")
            self._llm = None
        return self._llm

    def analyze(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the data for technical patterns.
        Computes metrics first, then uses Ollama for reasoning (with fallback).
        """
        if 'historical_df' not in data or data['historical_df'].empty:
            return {
                "signal": 0,
                "confidence": 0.0,
                "reasoning": "No historical data available for pattern analysis",
                "metrics": {}
            }

        df = data['historical_df']

        # 1. Compute all metrics (always rule-based)
        support, resistance = self._detect_support_resistance(df)
        breakout = self._detect_breakout(df, support, resistance)
        trend = self._detect_trend(df)

        current_price = float(df['Close'].iloc[-1])
        prev_price = float(df['Close'].iloc[-2]) if len(df) > 1 else current_price
        price_change_pct = ((current_price - prev_price) / prev_price * 100) if prev_price else 0

        # 1b. Ichimoku Cloud — dynamic S/R and trend confirmation
        ichimoku_result = analyze_ichimoku(df)
        ichimoku_trend = ichimoku_result.get("trend", "neutral")
        cloud_support = ichimoku_result.get("cloud_support")
        cloud_resistance = ichimoku_result.get("cloud_resistance")

        # Merge Ichimoku cloud levels into support/resistance
        if cloud_support and cloud_support not in support:
            support.append(cloud_support)
            support = sorted(support)
        if cloud_resistance and cloud_resistance not in resistance:
            resistance.append(cloud_resistance)
            resistance = sorted(resistance)

        # Enhance trend with Ichimoku confirmation
        if trend == "neutral" and ichimoku_trend != "neutral":
            trend = f"{ichimoku_trend} (Ichimoku)"
        elif trend in ("uptrend", "downtrend") and ichimoku_trend == trend.replace("uptrend", "bullish").replace("downtrend", "bearish"):
            trend = f"{trend} (confirmed by Ichimoku)"

        metrics = {
            "support_levels": support,
            "resistance_levels": resistance,
            "breakout": breakout,
            "trend": trend,
            "ichimoku_trend": ichimoku_trend,
            "ichimoku_momentum": ichimoku_result.get("momentum", "neutral"),
            "cloud_support": cloud_support,
            "cloud_resistance": cloud_resistance,
        }

        # 2. Try LLM reasoning
        llm_result = self._llm_analyze(
            ticker, current_price, price_change_pct,
            support, resistance, breakout, trend
        )

        if llm_result:
            return {
                "signal": llm_result["signal"],
                "confidence": self._normalize_confidence(llm_result["confidence"]),
                "reasoning": llm_result["reasoning"],
                "metrics": metrics,
            }

        # 3. Fallback: rule-based reasoning
        return self._rule_based_analyze(
            support, resistance, breakout, trend, metrics
        )

    # ─── LLM Reasoning ──────────────────────────────────────────────────

    def _llm_analyze(
        self, ticker: str, current_price: float, price_change_pct: float,
        support: List[float], resistance: List[float],
        breakout: Dict, trend: str,
    ) -> Dict[str, Any] | None:
        """Send metrics to Ollama for pattern reasoning. Returns None on failure."""
        llm = self._get_llm()
        if not llm:
            return None

        breakout_desc = f"at ${breakout['level']:.2f}" if breakout['type'] != 'none' else ''
        prompt = (
            f"Stock: {ticker} at ${current_price:.2f} "
            f"(today's change: {price_change_pct:+.2f}%)\n"
            f"Trend: {trend}\n"
            f"Support levels: {support}\n"
            f"Resistance levels: {resistance}\n"
            f"Breakout: {breakout['type']} {breakout_desc}\n"
        )

        try:
            response = llm.invoke([
                ("system", self.SYSTEM_PROMPT),
                ("human", prompt),
            ])

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

            parsed = json.loads(content)

            signal = float(parsed.get("signal", 0))
            signal = max(-1.0, min(1.0, signal))
            confidence = float(parsed.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
            reasoning = str(parsed.get("reasoning", ""))

            if not reasoning:
                return None

            logger.info(f"PatternAgent LLM: signal={signal}, confidence={confidence}")
            return {"signal": signal, "confidence": confidence, "reasoning": reasoning}

        except Exception as e:
            logger.warning(f"PatternAgent LLM failed, using rules: {e}")
            return None

    # ─── Rule-Based Fallback ─────────────────────────────────────────────

    def _rule_based_analyze(
        self, support, resistance, breakout, trend, metrics
    ) -> Dict[str, Any]:
        """Original rule-based pattern analysis (fallback)."""
        signal = 0
        reasoning_parts = []

        if breakout['type'] == 'bullish':
            signal = 1
            reasoning_parts.append(
                f"Bullish breakout detected above resistance ${breakout['level']:.2f}"
            )
        elif breakout['type'] == 'bearish':
            signal = -1
            reasoning_parts.append(
                f"Bearish breakout detected below support ${breakout['level']:.2f}"
            )

        if trend == 'uptrend' and signal >= 0:
            if signal == 0:
                signal = 0.5
                reasoning_parts.append("Uptrend continuation")
            else:
                reasoning_parts.append("confirmed by uptrend")
        elif trend == 'downtrend' and signal <= 0:
            if signal == 0:
                signal = -0.5
                reasoning_parts.append("Downtrend continuation")
            else:
                reasoning_parts.append("confirmed by downtrend")

        confidence = 0.5
        if breakout['type'] != 'none':
            confidence += 0.3
        if (trend == 'uptrend' and signal > 0) or (trend == 'downtrend' and signal < 0):
            confidence += 0.1

        return {
            "signal": signal,
            "confidence": self._normalize_confidence(confidence),
            "reasoning": "; ".join(reasoning_parts) if reasoning_parts else "No significant patterns detected",
            "metrics": metrics,
        }

    # ─── Metric Computation (unchanged) ──────────────────────────────────

    def _detect_support_resistance(self, df: pd.DataFrame, window: int = 20) -> Tuple[List[float], List[float]]:
        """Identify support and resistance levels using local minima/maxima."""
        if len(df) < window * 2:
            return [], []

        recent_df = df.tail(100)
        support_levels = []
        resistance_levels = []

        for i in range(window, len(recent_df) - window):
            if recent_df['Low'].iloc[i] == recent_df['Low'].iloc[i-window:i+window].min():
                support_levels.append(float(recent_df['Low'].iloc[i]))
            if recent_df['High'].iloc[i] == recent_df['High'].iloc[i-window:i+window].max():
                resistance_levels.append(float(recent_df['High'].iloc[i]))

        support_levels = sorted(list(set([round(s, 2) for s in support_levels])))
        resistance_levels = sorted(list(set([round(r, 2) for r in resistance_levels])))

        return support_levels[-3:], resistance_levels[-3:]

    def _detect_breakout(self, df: pd.DataFrame, support: List[float], resistance: List[float]) -> Dict[str, Any]:
        """Detect if the latest price has broken through support or resistance."""
        if not support and not resistance:
            return {"type": "none", "level": 0.0}

        current_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2]

        for r in resistance:
            if prev_price < r and current_price > r:
                return {"type": "bullish", "level": r}

        for s in support:
            if prev_price > s and current_price < s:
                return {"type": "bearish", "level": s}

        return {"type": "none", "level": 0.0}

    def _detect_trend(self, df: pd.DataFrame) -> str:
        """Simple trend detection using 50-day SMA."""
        if len(df) < 50:
            return "neutral"

        sma_50 = df['Close'].rolling(window=50).mean()
        current_price = df['Close'].iloc[-1]
        current_sma = sma_50.iloc[-1]

        if current_price > current_sma * 1.02:
            return "uptrend"
        elif current_price < current_sma * 0.98:
            return "downtrend"
        else:
            return "neutral"
