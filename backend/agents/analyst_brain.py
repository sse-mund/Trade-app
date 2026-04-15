"""
AnalystBrain — Knowledge-Based Expert System for Trading Analysis

Synthesizes outputs from Pattern, Quant, and Sentiment agents into
intelligent, contextual reasoning. Encodes the logic of an experienced
technical analyst: confluence detection, contradiction analysis,
market regime classification, and narrative generation.

No external API calls — pure logic.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# Knowledge Base — Rules encoded as condition→insight mappings
# ────────────────────────────────────────────────────────────────────────────

REGIME_DESCRIPTIONS = {
    "trending_up":   "📈 Trending Up",
    "trending_down":  "📉 Trending Down",
    "ranging":        "📊 Ranging",
    "volatile":       "⚡ Volatile",
    "breakout":       "🚀 Breakout",
    "squeeze":        "🔋 Coiling (Squeeze)",
}

RSI_INSIGHTS = {
    "extreme_oversold": {
        "condition": lambda rsi: rsi is not None and rsi < 20,
        "insight": "RSI at {rsi:.0f} is extremely oversold — a sharp relief bounce is likely, "
                   "but confirm with volume before entering.",
        "bias": 1.0,
    },
    "oversold": {
        "condition": lambda rsi: rsi is not None and 20 <= rsi < 30,
        "insight": "RSI at {rsi:.0f} signals oversold conditions — "
                   "a bounce is probable if support levels hold.",
        "bias": 0.7,
    },
    "approaching_oversold": {
        "condition": lambda rsi: rsi is not None and 30 <= rsi < 40,
        "insight": "RSI at {rsi:.0f} is trending toward oversold territory — "
                   "watch for a potential reversal zone.",
        "bias": 0.3,
    },
    "neutral": {
        "condition": lambda rsi: rsi is not None and 40 <= rsi <= 60,
        "insight": "RSI at {rsi:.0f} is neutral — no strong momentum bias from this indicator.",
        "bias": 0.0,
    },
    "approaching_overbought": {
        "condition": lambda rsi: rsi is not None and 60 < rsi <= 70,
        "insight": "RSI at {rsi:.0f} is approaching overbought — "
                   "momentum is strong but watch for exhaustion.",
        "bias": -0.3,
    },
    "overbought": {
        "condition": lambda rsi: rsi is not None and 70 < rsi <= 80,
        "insight": "RSI at {rsi:.0f} is overbought — upside may be limited. "
                   "Consider tightening stops or taking partial profits.",
        "bias": -0.7,
    },
    "extreme_overbought": {
        "condition": lambda rsi: rsi is not None and rsi > 80,
        "insight": "RSI at {rsi:.0f} is extremely overbought — a pullback is highly likely. "
                   "Aggressive buyers should wait for a reset.",
        "bias": -1.0,
    },
}

VOLUME_INSIGHTS = {
    "surge": {
        "condition": lambda rv: rv is not None and rv > 2.0,
        "insight": "Volume at {rv:.1f}x the 20-day average is a significant surge — "
                   "this move has institutional participation and conviction.",
    },
    "elevated": {
        "condition": lambda rv: rv is not None and 1.5 < rv <= 2.0,
        "insight": "Volume at {rv:.1f}x above average confirms increased market interest.",
    },
    "normal": {
        "condition": lambda rv: rv is not None and 0.8 <= rv <= 1.5,
        "insight": "Volume is within normal range ({rv:.1f}x average) — "
                   "no unusual participation detected.",
    },
    "low": {
        "condition": lambda rv: rv is not None and rv < 0.8,
        "insight": "Volume at {rv:.1f}x average is below normal — "
                   "the current price action lacks conviction and may reverse.",
    },
}

ICHIMOKU_INSIGHTS = {
    "bullish_above_cloud": {
        "condition": lambda ichi: ichi.get("ichimoku_trend") == "bullish",
        "insight": "Ichimoku: Price is above the Kumo cloud — confirming bullish trend. "
                   "Cloud top at ${cloud_support} acts as dynamic support.",
    },
    "bearish_below_cloud": {
        "condition": lambda ichi: ichi.get("ichimoku_trend") == "bearish",
        "insight": "Ichimoku: Price is below the Kumo cloud — confirming bearish trend. "
                   "Cloud bottom at ${cloud_resistance} acts as dynamic resistance.",
    },
    "inside_cloud": {
        "condition": lambda ichi: ichi.get("ichimoku_trend") == "neutral" and ichi.get("ichimoku_cloud_support") is not None,
        "insight": "Ichimoku: Price is inside the Kumo cloud — trend is indeterminate. "
                   "Wait for a clear breakout above or below the cloud before taking directional positions.",
    },
    "bullish_tk_cross": {
        "condition": lambda ichi: ichi.get("ichimoku_momentum") == "strong" and ichi.get("ichimoku_trend") == "bullish",
        "insight": "Ichimoku TK Cross: Tenkan-sen above Kijun-sen with price above cloud — "
                   "strong bullish momentum confirmed.",
    },
    "bearish_tk_cross": {
        "condition": lambda ichi: ichi.get("ichimoku_momentum") == "weak" and ichi.get("ichimoku_trend") == "bearish",
        "insight": "Ichimoku TK Cross: Tenkan-sen below Kijun-sen with price below cloud — "
                   "strong bearish momentum confirmed.",
    },
}

CONTRADICTION_RULES = [
    {
        "name": "bull_trap_risk",
        "condition": lambda p, q, s: (
            p.get("signal", 0) > 0 and s.get("signal", 0) < 0
        ),
        "insight": "⚠️ Possible bull trap: price patterns look bullish, "
                   "but news sentiment is negative. The breakout may fail.",
        "risk": "Bull trap — bearish sentiment conflicts with bullish technical setup",
    },
    {
        "name": "bear_trap_risk",
        "condition": lambda p, q, s: (
            p.get("signal", 0) < 0 and s.get("signal", 0) > 0
        ),
        "insight": "⚠️ Possible bear trap: price patterns look bearish, "
                   "but sentiment is positive. Downturn may be short-lived.",
        "risk": "Bear trap — bullish sentiment conflicts with bearish technical setup",
    },
    {
        "name": "divergence_momentum_trend",
        "condition": lambda p, q, s: (
            p.get("metrics", {}).get("trend") == "uptrend"
            and q.get("signal", 0) < 0
        ),
        "insight": "⚠️ Momentum divergence: the trend is up, but momentum indicators "
                   "(RSI/MACD) are weakening. This often precedes a reversal.",
        "risk": "Momentum diverging from trend — potential trend exhaustion",
    },
    {
        "name": "divergence_momentum_trend_bearish",
        "condition": lambda p, q, s: (
            p.get("metrics", {}).get("trend") == "downtrend"
            and q.get("signal", 0) > 0
        ),
        "insight": "📍 Positive momentum divergence: the trend is down, but momentum "
                   "is turning up. This can signal a bottoming pattern.",
        "risk": "Potential trend reversal forming — watch for confirmation",
    },
    {
        "name": "low_volume_breakout",
        "condition": lambda p, q, s: (
            p.get("metrics", {}).get("breakout", {}).get("type", "none") != "none"
            and q.get("metrics", {}).get("relative_volume", 1.0) < 1.0
        ),
        "insight": "⚠️ Low-conviction breakout: price broke a key level but volume is "
                   "below average. Breakouts without volume often fail.",
        "risk": "Breakout on low volume — high failure probability",
    },
    {
        "name": "squeeze_with_catalyst",
        "condition": lambda p, q, s: (
            q.get("metrics", {}).get("is_squeezing", False)
            and abs(s.get("signal", 0)) > 0
        ),
        "insight": "🔋 Volatility squeeze + sentiment catalyst: Bollinger Bands are compressed "
                   "and news sentiment is active. An explosive move may be imminent.",
        "risk": "Squeeze breakout direction uncertain — size positions carefully",
    },
]


class AnalystBrain:
    """
    Expert system that synthesizes Pattern, Quant, and Sentiment agent
    outputs into intelligent, contextual market analysis.
    """

    def synthesize(
        self,
        ticker: str,
        agent_results: Dict[str, Dict[str, Any]],
        current_price: Optional[float] = None,
        news_articles: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point. Takes all agent results and produces a
        unified analysis with rich reasoning.

        Returns:
            Dict with: recommendation, confidence, brain_reasoning,
            risk_factors, market_regime, key_insight, signal
        """
        pattern = agent_results.get("pattern", {})
        quant = agent_results.get("quant", {})
        sentiment = agent_results.get("sentiment", {})

        # 1. Classify market regime
        regime = self._classify_regime(pattern, quant)

        # 2. Detect confluence (how many agents agree)
        confluence = self._detect_confluence(pattern, quant, sentiment)

        # 3. Detect contradictions
        contradictions = self._detect_contradictions(pattern, quant, sentiment)

        # 4. Generate metric-specific insights
        metric_insights = self._generate_metric_insights(quant)

        # 5. Compute dynamic signal (regime-aware weighting)
        signal, confidence = self._compute_signal(
            pattern, quant, sentiment, regime, confluence
        )

        # 6. Determine recommendation
        recommendation = self._signal_to_recommendation(signal)

        # 7. Assess risk
        risk_factors = self._assess_risk(
            pattern, quant, sentiment, regime, contradictions, confidence
        )

        # 8. Determine risk level
        risk_level = self._compute_risk_level(risk_factors, confidence, contradictions)

        # 9. Generate key insight (the single most important takeaway)
        key_insight = self._generate_key_insight(
            ticker, recommendation, regime, confluence, contradictions, current_price
        )

        # 10. Compute trade parameters (target, stop loss, duration)
        target_price, stop_loss, time_horizon, trade_reasoning = self._compute_trade_params(
            recommendation, regime, pattern, current_price
        )

        # 11. Generate full narrative
        brain_reasoning = self._generate_narrative(
            ticker, recommendation, confidence, regime, confluence,
            contradictions, metric_insights, risk_factors, current_price
        )

        return {
            "recommendation": recommendation,
            "confidence": round(confidence, 2),
            "signal": round(signal, 4),
            "target_price": target_price,
            "stop_loss": stop_loss,
            "time_horizon": time_horizon,
            "trade_reasoning": trade_reasoning,
            "brain_reasoning": brain_reasoning,
            "risk_factors": risk_factors,
            "risk_level": risk_level,
            "market_regime": REGIME_DESCRIPTIONS.get(regime, regime),
            "key_insight": key_insight,
            "confluence": confluence,
        }

    # ─── Trade Parameter Computation ─────────────────────────────────────

    def _compute_trade_params(
        self, recommendation: str, regime: str,
        pattern: Dict, current_price: Optional[float],
    ) -> tuple:
        """
        Compute target_price, stop_loss, time_horizon, and trade_reasoning
        from support/resistance levels and market regime.
        Every price is justified by a specific data point.
        """
        if not current_price:
            return None, None, "", ""

        metrics = pattern.get("metrics", {})
        support = metrics.get("support_levels", [])
        resistance = metrics.get("resistance_levels", [])

        target_price = None
        stop_loss = None
        reasoning_parts = []

        if recommendation == "BUY":
            # Target: nearest resistance above current price
            above = [r for r in resistance if r > current_price]
            if above:
                target_price = round(above[0], 2)
                reasoning_parts.append(
                    f"Target ${target_price} is the nearest resistance level above "
                    f"the current price of ${current_price:.2f}."
                )
            else:
                target_price = round(current_price * 1.05, 2)
                reasoning_parts.append(
                    f"No resistance level found above ${current_price:.2f}; "
                    f"using conservative 5% upside target at ${target_price}."
                )

            # Stop loss: nearest support below, with 2% buffer
            below = [s for s in support if s < current_price]
            if below:
                raw_support = below[-1]
                stop_loss = round(raw_support * 0.98, 2)
                reasoning_parts.append(
                    f"Stop loss ${stop_loss} is 2% below the nearest support "
                    f"at ${raw_support:.2f}."
                )
            else:
                stop_loss = round(current_price * 0.95, 2)
                reasoning_parts.append(
                    f"No support level found below ${current_price:.2f}; "
                    f"using conservative 5% downside stop at ${stop_loss}."
                )

        elif recommendation == "SELL":
            # Target: nearest support below current price
            below = [s for s in support if s < current_price]
            if below:
                target_price = round(below[-1], 2)
                reasoning_parts.append(
                    f"Target ${target_price} is the nearest support level below "
                    f"the current price of ${current_price:.2f}."
                )
            else:
                target_price = round(current_price * 0.95, 2)
                reasoning_parts.append(
                    f"No support level found below ${current_price:.2f}; "
                    f"using conservative 5% downside target at ${target_price}."
                )

            # Stop loss: nearest resistance above, with 2% buffer
            above = [r for r in resistance if r > current_price]
            if above:
                raw_resistance = above[0]
                stop_loss = round(raw_resistance * 1.02, 2)
                reasoning_parts.append(
                    f"Stop loss ${stop_loss} is 2% above the nearest resistance "
                    f"at ${raw_resistance:.2f}."
                )
            else:
                stop_loss = round(current_price * 1.05, 2)
                reasoning_parts.append(
                    f"No resistance level found above ${current_price:.2f}; "
                    f"using conservative 5% upside stop at ${stop_loss}."
                )

        else:  # HOLD
            target_price = round(current_price, 2)
            stop_loss = round(current_price * 0.97, 2)
            reasoning_parts.append(
                f"HOLD stance — target is current price ${target_price}, "
                f"protective stop at ${stop_loss} (3% below)."
            )

        # Time horizon based on market regime
        regime_horizons = {
            "breakout": "1-3 days",
            "squeeze": "1-2 weeks",
            "volatile": "1-3 days",
            "trending_up": "2-4 weeks",
            "trending_down": "2-4 weeks",
            "ranging": "1-2 weeks",
        }
        time_horizon = regime_horizons.get(regime, "1-2 weeks")
        trade_reasoning = " ".join(reasoning_parts)

        return target_price, stop_loss, time_horizon, trade_reasoning

    # ─── Market Regime Detection ─────────────────────────────────────────

    def _classify_regime(
        self, pattern: Dict, quant: Dict
    ) -> str:
        """Classify the current market environment."""
        trend = pattern.get("metrics", {}).get("trend", "neutral")
        breakout = pattern.get("metrics", {}).get("breakout", {})
        is_squeezing = quant.get("metrics", {}).get("is_squeezing", False)
        bb_width = quant.get("metrics", {}).get("bb_width")
        rel_vol = quant.get("metrics", {}).get("relative_volume", 1.0)
        ichimoku_trend = quant.get("metrics", {}).get("ichimoku_trend", "neutral")

        # Breakout takes priority
        if breakout.get("type", "none") != "none" and rel_vol and rel_vol > 1.3:
            return "breakout"

        # Squeeze — very low volatility, coiling for a move
        if is_squeezing:
            return "squeeze"

        # High volatility
        if bb_width is not None and bb_width > 0.08:
            return "volatile"

        # Trending (enhanced with Ichimoku to break ties)
        if trend == "uptrend" or (trend == "neutral" and ichimoku_trend == "bullish"):
            return "trending_up"
        if trend == "downtrend" or (trend == "neutral" and ichimoku_trend == "bearish"):
            return "trending_down"

        return "ranging"

    # ─── Confluence Detection ────────────────────────────────────────────

    def _detect_confluence(
        self, pattern: Dict, quant: Dict, sentiment: Dict
    ) -> Dict[str, Any]:
        """Detect how many agents agree on direction."""
        signals = {
            "pattern": pattern.get("signal", 0),
            "quant": quant.get("signal", 0),
            "sentiment": sentiment.get("signal", 0),
        }

        bullish = sum(1 for s in signals.values() if s > 0)
        bearish = sum(1 for s in signals.values() if s < 0)
        neutral = sum(1 for s in signals.values() if s == 0)

        if bullish == 3:
            agreement = "strong_bullish"
            description = "All 3 agents are bullish — strong conviction"
        elif bearish == 3:
            agreement = "strong_bearish"
            description = "All 3 agents are bearish — strong conviction"
        elif bullish == 2 and bearish == 0:
            agreement = "moderate_bullish"
            description = "2 of 3 agents lean bullish"
        elif bearish == 2 and bullish == 0:
            agreement = "moderate_bearish"
            description = "2 of 3 agents lean bearish"
        elif bullish > 0 and bearish > 0:
            agreement = "mixed"
            description = "Agents are giving mixed signals — proceed with caution"
        else:
            agreement = "neutral"
            description = "No strong directional bias from agents"

        return {
            "agreement": agreement,
            "description": description,
            "bullish_count": bullish,
            "bearish_count": bearish,
            "neutral_count": neutral,
            "signals": signals,
        }

    # ─── Contradiction Detection ─────────────────────────────────────────

    def _detect_contradictions(
        self, pattern: Dict, quant: Dict, sentiment: Dict
    ) -> List[Dict[str, str]]:
        """Identify conflicting signals between agents."""
        contradictions = []
        for rule in CONTRADICTION_RULES:
            try:
                if rule["condition"](pattern, quant, sentiment):
                    contradictions.append({
                        "name": rule["name"],
                        "insight": rule["insight"],
                        "risk": rule["risk"],
                    })
            except Exception:
                continue
        return contradictions

    # ─── Metric-Specific Insights ────────────────────────────────────────

    def _generate_metric_insights(self, quant: Dict) -> List[str]:
        """Generate human-readable insights from raw metrics."""
        insights = []
        metrics = quant.get("metrics", {})

        # RSI insight
        rsi = metrics.get("rsi")
        if rsi is not None:
            for rule in RSI_INSIGHTS.values():
                if rule["condition"](rsi):
                    insights.append(rule["insight"].format(rsi=rsi))
                    break

        # Volume insight
        rv = metrics.get("relative_volume")
        if rv is not None:
            for rule in VOLUME_INSIGHTS.values():
                if rule["condition"](rv):
                    insights.append(rule["insight"].format(rv=rv))
                    break

        # Squeeze insight
        if metrics.get("is_squeezing"):
            insights.append(
                "Bollinger Bands are compressing — volatility is building. "
                "Expect an explosive move in either direction soon."
            )

        # Ichimoku insights
        ichimoku_data = {
            "ichimoku_trend": metrics.get("ichimoku_trend"),
            "ichimoku_momentum": metrics.get("ichimoku_momentum"),
            "ichimoku_cloud_support": metrics.get("ichimoku_cloud_support"),
            "ichimoku_cloud_resistance": metrics.get("ichimoku_cloud_resistance"),
        }
        for rule in ICHIMOKU_INSIGHTS.values():
            try:
                if rule["condition"](ichimoku_data):
                    insight_text = rule["insight"]
                    # Substitute dynamic values
                    cs = ichimoku_data.get("ichimoku_cloud_support")
                    cr = ichimoku_data.get("ichimoku_cloud_resistance")
                    if cs is not None:
                        insight_text = insight_text.replace("${cloud_support}", f"${cs:.2f}")
                    if cr is not None:
                        insight_text = insight_text.replace("${cloud_resistance}", f"${cr:.2f}")
                    insights.append(insight_text)
                    break  # Only first matching Ichimoku insight
            except Exception:
                continue

        return insights

    # ─── Dynamic Signal Computation ──────────────────────────────────────

    def _compute_signal(
        self,
        pattern: Dict, quant: Dict, sentiment: Dict,
        regime: str, confluence: Dict,
    ) -> Tuple[float, float]:
        """
        Compute a weighted signal based on market regime.
        Different regimes weight agents differently.
        """
        # Regime-adaptive weights
        weights = {
            "trending_up":   {"pattern": 0.35, "quant": 0.40, "sentiment": 0.25},
            "trending_down": {"pattern": 0.35, "quant": 0.40, "sentiment": 0.25},
            "ranging":       {"pattern": 0.30, "quant": 0.30, "sentiment": 0.40},
            "volatile":      {"pattern": 0.25, "quant": 0.45, "sentiment": 0.30},
            "breakout":      {"pattern": 0.50, "quant": 0.30, "sentiment": 0.20},
            "squeeze":       {"pattern": 0.30, "quant": 0.45, "sentiment": 0.25},
        }

        w = weights.get(regime, {"pattern": 0.33, "quant": 0.34, "sentiment": 0.33})

        p_signal = pattern.get("signal", 0) * pattern.get("confidence", 0)
        q_signal = quant.get("signal", 0) * quant.get("confidence", 0)
        s_signal = sentiment.get("signal", 0) * sentiment.get("confidence", 0)

        signal = (
            p_signal * w["pattern"]
            + q_signal * w["quant"]
            + s_signal * w["sentiment"]
        )

        # Confidence: base from weighted agent confidence, boosted by confluence
        base_confidence = (
            pattern.get("confidence", 0) * w["pattern"]
            + quant.get("confidence", 0) * w["quant"]
            + sentiment.get("confidence", 0) * w["sentiment"]
        )

        # Confluence boost/penalty
        agreement = confluence.get("agreement", "neutral")
        if agreement in ("strong_bullish", "strong_bearish"):
            base_confidence = min(1.0, base_confidence * 1.3)
        elif agreement == "mixed":
            base_confidence *= 0.7

        return signal, max(0.0, min(1.0, base_confidence))

    # ─── Signal → Recommendation ─────────────────────────────────────────

    def _signal_to_recommendation(self, signal: float) -> str:
        if signal > 0.15:
            return "BUY"
        elif signal < -0.15:
            return "SELL"
        return "HOLD"

    # ─── Risk Assessment ─────────────────────────────────────────────────

    def _assess_risk(
        self,
        pattern: Dict, quant: Dict, sentiment: Dict,
        regime: str, contradictions: List, confidence: float,
    ) -> List[str]:
        """Identify specific risk factors."""
        risks = []

        # From contradictions
        for c in contradictions:
            risks.append(c["risk"])

        # Low confidence
        if confidence < 0.35:
            risks.append("Low overall confidence — consider smaller position size")

        # Volatile regime
        if regime == "volatile":
            risks.append("High volatility environment — wider stops recommended")

        # Low sentiment article count
        article_count = sentiment.get("metrics", {}).get("article_count", 0)
        if article_count < 3:
            risks.append(
                f"Limited news coverage ({article_count} articles) — "
                "sentiment signal may not be reliable"
            )

        # RSI extremes
        rsi = quant.get("metrics", {}).get("rsi")
        if rsi is not None:
            if rsi > 75:
                risks.append(
                    f"RSI at {rsi:.0f} is overbought — risk of a pullback"
                )
            elif rsi < 25:
                risks.append(
                    f"RSI at {rsi:.0f} is deeply oversold — "
                    "could be catching a falling knife"
                )

        return risks

    # ─── Risk Level Computation ──────────────────────────────────────────

    def _compute_risk_level(
        self, risk_factors: List[str], confidence: float,
        contradictions: List,
    ) -> str:
        risk_score = len(risk_factors) + len(contradictions) * 0.5
        if confidence < 0.3:
            risk_score += 1

        if risk_score >= 3:
            return "High"
        elif risk_score >= 1.5:
            return "Medium"
        return "Low"

    # ─── Key Insight Generation ──────────────────────────────────────────

    def _generate_key_insight(
        self,
        ticker: str, recommendation: str, regime: str,
        confluence: Dict, contradictions: List,
        current_price: Optional[float],
    ) -> str:
        """The single most important takeaway for the trader."""
        agreement = confluence.get("agreement", "neutral")

        # Strong confluence is the top insight
        if agreement == "strong_bullish":
            return (
                f"Strong buy signal — all three analysis agents agree {ticker} "
                f"has bullish conditions across technicals, momentum, and sentiment."
            )
        if agreement == "strong_bearish":
            return (
                f"Strong sell signal — all three analysis agents agree {ticker} "
                f"shows bearish conditions across technicals, momentum, and sentiment."
            )

        # Contradictions are the next most important
        if contradictions:
            return contradictions[0]["insight"]

        # Regime-based fallback
        regime_insights = {
            "breakout": f"{ticker} is breaking out of a key level — "
                        "momentum is building for a significant move.",
            "squeeze": f"{ticker} is coiling in a tight range — "
                       "a large move is building. Direction will be determined by the breakout.",
            "volatile": f"{ticker} is in a high-volatility environment — "
                        "expect large swings. Trade with tighter risk management.",
            "trending_up": f"{ticker} is in a confirmed uptrend — "
                          "look for pullback entries near support levels.",
            "trending_down": f"{ticker} is in a confirmed downtrend — "
                            "rallies may present selling opportunities.",
            "ranging": f"{ticker} is trading sideways in a range — "
                      "wait for a directional breakout before committing.",
        }
        return regime_insights.get(
            regime,
            f"{ticker} shows no dominant pattern — staying neutral is the safest approach."
        )

    # ─── Full Narrative Generation ───────────────────────────────────────

    def _generate_narrative(
        self,
        ticker: str, recommendation: str, confidence: float,
        regime: str, confluence: Dict, contradictions: List,
        metric_insights: List[str], risk_factors: List[str],
        current_price: Optional[float],
    ) -> str:
        """Build a multi-sentence narrative explaining the full analysis."""
        parts = []

        # Opening: regime + price context
        regime_label = REGIME_DESCRIPTIONS.get(regime, regime)
        if current_price:
            parts.append(
                f"{ticker} is currently trading at ${current_price:.2f} "
                f"in a {regime_label.lower().lstrip('📈📉📊⚡🚀🔋 ')} market environment."
            )
        else:
            parts.append(
                f"{ticker} is currently in a "
                f"{regime_label.lower().lstrip('📈📉📊⚡🚀🔋 ')} market environment."
            )

        # Confluence summary
        agreement = confluence.get("agreement", "neutral")
        bc = confluence.get("bullish_count", 0)
        brc = confluence.get("bearish_count", 0)
        if agreement in ("strong_bullish", "strong_bearish"):
            parts.append(confluence["description"] + ".")
        elif agreement == "mixed":
            parts.append(
                f"Agents are divided: {bc} bullish vs {brc} bearish. "
                "Mixed signals warrant a cautious approach."
            )
        elif agreement.startswith("moderate"):
            parts.append(confluence["description"] + ".")

        # Metric insights (top 2, keep it concise)
        for insight in metric_insights[:2]:
            parts.append(insight)

        # Contradiction insights (top 2)
        for c in contradictions[:2]:
            parts.append(c["insight"])

        # Closing: recommendation + confidence
        conf_label = "high" if confidence > 0.65 else "moderate" if confidence > 0.4 else "low"
        parts.append(
            f"Overall, the analysis suggests a {recommendation} stance "
            f"with {conf_label} confidence ({confidence*100:.0f}%)."
        )

        return " ".join(parts)
