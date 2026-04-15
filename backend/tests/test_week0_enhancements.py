"""
Test suite for Week 0 Enhancements:
- Caching logic
- Data Connectors (Finnhub, Reddit, Twitter)
- Multi-chart data structure
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import time

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cache_manager import CacheManager
from data.ingestion.finnhub_connector import FinnhubConnector
from data.ingestion.reddit_connector import RedditConnector
from data.ingestion.twitter_scraper import get_twitter_mentions

# ============================================================================
# CACHE MANAGER TESTS
# ============================================================================

class TestCacheManager:
    """Test the caching mechanism."""
    
    def test_cache_set_get(self):
        """Test basic set and get operations."""
        cache = CacheManager(ttl_seconds=1)
        cache.set("test_key", {"data": "value"})
        
        result = cache.get("test_key")
        assert result == {"data": "value"}
        
    def test_cache_expiration(self):
        """Test that keys expire after TTL."""
        cache = CacheManager(ttl_seconds=1)
        cache.set("expire_key", "value")
        
        # Verify it exists initially
        assert cache.get("expire_key") == "value"
        
        # Wait for expiration (1.1s > 1s)
        time.sleep(1.1)
        
        # Verify it's gone
        assert cache.get("expire_key") is None

    def test_cache_stats(self):
        """Test cache statistics."""
        cache = CacheManager()
        cache.set("key1", "val1")
        cache.set("key2", "val2")
        
        stats = cache.get_stats()
        assert stats["size"] == 2
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        
        cache.get("key1")  # Hit
        cache.get("key3")  # Miss
        
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1


# ============================================================================
# DATA CONNECTOR TESTS
# ============================================================================

class TestDataConnectors:
    """Test data ingestion connectors with mocking."""
    
    @patch('requests.get')
    def test_finnhub_connector(self, mock_get):
        """Test Finnhub connector news fetching."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "headline": "Test News",
                "summary": "Test Summary",
                "source": "CNBC",
                "datetime": 1700000000,
                "url": "http://test.com",
                "related": "AAPL"
            }
        ]
        mock_get.return_value = mock_response
        
        connector = FinnhubConnector(api_key="test_key")
        news = connector.fetch_company_news("AAPL")
        
        assert len(news) == 1
        assert news[0]["headline"] == "Test News"
        assert news[0]["source"] == "CNBC"

    @patch('data.ingestion.finnhub_connector.FinnhubConnector._make_request')
    def test_finnhub_rate_limiting(self, mock_request):
        """Test that rate limiting is respected."""
        mock_request.return_value = []
        connector = FinnhubConnector(api_key="test_key")
        
        start_time = time.time()
        # Make 2 consecutive calls
        connector.fetch_company_news("AAPL")
        connector.fetch_company_news("AAPL")
        duration = time.time() - start_time
        
        # Should take at least 1 second (since rate limit is 1 call/sec)
        # Note: Implementation has sleep(1) in _wait_for_rate_limit
        assert duration >= 1.0

    @patch('praw.Reddit')
    def test_reddit_connector(self, mock_reddit_cls):
        """Test Reddit connector initialization and search."""
        # Mock PRAW Reddit instance
        mock_reddit_instance = MagicMock()
        mock_reddit_cls.return_value = mock_reddit_instance
        
        # Mock subreddit search
        mock_submission = MagicMock()
        mock_submission.title = "Test Post about $AAPL"
        mock_submission.score = 100
        mock_submission.url = "http://reddit.com/post"
        mock_submission.created_utc = 1700000000
        mock_submission.num_comments = 50
        mock_submission.selftext = "Content"
        
        mock_subreddit = MagicMock()
        mock_subreddit.search.return_value = [mock_submission]
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        
        connector = RedditConnector(client_id="id", client_secret="secret")
        mentions = connector.search_ticker_mentions("AAPL")
        
        assert len(mentions) >= 1
        assert mentions[0]["headline"] == "Test Post about $AAPL"
        assert mentions[0]["sentiment_score"] == 0.0  # Default

    @patch('data.ingestion.twitter_scraper.get_twitter_mentions')
    def test_twitter_scraper_mock(self, mock_get_mentions):
        """Test Twitter scraper mock functionality."""
        # Since we use a function, we test the logic directly or mock it
        # The real implementation returns mock data currently
        
        # Test the actual function (it returns mock data)
        tweets = get_twitter_mentions("AAPL")
        
        assert isinstance(tweets, list)
        if len(tweets) > 0:
            assert "headline" in tweets[0]
            assert "source" in tweets[0]
            assert tweets[0]["source"] == "Twitter"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
