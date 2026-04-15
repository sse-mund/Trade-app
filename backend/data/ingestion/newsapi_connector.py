"""
News API connector for fetching financial and business news.

News API (newsapi.org) provides access to 150,000+ news sources worldwide.
Free tier: 100 requests/day, business category support.
"""
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import requests

logger = logging.getLogger(__name__)


class NewsAPIConnector:
    """
    Connector for News API (newsapi.org) to fetch financial news.
    
    Features:
    - Company-specific news search by ticker/keyword
    - Business news fetching
    - Rate limiting (100 calls/day on free tier)
    - Standardized output schema
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize News API connector.
        
        Args:
            api_key: News API key. If not provided, reads from NEWSAPI_KEY env variable.
        """
        self.api_key = api_key or os.getenv('NEWSAPI_KEY', '')
        self.base_url = "https://newsapi.org/v2"
        
        if not self.api_key:
            logger.warning("No News API key provided. Set NEWSAPI_KEY environment variable.")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("News API connector initialized")
        
        # Rate limiting: 100 calls/day = conservative 1 call per 15 minutes for 24/7 operation
        # For development/testing, we'll be more lenient
        self.last_call_time = 0
        self.min_call_interval = 1.0  # seconds between calls
    
    def _is_english(self, article: Dict) -> bool:
        """
        Check if an article is in English by inspecting its title and description
        for non-ASCII characters (a reliable proxy for non-Latin-script languages).
        """
        text = (article.get('title') or '') + ' ' + (article.get('description') or '')
        try:
            text.encode('ascii')
            return True
        except UnicodeEncodeError:
            return False

    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limit."""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_call_interval:
            time.sleep(self.min_call_interval - elapsed)
        self.last_call_time = time.time()
    
    def _make_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """
        Make HTTP request to News API.
        
        Args:
            endpoint: API endpoint (e.g., 'everything', 'top-headlines')
            params: Query parameters
            
        Returns:
            JSON response or None if error
        """
        if not self.enabled:
            logger.error("News API connector not enabled (missing API key)")
            return None
        
        try:
            # Add API key to params
            params['apiKey'] = self.api_key
            
            # Rate limiting
            self._wait_for_rate_limit()
            
            # Make request
            url = f"{self.base_url}/{endpoint}"
            logger.info(f"Requesting News API: {endpoint} with params: {params}")
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'ok':
                    return data
                else:
                    logger.error(f"News API error: {data.get('message', 'Unknown error')}")
                    return None
            elif response.status_code == 401:
                logger.error("News API authentication failed. Check your API key.")
                return None
            elif response.status_code == 429:
                logger.warning("News API rate limit exceeded")
                return None
            else:
                logger.error(f"News API request failed: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("News API request timed out")
            return None
        except Exception as e:
            logger.error(f"Error making News API request: {str(e)}")
            return None
    
    def fetch_company_news(
        self, 
        ticker: str, 
        hours_back: int = 24
    ) -> List[Dict]:
        """
        Fetch company-specific news for a ticker.
        
        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            hours_back: How many hours back to fetch news (default: 24)
        
        Returns:
            List of news articles in standardized format:
            [
                {
                    'headline': str,
                    'summary': str,
                    'source': str,
                    'datetime': int,  # Unix timestamp
                    'url': str,
                    'related': str,  # Ticker symbol
                    'sentiment_score': None  # To be filled by sentiment agent
                },
                ...
            ]
        """
        if not self.enabled:
            logger.error("News API connector not enabled")
            return []
        
        try:
            # Calculate date range
            to_date = datetime.now()
            from_date = to_date - timedelta(hours=hours_back)
            
            # Format dates as ISO 8601
            from_str = from_date.strftime('%Y-%m-%dT%H:%M:%S')
            to_str = to_date.strftime('%Y-%m-%dT%H:%M:%S')
            
            logger.info(f"Fetching News API articles for {ticker} from {from_str} to {to_str}")
            
            # Build query - search for ticker symbol and company name variations
            # For better results, we search in business category
            params = {
                'q': ticker,  # Search query
                'from': from_str,
                'to': to_str,
                'language': 'en',
                'sortBy': 'relevancy',
                'pageSize': 10  # Limit results
            }
            
            # Use 'everything' endpoint for keyword search
            data = self._make_request('everything', params)
            
            if not data or 'articles' not in data:
                logger.warning(f"No articles returned for {ticker}")
                return []
            
            articles = data['articles']
            logger.info(f"News API returned {len(articles)} articles for {ticker}")
            
            # Standardize format
            standardized = []
            for article in articles:
                # Parse published date
                published_at = article.get('publishedAt', '')
                try:
                    dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    timestamp = int(dt.timestamp())
                except:
                    timestamp = int(datetime.now().timestamp())
                
                standardized.append({
                    'headline': article.get('title', ''),
                    'summary': article.get('description', '') or article.get('content', ''),
                    'source': article.get('source', {}).get('name', 'News API'),
                    'datetime': timestamp,
                    'url': article.get('url', ''),
                    'related': ticker,
                    'sentiment_score': None  # To be filled later
                })
            
            # Post-fetch English filter (belt-and-suspenders alongside language='en' param)
            standardized = [a for a in standardized if self._is_english(
                next((art for art in articles if art.get('title') == a['headline']), {})
            )]
            logger.info(f"Standardized {len(standardized)} English news articles for {ticker}")
            return standardized
            
        except Exception as e:
            logger.error(f"Error fetching News API articles for {ticker}: {str(e)}")
            return []
    
    def fetch_market_news(self, category: str = 'business') -> List[Dict]:
        """
        Fetch general market/business news.
        
        Args:
            category: News category (default: 'business')
                     Options: business, technology, general
        
        Returns:
            List of news articles in standardized format
        """
        if not self.enabled:
            logger.error("News API connector not enabled")
            return []
        
        try:
            logger.info(f"Fetching News API top headlines for category: {category}")
            
            # Use top-headlines endpoint for general news
            params = {
                'category': category,
                'language': 'en',
                'country': 'us',  # Focus on US business news
                'pageSize': 10
            }
            
            data = self._make_request('top-headlines', params)
            
            if not data or 'articles' not in data:
                logger.warning(f"No headlines returned for category {category}")
                return []
            
            articles = data['articles']
            logger.info(f"News API returned {len(articles)} headlines")
            
            # Standardize format
            standardized = []
            for article in articles:
                # Parse published date
                published_at = article.get('publishedAt', '')
                try:
                    dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    timestamp = int(dt.timestamp())
                except:
                    timestamp = int(datetime.now().timestamp())
                
                standardized.append({
                    'headline': article.get('title', ''),
                    'summary': article.get('description', '') or article.get('content', ''),
                    'source': article.get('source', {}).get('name', 'News API'),
                    'datetime': timestamp,
                    'url': article.get('url', ''),
                    'related': category,
                    'sentiment_score': None
                })
            
            # Post-fetch English filter (belt-and-suspenders alongside language='en' param)
            standardized = [a for a in standardized if self._is_english(
                next((art for art in articles if art.get('title') == a['headline']), {})
            )]
            logger.info(f"Standardized {len(standardized)} English market news articles")
            return standardized
            
        except Exception as e:
            logger.error(f"Error fetching News API headlines: {str(e)}")
            return []


# Convenience function
def get_recent_news(ticker: str, hours: int = 24) -> List[Dict]:
    """
    Quick helper to fetch recent news for a ticker.
    
    Args:
        ticker: Stock ticker symbol
        hours: Hours back to fetch
    
    Returns:
        List of news articles
    """
    connector = NewsAPIConnector()
    return connector.fetch_company_news(ticker, hours)


if __name__ == "__main__":
    # Test the connector
    logging.basicConfig(level=logging.INFO)
    
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    
    connector = NewsAPIConnector()
    if connector.enabled:
        print(f"\n{'='*60}")
        print(f"Testing News API Connector for {ticker}")
        print(f"{'='*60}\n")
        
        news = connector.fetch_company_news(ticker, hours_back=48)
        print(f"\nFetched {len(news)} articles for {ticker}")
        
        if news:
            print(f"\n{'='*60}")
            print("First 3 articles:")
            print(f"{'='*60}\n")
            for i, article in enumerate(news[:3], 1):
                print(f"{i}. {article['headline']}")
                print(f"   Source: {article['source']}")
                print(f"   URL: {article['url']}")
                print(f"   Time: {datetime.fromtimestamp(article['datetime'])}")
                print()
    else:
        print("News API connector not enabled. Set NEWSAPI_KEY environment variable.")
