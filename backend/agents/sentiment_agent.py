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
    Analyzes sentiment of news headlines and summaries using vaderSentiment.

    Now implements the full agent interface — analyze(ticker, data) — so it
    participates as a voting agent in AnalystOrchestrator alongside Pattern and Quant.
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

        Expects data['news_articles'] to be a list of article dicts with
        optional 'sentiment_score', 'headline', and 'summary' fields.

        Returns the standard agent dict: { signal, confidence, reasoning, metrics }
        """
        articles: List[Dict] = data.get('news_articles', [])

        if not articles:
            return {
                "signal": 0,
                "confidence": 0.0,
                "reasoning": "No news articles available for sentiment analysis.",
                "metrics": {"article_count": 0, "avg_sentiment": None},
            }

        if not self.analyzer:
            return {
                "signal": 0,
                "confidence": 0.0,
                "reasoning": "vaderSentiment not installed — sentiment analysis skipped.",
                "metrics": {"article_count": len(articles), "avg_sentiment": None},
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
                "metrics": {"article_count": len(articles), "avg_sentiment": None},
            }

        avg_score = sum(scores) / len(scores)
        # Confidence scales with |avg| and article count (saturates at 10 articles)
        count_factor = min(len(scores) / 10.0, 1.0)
        confidence = round(min(abs(avg_score) * count_factor + 0.2, 1.0), 2)

        # Map VADER compound average → discrete signal
        # VADER standard thresholds: >0.05 positive, <-0.05 negative
        if avg_score > 0.05:
            signal = 1
            direction = "positive"
        elif avg_score < -0.05:
            signal = -1
            direction = "negative"
        else:
            signal = 0
            direction = "neutral"

        impact_note = (
            "Positive sentiment suggests favorable market perception, supporting upside."
            if signal > 0
            else "Negative sentiment suggests unfavorable market perception, adding downside risk."
            if signal < 0
            else "No strong sentiment bias detected in recent news."
        )

        reasoning = (
            f"News sentiment is {direction} (avg score: {avg_score:+.3f}) "
            f"across {len(scores)} article(s). {impact_note}"
        )

        return {
            "signal": signal,
            "confidence": confidence,
            "reasoning": reasoning,
            "metrics": {
                "article_count": len(scores),
                "avg_sentiment": round(avg_score, 4),
                "positive_count": sum(1 for s in scores if s > 0.05),
                "negative_count": sum(1 for s in scores if s < -0.05),
                "neutral_count":  sum(1 for s in scores if -0.05 <= s <= 0.05),
            },
        }

    # ------------------------------------------------------------------ #
    #  Article-level helpers                                               #
    # ------------------------------------------------------------------ #

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
