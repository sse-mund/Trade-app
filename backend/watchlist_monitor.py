"""
Watchlist Monitor — Trend Reversal & Sentiment Shift Detection

Compares current agent analysis against previous signals to detect
meaningful changes and raise alerts.
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional

from database import StockDatabase
from agents.quant_agent import QuantAgent
from agents.sentiment_agent import SentimentAgent
from agents.pattern_agent import PatternAgent
from agents.analyst_orchestrator import AnalystOrchestrator
from data_collector import DataCollector
from market_hours import is_data_fresh

from config import (
    MONITOR_RSI_OVERSOLD,
    MONITOR_RSI_OVERBOUGHT,
    MONITOR_VOLUME_SPIKE_THRESHOLD,
    MONITOR_SENTIMENT_FLIP_THRESHOLD,
    MONITOR_CONFIDENCE_MIN,
)

logger = logging.getLogger(__name__)


class MonitorScanner:
    """
    Scans a ticker by running agents and comparing current signals
    against a previous baseline to detect trend reversals and sentiment shifts.
    """

    def __init__(self, db: StockDatabase, orchestrator: AnalystOrchestrator,
                 data_collector: DataCollector,
                 finnhub=None, newsapi=None, reddit=None):
        self.db = db
        self.orchestrator = orchestrator
        self.data_collector = data_collector
        self.finnhub = finnhub
        self.newsapi = newsapi
        self.reddit = reddit

    @staticmethod
    def _inject_live_price(df, live_price: float):
        """Append a synthetic bar with the live price if newer than the last bar."""
        import pandas as pd
        from datetime import datetime
        import pytz

        if df.empty:
            return df
        last_close = float(df['Close'].iloc[-1])
        if abs(live_price - last_close) < 0.001:
            return df

        now = datetime.now(pytz.timezone('America/New_York'))
        new_row = pd.DataFrame({
            'Open': [live_price], 'High': [max(live_price, last_close)],
            'Low': [min(live_price, last_close)], 'Close': [live_price],
            'Volume': [0],
        }, index=[pd.Timestamp(now)])
        return pd.concat([df, new_row])

    def scan_ticker(self, ticker: str, previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Scan a single ticker and compare against previous signals.

        Args:
            ticker: Stock symbol
            previous: Dict with previous scan data:
                {recommendation, signal, rsi, sentiment_score, confidence}
                If None, this is treated as a baseline scan (no alerts).

        Returns:
            Dict with:
                alerts: List of alert dicts (may be empty)
                current: Current signal snapshot for storage
                scan_time: Duration in seconds
        """
        start = time.time()
        alerts: List[Dict[str, Any]] = []

        try:
            # 1. Refresh data if stale
            df = self.db.get_historical_data(ticker)
            if not df.empty:
                last_bar = df.index.max()
                if not is_data_fresh(last_bar):
                    logger.info(f"Monitor: refreshing stale data for {ticker}")
                    try:
                        self.data_collector.update_stock_data(ticker, last_bar_date=last_bar.date())
                        df = self.db.get_historical_data(ticker)
                    except Exception as e:
                        logger.warning(f"Monitor: data refresh failed for {ticker}: {e}")
            else:
                try:
                    self.data_collector.update_stock_data(ticker)
                    df = self.db.get_historical_data(ticker)
                except Exception as e:
                    logger.warning(f"Monitor: initial data fetch failed for {ticker}: {e}")

            if df.empty or len(df) < 30:
                return {
                    'alerts': [],
                    'current': {'recommendation': 'N/A', 'signal': 0, 'rsi': None,
                                'sentiment_score': None, 'confidence': 0},
                    'scan_time': time.time() - start,
                }

            # 2. Inject live price if available
            live_price = None
            try:
                if self.finnhub and self.finnhub.client:
                    quote = self.finnhub.get_quote(ticker)
                    if quote and quote.get('price'):
                        live_price = quote['price']
            except Exception:
                pass

            if live_price:
                df = self._inject_live_price(df, live_price)

            current_price = float(df['Close'].iloc[-1])

            # 3. News/Sentiment — DISABLED for monitor scans (saves API quota)
            #    Only pattern + quant analysis runs in the 10-min monitor cycle.
            #    Full sentiment analysis runs via the main /analyze_charts endpoint.
            news_items = []
            finnhub_sent = None

            # 4. Run orchestrator (pattern + quant only, no sentiment data)
            data_payload = {
                'historical_df': df,
                'news_articles': [],
                'finnhub_sentiment': None,
            }
            synthesis = self.orchestrator.analyze(ticker, data_payload)

            # 5. Extract current snapshot
            agent_results = synthesis.get('agent_results', {})
            quant_metrics = agent_results.get('quant', {}).get('metrics', {})
            sentiment_metrics = agent_results.get('sentiment', {}).get('metrics', {})
            pattern_metrics = agent_results.get('pattern', {}).get('metrics', {})

            current_rsi = quant_metrics.get('rsi')
            current_sentiment = sentiment_metrics.get('avg_sentiment') or sentiment_metrics.get('compound_score', 0)
            current_rec = synthesis.get('recommendation', 'HOLD')
            current_signal = synthesis.get('agent_results', {}).get('quant', {}).get('signal', 0)
            current_confidence = synthesis.get('confidence', 0)
            current_buzz = sentiment_metrics.get('buzz', 0)

            current_snapshot = {
                'recommendation': current_rec,
                'signal': current_signal,
                'rsi': current_rsi,
                'sentiment_score': current_sentiment,
                'confidence': current_confidence,
                'current_price': current_price,
                'market_regime': synthesis.get('market_regime', ''),
                'key_insight': synthesis.get('key_insight', ''),
                'target_price': synthesis.get('target_price'),
                'stop_loss': synthesis.get('stop_loss'),
                'risk_level': synthesis.get('risk_level', 'Medium'),
            }

            # 6. Compare against previous signals (if available)
            if previous:
                alerts = self._detect_alerts(
                    ticker, previous, current_snapshot,
                    pattern_metrics, quant_metrics, sentiment_metrics,
                    current_price, current_buzz
                )

            scan_time = time.time() - start
            logger.info(
                f"Monitor scan for {ticker}: {current_rec} "
                f"(confidence={current_confidence:.2f}), "
                f"{len(alerts)} alert(s), {scan_time:.1f}s"
            )

            return {
                'alerts': alerts,
                'current': current_snapshot,
                'scan_time': scan_time,
            }

        except Exception as e:
            logger.error(f"Monitor scan error for {ticker}: {e}", exc_info=True)
            return {
                'alerts': [],
                'current': {'recommendation': 'ERROR', 'signal': 0, 'rsi': None,
                            'sentiment_score': None, 'confidence': 0},
                'scan_time': time.time() - start,
            }

    def _detect_alerts(
        self, ticker: str,
        prev: Dict[str, Any],
        curr: Dict[str, Any],
        pattern_metrics: Dict,
        quant_metrics: Dict,
        sentiment_metrics: Dict,
        current_price: float,
        current_buzz: float,
    ) -> List[Dict[str, Any]]:
        """
        Compare previous vs current signals and generate alerts.
        """
        alerts = []
        prev_rec = prev.get('recommendation', 'HOLD')
        curr_rec = curr.get('recommendation', 'HOLD')
        curr_confidence = curr.get('confidence', 0)

        # ── 1. Recommendation Flip (CRITICAL) ────────────────────────────────
        if prev_rec != curr_rec and curr_confidence >= MONITOR_CONFIDENCE_MIN:
            # Determine severity based on the type of flip
            if (prev_rec == 'BUY' and curr_rec == 'SELL') or \
               (prev_rec == 'SELL' and curr_rec == 'BUY'):
                severity = 'critical'
                msg = f"🔴 TREND REVERSAL: {ticker} flipped from {prev_rec} → {curr_rec} (confidence: {curr_confidence:.0%})"
            else:
                severity = 'warning'
                msg = f"🟡 Signal changed: {ticker} moved from {prev_rec} → {curr_rec} (confidence: {curr_confidence:.0%})"

            alerts.append({
                'alert_type': 'trend_reversal',
                'severity': severity,
                'message': msg,
                'previous_recommendation': prev_rec,
                'current_recommendation': curr_rec,
                'previous_signal': prev.get('signal', 0),
                'current_signal': curr.get('signal', 0),
                'details': {
                    'price': current_price,
                    'confidence': curr_confidence,
                    'market_regime': curr.get('market_regime', ''),
                    'key_insight': curr.get('key_insight', ''),
                },
            })

        # ── 2. RSI Crossings (WARNING) ────────────────────────────────────────
        prev_rsi = prev.get('rsi')
        curr_rsi = curr.get('rsi')
        if prev_rsi is not None and curr_rsi is not None:
            # Crossed INTO oversold territory
            if prev_rsi > MONITOR_RSI_OVERSOLD and curr_rsi <= MONITOR_RSI_OVERSOLD:
                alerts.append({
                    'alert_type': 'rsi_oversold',
                    'severity': 'warning',
                    'message': f"📉 {ticker} RSI entered oversold territory ({curr_rsi:.1f} ← {prev_rsi:.1f})",
                    'previous_recommendation': prev_rec,
                    'current_recommendation': curr_rec,
                    'previous_signal': prev_rsi,
                    'current_signal': curr_rsi,
                    'details': {'rsi_prev': prev_rsi, 'rsi_curr': curr_rsi, 'price': current_price},
                })
            # Crossed INTO overbought territory
            elif prev_rsi < MONITOR_RSI_OVERBOUGHT and curr_rsi >= MONITOR_RSI_OVERBOUGHT:
                alerts.append({
                    'alert_type': 'rsi_overbought',
                    'severity': 'warning',
                    'message': f"📈 {ticker} RSI entered overbought territory ({curr_rsi:.1f} ← {prev_rsi:.1f})",
                    'previous_recommendation': prev_rec,
                    'current_recommendation': curr_rec,
                    'previous_signal': prev_rsi,
                    'current_signal': curr_rsi,
                    'details': {'rsi_prev': prev_rsi, 'rsi_curr': curr_rsi, 'price': current_price},
                })

        # ── 3. Breakout Detection (WARNING/CRITICAL) ─────────────────────────
        breakout = pattern_metrics.get('breakout', {})
        breakout_type = breakout.get('type', 'none')
        if breakout_type != 'none':
            level = breakout.get('level', 0)
            sev = 'critical' if breakout_type == 'bullish' and curr_rec == 'BUY' else \
                  'critical' if breakout_type == 'bearish' and curr_rec == 'SELL' else 'warning'
            direction = 'above resistance' if breakout_type == 'bullish' else 'below support'
            alerts.append({
                'alert_type': 'breakout',
                'severity': sev,
                'message': f"💥 {ticker} breakout {direction} at ${level:.2f} (price: ${current_price:.2f})",
                'previous_recommendation': prev_rec,
                'current_recommendation': curr_rec,
                'previous_signal': prev.get('signal', 0),
                'current_signal': curr.get('signal', 0),
                'details': {
                    'breakout_type': breakout_type,
                    'breakout_level': level,
                    'price': current_price,
                },
            })

        # ── 4. Volume Spike (INFO/WARNING) ────────────────────────────────────
        rel_vol = quant_metrics.get('relative_volume', 1.0)
        if rel_vol >= MONITOR_VOLUME_SPIKE_THRESHOLD:
            sev = 'warning' if rel_vol >= 3.0 else 'info'
            alerts.append({
                'alert_type': 'volume_spike',
                'severity': sev,
                'message': f"📊 {ticker} volume spike: {rel_vol:.1f}x average (price: ${current_price:.2f})",
                'previous_recommendation': prev_rec,
                'current_recommendation': curr_rec,
                'previous_signal': prev.get('signal', 0),
                'current_signal': curr.get('signal', 0),
                'details': {'relative_volume': rel_vol, 'price': current_price},
            })

        # ── 5. Sentiment Flip (WARNING) ───────────────────────────────────────
        prev_sent = prev.get('sentiment_score', 0) or 0
        curr_sent = curr.get('sentiment_score', 0) or 0
        sent_delta = abs(curr_sent - prev_sent)

        if sent_delta >= MONITOR_SENTIMENT_FLIP_THRESHOLD:
            # Check if sign actually flipped
            if (prev_sent > 0 and curr_sent < 0) or (prev_sent < 0 and curr_sent > 0):
                direction = 'negative' if curr_sent < 0 else 'positive'
                alerts.append({
                    'alert_type': 'sentiment_flip',
                    'severity': 'warning',
                    'message': f"📰 {ticker} sentiment flipped to {direction} ({prev_sent:+.3f} → {curr_sent:+.3f})",
                    'previous_recommendation': prev_rec,
                    'current_recommendation': curr_rec,
                    'previous_signal': prev_sent,
                    'current_signal': curr_sent,
                    'details': {
                        'sentiment_prev': prev_sent,
                        'sentiment_curr': curr_sent,
                        'delta': sent_delta,
                        'price': current_price,
                    },
                })

        # ── 6. News Buzz Spike (INFO) ─────────────────────────────────────────
        if current_buzz >= 2.0:
            alerts.append({
                'alert_type': 'buzz_spike',
                'severity': 'info',
                'message': f"🔔 {ticker} news buzz is {current_buzz:.1f}x weekly average",
                'previous_recommendation': prev_rec,
                'current_recommendation': curr_rec,
                'previous_signal': prev.get('signal', 0),
                'current_signal': curr.get('signal', 0),
                'details': {'buzz': current_buzz, 'price': current_price},
            })

        return alerts
