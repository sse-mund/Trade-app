"""
Tests for the Twitter API v2 connector.
"""
import pytest
from unittest.mock import MagicMock, patch
from data.ingestion.twitter_scraper import TwitterConnector, get_twitter_mentions


class TestTwitterConnectorInit:
    """Test connector initialization."""

    def test_no_credentials_disables_client(self):
        """Without credentials, client should be None."""
        with patch.dict("os.environ", {}, clear=True):
            connector = TwitterConnector(bearer_token="")
        assert connector.client is None

    def test_with_credentials_initializes_client(self):
        """With a valid bearer token, client should be initialized."""
        with patch("tweepy.Client") as mock_client:
            mock_client.return_value = MagicMock()
            connector = TwitterConnector(bearer_token="fake_token_for_testing")
        assert connector.client is not None

    def test_explicitly_disabled_sets_client_to_none(self):
        """If enabled=False, client should be None even with credentials."""
        with patch("tweepy.Client") as mock_client:
            mock_client.return_value = MagicMock()
            connector = TwitterConnector(bearer_token="fake_token", enabled=False)
        assert connector.client is None

    def test_tweepy_import_error_handled(self):
        """If tweepy is not installed, should handle gracefully."""
        with patch.dict("sys.modules", {"tweepy": None}):
            # Re-import to trigger the ImportError path
            import importlib
            import data.ingestion.twitter_scraper as ts_module
            importlib.reload(ts_module)
            connector = ts_module.TwitterConnector(bearer_token="fake_token")
            assert connector.client is None


class TestTwitterConnectorSearch:
    """Test tweet searching functionality."""

    def _make_mock_tweet(self, tweet_id, text, likes=10, retweets=5):
        tweet = MagicMock()
        tweet.id = tweet_id
        tweet.text = text
        tweet.author_id = 12345
        tweet.public_metrics = {"like_count": likes, "retweet_count": retweets}
        from datetime import datetime, timezone
        tweet.created_at = datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)
        return tweet

    def test_search_returns_standardized_format(self):
        """Search results should match the standardized schema."""
        mock_tweet = self._make_mock_tweet(111, "$AAPL is looking bullish today!")

        mock_user = MagicMock()
        mock_user.id = 12345
        mock_user.username = "trader_joe"

        mock_response = MagicMock()
        mock_response.data = [mock_tweet]
        mock_response.includes = {"users": [mock_user]}

        with patch("tweepy.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.search_recent_tweets.return_value = mock_response
            mock_client_cls.return_value = mock_client

            connector = TwitterConnector(bearer_token="fake_token")
            results = connector.search_ticker("AAPL", limit=10)

        assert len(results) == 1
        result = results[0]
        assert result["source"] == "Twitter"
        assert result["related"] == "AAPL"
        assert result["engagement"] == 15  # 10 likes + 5 retweets
        assert "x.com" in result["url"]
        assert result["sentiment_score"] is None
        assert "headline" in result
        assert "summary" in result
        assert "datetime" in result

    def test_search_no_results(self):
        """Empty API response should return empty list."""
        mock_response = MagicMock()
        mock_response.data = None

        with patch("tweepy.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.search_recent_tweets.return_value = mock_response
            mock_client_cls.return_value = mock_client

            connector = TwitterConnector(bearer_token="fake_token")
            results = connector.search_ticker("AAPL", limit=10)

        assert results == []

    def test_search_without_client_returns_empty(self):
        """Without initialized client, should return empty list."""
        connector = TwitterConnector(bearer_token="")
        results = connector.search_ticker("AAPL")
        assert results == []

    def test_search_api_error_returns_empty(self):
        """API errors should be caught and return empty list."""
        with patch("tweepy.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.search_recent_tweets.side_effect = Exception("API Error")
            mock_client_cls.return_value = mock_client

            connector = TwitterConnector(bearer_token="fake_token")
            results = connector.search_ticker("AAPL", limit=10)

        assert results == []

    def test_results_sorted_by_engagement(self):
        """Results should be sorted by engagement (highest first)."""
        tweet1 = self._make_mock_tweet(1, "Low engagement tweet", likes=2, retweets=1)
        tweet2 = self._make_mock_tweet(2, "High engagement tweet", likes=100, retweets=50)

        mock_user = MagicMock()
        mock_user.id = 12345
        mock_user.username = "trader"

        mock_response = MagicMock()
        mock_response.data = [tweet1, tweet2]
        mock_response.includes = {"users": [mock_user]}

        with patch("tweepy.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.search_recent_tweets.return_value = mock_response
            mock_client_cls.return_value = mock_client

            connector = TwitterConnector(bearer_token="fake_token")
            results = connector.search_ticker("AAPL", limit=10)

        assert results[0]["engagement"] == 150  # tweet2 first
        assert results[1]["engagement"] == 3    # tweet1 second


class TestGetTwitterMentions:
    """Test the convenience function."""

    def test_get_twitter_mentions_no_credentials(self):
        """Should return empty list without credentials."""
        with patch.dict("os.environ", {}, clear=True):
            result = get_twitter_mentions("AAPL")
        assert isinstance(result, list)
