import logging
from typing import Dict, Any, List, Optional

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False

logger = logging.getLogger(__name__)


class SentimentAgent:
    """
    Analyzes sentiment of news headlines and summaries.

    Signal priority:
    1. Finnhub aggregate /news-sentiment (bullishPercent / bearishPercent)
       — passed in via data['finnhub_sentiment'].  Richer & more reliable
       when the caller has a Finnhub paid plan.
    2. Per-article VADER scoring of data['news_articles'] headlines/summaries
       — used as a fallback when Finnhub aggregate data is unavailable.

    Implements the full agent interface: analyze(ticker, data) so it
    participates as a voting agent in AnalystOrchestrator alongside
    Pattern and Quant.
    """

    def __init__(self):
        if VADER_AVAILABLE:
            self.analyzer = SentimentIntensityAnalyzer()
            logger.info("SentimentAgent: vaderSentiment initialized successfully.")
        else:
            self.analyzer = None
            logger.warning(
                "SentimentAgent: vaderSentiment not available. "
                "Run `pip install vaderSentiment` to enable sentiment analysis."
            )

    # ------------------------------------------------------------------ #
    #  Orchestrator-compatible interface                                   #
    # ------------------------------------------------------------------ #

    def analyze(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregate news sentiment into a trading signal.

        Checks data['finnhub_sentiment'] first (Finnhub aggregate endpoint).
        Falls back to VADER scoring of data['news_articles'] if unavailable.

        Returns the standard agent dict: { signal, confidence, reasoning, metrics }
        """
        # ── Priority 1: Finnhub aggregate sentiment ────────────────────────
        finnhub_sentiment: Optional[Dict] = data.get('finnhub_sentiment')
        if finnhub_sentiment and isinstance(finnhub_sentiment, dict):
            return self._analyze_from_finnhub(ticker, finnhub_sentiment)

        # ── Priority 2: Per-article VADER fallback ─────────────────────────
        return self._analyze_from_articles(ticker, data)

    # ------------------------------------------------------------------ #
    #  Finnhub aggregate path                                             #
    # ------------------------------------------------------------------ #

    def _analyze_from_finnhub(self, ticker: str, fh: Dict[str, Any]) -> Dict[str, Any]:
        """
        Derive a trading signal from Finnhub's aggregate /news-sentiment data.

        fh keys expected:
            bullishPercent, bearishPercent, compound_score,
            articlesInLastWeek, buzz, companyNewsScore, sectorAverageBullish
        """
        bullish  = float(fh.get('bullishPercent',  0.0))
        bearish  = float(fh.get('bearishPercent',  0.0))
        compound = float(fh.get('compound_score',  bullish - bearish))
        articles = int(fh.get('articlesInLastWeek', 0))
        score    = float(fh.get('companyNewsScore',  0.0))
        sector   = float(fh.get('sectorAverageBullish', 0.5))
        buzz     = float(fh.get('buzz', 0.0))

        # Signal: use compound (bullish% - bearish%); thresholds are wider
        # than VADER because these are already curated percentages not raw text.
        if compound > 0.10:
            signal    = 1
            direction = "bullish"
        elif compound < -0.10:
            signal    = -1
            direction = "bearish"
        else:
            signal    = 0
            direction = "neutral"

        # Confidence: scales with |compound| and news volume
        article_factor = min(articles / 20.0, 1.0)  # saturates at 20 articles/week
        confidence     = round(min(abs(compound) * article_factor + 0.25, 1.0), 2)

        vs_sector = "above" if bullish > sector else ("below" if bullish < sector else "at")
        buzz_note = (
            f"News buzz is {buzz:.1f}x the weekly average. "
            if buzz > 1.2 else
            f"News volume is below average (buzz={buzz:.2f}). "
            if buzz < 0.8 else ""
        )

        impact_note = (
            "Positive aggregate sentiment supports upside. "
            if signal > 0 else
            "Negative aggregate sentiment adds downside risk. "
            if signal < 0 else
            "No strong sentiment bias in recent news coverage. "
        )

        reasoning = (
            f"[Finnhub Aggregate] News sentiment is {direction} "
            f"(bullish={bullish:.0%}, bearish={bearish:.0%}, compound={compound:+.4f}) "
            f"across ~{articles} article(s) this week. "
            f"Bullish% is {vs_sector} sector average ({sector:.0%}). "
            f"{buzz_note}{impact_note}"
        )

        logger.info(f"SentimentAgent [{ticker}]: Finnhub aggregate — {direction} (compound={compound:+.4f})")

        return {
            "signal":     signal,
            "confidence": confidence,
            "reasoning":  reasoning,
            "metrics": {
                "source":               "finnhub_aggregate",
                "bullish_percent":      round(bullish, 4),
                "bearish_percent":      round(bearish, 4),
                "compound_score":       round(compound, 4),
                "articles_in_week":     articles,
                "buzz":                 round(buzz, 4),
                "company_news_score":   round(score, 4),
                "sector_avg_bullish":   round(sector, 4),
            },
        }

    # ------------------------------------------------------------------ #
    #  VADER article-level path (fallback)                                #
    # ------------------------------------------------------------------ #

    def _analyze_from_articles(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Original VADER-based per-article scoring (fallback path)."""
        articles: List[Dict] = data.get('news_articles', [])

        if not articles:
            return {
                "signal": 0,
                "confidence": 0.0,
                "reasoning": "No news articles available for sentiment analysis.",
                "metrics": {"source": "vader", "article_count": 0, "avg_sentiment": None},
            }

        if not self.analyzer:
            return {
                "signal": 0,
                "confidence": 0.0,
                "reasoning": "vaderSentiment not installed — sentiment analysis skipped.",
                "metrics": {"source": "vader", "article_count": len(articles), "avg_sentiment": None},
            }

        # Score any articles that don't already have a score
        scored = self.analyze_articles(list(articles))

        scores = [
            a["sentiment_score"]
            for a in scored
            if a.get("sentiment_score") is not None
        ]

        if not scores:
            return {
                "signal": 0,
                "confidence": 0.0,
                "reasoning": "Could not score any articles.",
                "metrics": {"source": "vader", "article_count": len(articles), "avg_sentiment": None},
            }

        avg_score = sum(scores) / len(scores)
        # Confidence scales with |avg| and article count (saturates at 10 articles)
        count_factor = min(len(scores) / 10.0, 1.0)
        confidence   = round(min(abs(avg_score) * count_factor + 0.2, 1.0), 2)

        # Map VADER compound average → discrete signal
        # VADER standard thresholds: >0.05 positive, <-0.05 negative
        if avg_score > 0.05:
            signal    = 1
            direction = "positive"
        elif avg_score < -0.05:
            signal    = -1
            direction = "negative"
        else:
            signal    = 0
            direction = "neutral"

        impact_note = (
            "Positive sentiment suggests favorable market perception, supporting upside."
            if signal > 0
            else "Negative sentiment suggests unfavorable market perception, adding downside risk."
            if signal < 0
            else "No strong sentiment bias detected in recent news."
        )

        reasoning = (
            f"[VADER] News sentiment is {direction} (avg score: {avg_score:+.3f}) "
            f"across {len(scores)} article(s). {impact_note}"
        )

        return {
            "signal":     signal,
            "confidence": confidence,
            "reasoning":  reasoning,
            "metrics": {
                "source":         "vader",
                "article_count":  len(scores),
                "avg_sentiment":  round(avg_score, 4),
                "positive_count": sum(1 for s in scores if s > 0.05),
                "negative_count": sum(1 for s in scores if s < -0.05),
                "neutral_count":  sum(1 for s in scores if -0.05 <= s <= 0.05),
            },
        }

    def get_sentiment(self, text: str) -> Optional[float]:
        """
        Analyze sentiment of a given text.

        Returns:
            Compound sentiment score in [-1.0, 1.0], or None if unavailable.
        """
        if not self.analyzer or not text:
            return None
        scores = self.analyzer.polarity_scores(text)
        return round(scores["compound"], 4)

    def analyze_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich a list of news article dicts with a `sentiment_score` field.
        Skips articles that already have a non-None sentiment_score.
        """
        if not self.analyzer:
            logger.warning("SentimentAgent: Skipping — vaderSentiment not initialized.")
            return articles

        for article in articles:
            if article.get("sentiment_score") is not None:
                continue
            headline = article.get("headline", "")
            summary  = article.get("summary", "")
            text = f"{headline}. {summary}".strip(". ")
            article["sentiment_score"] = self.get_sentiment(text)

        logger.info(f"SentimentAgent: Scored {len(articles)} articles.")
        return articles
