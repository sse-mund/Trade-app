"""
Twitter/X connector using Twitter API v2 via Tweepy.

Fetches recent tweets mentioning a stock ticker for sentiment analysis.
Requires TWITTER_BEARER_TOKEN environment variable.
"""
import os
import logging
import time
from typing import List, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    import tweepy
except ImportError:
    logger.warning("tweepy not installed. Run: pip install tweepy")
    tweepy = None


class TwitterConnector:
    """
    Connector for Twitter API v2 to fetch real-time ticker mentions.

    Features:
    - Search recent tweets (last 7 days) mentioning a ticker
    - Filter out retweets and replies for cleaner signal
    - Engagement metrics (likes + retweets)
    - Rate limiting (180 requests per 15-minute window)
    - Standardized output schema matching other connectors
    """

    def __init__(self, bearer_token: Optional[str] = None, enabled: bool = True):
        """
        Initialize Twitter connector.

        Args:
            bearer_token: Twitter API v2 Bearer Token.
                          If not provided, reads from TWITTER_BEARER_TOKEN env variable.
            enabled: Whether the connector is enabled.
        """
        self.enabled = enabled
        self.bearer_token = bearer_token or os.getenv('TWITTER_BEARER_TOKEN', '')

        if not self.enabled:
            logger.info("Twitter integration is DISABLED via configuration.")
            self.client = None
        elif not self.bearer_token:
            logger.info("No Twitter Bearer Token provided. Set TWITTER_BEARER_TOKEN environment variable.")
            self.client = None
        elif tweepy is None:
            logger.error("tweepy package not installed. Run: pip install tweepy")
            self.client = None
        else:
            try:
                self.client = tweepy.Client(bearer_token=self.bearer_token, wait_on_rate_limit=True)
                logger.info("Twitter connector initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Twitter connector: {e}")
                self.client = None

        # Rate limiting: 180 requests per 15 min = 1 per 5 seconds (conservative)
        self.last_call_time = 0
        self.min_call_interval = 5.0  # seconds

    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limit."""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_call_interval:
            time.sleep(self.min_call_interval - elapsed)
        self.last_call_time = time.time()

    def search_ticker(
        self,
        ticker: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Search for recent tweets mentioning a stock ticker.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            limit: Maximum number of tweets to return (default: 10, max: 100)

        Returns:
            List of tweets in standardized format:
            [
                {
                    'headline': str,    # First line of tweet
                    'summary': str,     # Full tweet text
                    'source': str,      # 'Twitter'
                    'datetime': int,    # Unix timestamp
                    'url': str,         # Link to tweet on x.com
                    'related': str,     # Ticker symbol
                    'engagement': int,  # Likes + retweets
                    'sentiment_score': None  # To be filled by sentiment agent
                },
                ...
            ]
        """
        if not self.client:
            logger.info("Twitter client not initialized, skipping Twitter fetch")
            return []

        try:
            self._wait_for_rate_limit()

            # Build query: ticker cashtag OR name, exclude retweets and replies
            query = f"${ticker} -is:retweet -is:reply lang:en"

            # Cap limit to API max per request
            max_results = min(max(limit, 10), 100)

            logger.info(f"Fetching Twitter data for ${ticker} (limit={max_results})")

            response = self.client.search_recent_tweets(
                query=query,
                max_results=max_results,
                tweet_fields=["created_at", "public_metrics", "author_id", "text"],
                expansions=["author_id"],
                user_fields=["username", "name"]
            )

            if not response.data:
                logger.info(f"No tweets found for ${ticker}")
                return []

            # Build author lookup map
            author_map = {}
            if response.includes and "users" in response.includes:
                for user in response.includes["users"]:
                    author_map[user.id] = user.username

            results = []
            for tweet in response.data:
                metrics = tweet.public_metrics or {}
                likes = metrics.get("like_count", 0)
                retweets = metrics.get("retweet_count", 0)
                engagement = likes + retweets

                # Convert created_at to unix timestamp
                if tweet.created_at:
                    ts = int(tweet.created_at.replace(tzinfo=timezone.utc).timestamp())
                else:
                    ts = int(datetime.now(timezone.utc).timestamp())

                # Get author username for URL
                username = author_map.get(tweet.author_id, "unknown")
                tweet_url = f"https://x.com/{username}/status/{tweet.id}"

                # Use first line as headline, full text as summary
                text = tweet.text or ""
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                headline = lines[0] if lines else text[:100]

                results.append({
                    "headline": headline,
                    "summary": text,
                    "source": "Twitter",
                    "datetime": ts,
                    "url": tweet_url,
                    "related": ticker,
                    "engagement": engagement,
                    "sentiment_score": None
                })

            # Sort by engagement (most popular first)
            results.sort(key=lambda x: x["engagement"], reverse=True)

            logger.info(f"Fetched {len(results)} tweets for ${ticker}")
            return results

        except Exception as e:
            logger.error(f"Error fetching Twitter data for {ticker}: {e}")
            return []


# Convenience function (maintains backward compatibility)
def get_twitter_mentions(ticker: str, limit: int = 10) -> List[Dict]:
    """
    Fetch recent Twitter mentions for a ticker using Twitter API v2.

    Args:
        ticker: Stock ticker symbol
        limit: Maximum tweets to fetch

    Returns:
        List of tweets in standardized format
    """
    connector = TwitterConnector()
    return connector.search_ticker(ticker, limit)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    connector = TwitterConnector()
    if connector.client:
        tweets = connector.search_ticker("AAPL", limit=5)
        print(f"\nFetched {len(tweets)} tweets for AAPL")
        if tweets:
            print("\nTop tweet:")
            print(f"Text: {tweets[0]['summary']}")
            print(f"Engagement: {tweets[0]['engagement']}")
            print(f"URL: {tweets[0]['url']}")
    else:
        print("Twitter connector not initialized. Set TWITTER_BEARER_TOKEN environment variable.")
