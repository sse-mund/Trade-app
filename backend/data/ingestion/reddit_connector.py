import os
from typing import List, Dict, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    import praw
except ImportError:
    logger.warning("praw not installed. Run: pip install praw")
    praw = None


class RedditConnector:
    """
    Connector for Reddit API using PRAW to fetch social sentiment.
    
    Features:
    - Search ticker mentions in finance subreddits
    - Filter by upvotes and recency
    - Standardized output schema
    """
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: str = "TradingStrategyApp/1.0"
    ):
        """
        Initialize Reddit connector using PRAW.
        
        Args:
            client_id: Reddit app client ID
            client_secret: Reddit app client secret
            user_agent: User agent string for API requests
        """
        self.client_id = client_id or os.getenv('REDDIT_CLIENT_ID', '')
        self.client_secret = client_secret or os.getenv('REDDIT_CLIENT_SECRET', '')
        self.user_agent = user_agent
        
        if not self.client_id or not self.client_secret:
            logger.warning("Reddit credentials not provided. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET.")
            self.reddit = None
        elif praw is None:
            logger.error("praw package not installed")
            self.reddit = None
        else:
            try:
                self.reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    user_agent=self.user_agent
                )
                logger.info("Reddit connector initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Reddit connector: {str(e)}")
                self.reddit = None
        
        # Default subreddits to search
        self.default_subreddits = ['stocks', 'wallstreetbets', 'investing', 'options']
    
    def search_ticker_mentions(
        self,
        ticker: str,
        subreddits: Optional[List[str]] = None,
        hours_back: int = 24,
        min_upvotes: int = 10,
        limit: int = 50
    ) -> List[Dict]:
        """
        Search for ticker mentions in specified subreddits.
        
        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            subreddits: List of subreddit names (default: stocks, wallstreetbets, investing, options)
            hours_back: How many hours back to search (default: 24)
            min_upvotes: Minimum upvotes to include (default: 10)
            limit: Maximum number of posts to fetch per subreddit (default: 50)
        
        Returns:
            List of posts/comments in standardized format:
            [
                {
                    'headline': str,  # Post title
                    'summary': str,   # Post text or comment body
                    'source': str,    # Subreddit name
                    'datetime': int,  # Unix timestamp
                    'url': str,       # Reddit post URL
                    'related': str,   # Ticker symbol
                    'upvotes': int,   # Number of upvotes
                    'sentiment_score': None  # To be filled by sentiment agent
                },
                ...
            ]
        """
        if not self.reddit:
            logger.error("Reddit client not initialized")
            return []
        
        subreddits = subreddits or self.default_subreddits
        results = []
        
        try:
            # Calculate cutoff time
            cutoff_time = datetime.now().timestamp() - (hours_back * 3600)
            
            for subreddit_name in subreddits:
                try:
                    subreddit = self.reddit.subreddit(subreddit_name)
                    logger.info(f"Searching r/{subreddit_name} for ${ticker}")
                    
                    # Search for ticker mentions
                    # Search both with $ prefix and without
                    search_queries = [f"${ticker}", ticker]
                    
                    for query in search_queries:
                        for submission in subreddit.search(query, time_filter='day', limit=limit):
                            # Check if post is within time range
                            if submission.created_utc < cutoff_time:
                                continue
                            
                            # Check upvotes
                            if submission.score < min_upvotes:
                                continue
                            
                            # Add post
                            results.append({
                                'headline': submission.title,
                                'summary': submission.selftext[:500] if submission.selftext else '',  # Limit length
                                'source': f'r/{subreddit_name}',
                                'datetime': int(submission.created_utc),
                                'url': f"https://reddit.com{submission.permalink}",
                                'related': ticker,
                                'upvotes': submission.score,
                                'sentiment_score': None
                            })
                    
                except Exception as e:
                    logger.error(f"Error searching r/{subreddit_name}: {str(e)}")
                    continue
            
            # Sort by upvotes (most popular first)
            results.sort(key=lambda x: x['upvotes'], reverse=True)
            
            # Remove duplicates based on URL
            seen_urls = set()
            unique_results = []
            for result in results:
                if result['url'] not in seen_urls:
                    seen_urls.add(result['url'])
                    unique_results.append(result)
            
            logger.info(f"Found {len(unique_results)} Reddit mentions for ${ticker}")
            return unique_results[:25]  # Limit to top 25
            
        except Exception as e:
            logger.error(f"Error searching Reddit for {ticker}: {str(e)}")
            return []
    
    def get_trending_tickers(self, subreddit: str = 'wallstreetbets', limit: int = 10) -> List[str]:
        """
        Get trending ticker mentions from a subreddit.
        
        Args:
            subreddit: Subreddit to search (default: wallstreetbets)
            limit: Number of hot posts to analyze
        
        Returns:
            List of ticker symbols mentioned most frequently
        """
        if not self.reddit:
            logger.error("Reddit client not initialized")
            return []
        
        try:
            sub = self.reddit.subreddit(subreddit)
            tickers = {}
            
            # Analyze hot posts
            for submission in sub.hot(limit=limit):
                # Simple ticker extraction (words with $ prefix or all caps 2-5 letters)
                text = f"{submission.title} {submission.selftext}"
                words = text.split()
                
                for word in words:
                    # Check for $ prefix
                    if word.startswith('$') and len(word) > 1:
                        ticker = word[1:].strip('.,!?').upper()
                        if 2 <= len(ticker) <= 5:
                            tickers[ticker] = tickers.get(ticker, 0) + 1
                    # Check for all caps words
                    elif word.isupper() and 2 <= len(word) <= 5:
                        tickers[word] = tickers.get(word, 0) + 1
            
            # Sort by frequency
            sorted_tickers = sorted(tickers.items(), key=lambda x: x[1], reverse=True)
            return [ticker for ticker, count in sorted_tickers[:10]]
            
        except Exception as e:
            logger.error(f"Error getting trending tickers: {str(e)}")
            return []


# Convenience function
def get_reddit_sentiment(ticker: str, hours: int = 24) -> List[Dict]:
    """
    Quick helper to fetch Reddit mentions for a ticker.
    
    Args:
        ticker: Stock ticker symbol
        hours: Hours back to search
    
    Returns:
        List of Reddit posts/comments
    """
    connector = RedditConnector()
    return connector.search_ticker_mentions(ticker, hours_back=hours)


if __name__ == "__main__":
    # Test the connector
    logging.basicConfig(level=logging.INFO)
    
    connector = RedditConnector()
    if connector.reddit:
        mentions = connector.search_ticker_mentions("AAPL", hours_back=24)
        print(f"\nFound {len(mentions)} Reddit mentions for AAPL")
        if mentions:
            print("\nTop mention:")
            print(f"Title: {mentions[0]['headline']}")
            print(f"Subreddit: {mentions[0]['source']}")
            print(f"Upvotes: {mentions[0]['upvotes']}")
            print(f"URL: {mentions[0]['url']}")
    else:
        print("Reddit connector not initialized. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET.")
