from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import time
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Simple in-memory cache manager for API responses.
    
    Features:
    - Time-to-live (TTL) based expiration
    - Automatic cleanup of expired entries
    - Thread-safe operations (for single-process use)
    
    Note: This is an in-memory cache. For production with multiple workers,
    consider Redis or similar distributed cache.
    """
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize cache manager.
        
        Args:
            ttl_seconds: Time to live for cached entries in seconds (default: 300 = 5 minutes)
        """
        self.ttl = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        logger.info(f"CacheManager initialized with TTL={ttl_seconds}s")
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached data if not expired.
        
        Args:
            key: Cache key
        
        Returns:
            Cached data if found and not expired, None otherwise
        """
        if key not in self.cache:
            logger.debug(f"Cache MISS: {key}")
            return None
        
        entry = self.cache[key]
        timestamp = entry.get('timestamp', 0)
        
        # Check if expired
        if time.time() - timestamp > self.ttl:
            logger.debug(f"Cache EXPIRED: {key}")
            del self.cache[key]
            return None
        
        logger.debug(f"Cache HIT: {key}")
        return entry.get('data')
    
    def set(self, key: str, value: Dict[str, Any]) -> None:
        """
        Store data in cache with current timestamp.
        
        Args:
            key: Cache key
            value: Data to cache
        """
        self.cache[key] = {
            'data': value,
            'timestamp': time.time()
        }
        logger.debug(f"Cache SET: {key}")
    
    def delete(self, key: str) -> None:
        """
        Remove entry from cache.
        
        Args:
            key: Cache key to remove
        """
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"Cache DELETE: {key}")
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self.cache.items():
            if current_time - entry.get('timestamp', 0) > self.ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats (size, oldest entry, etc.)
        """
        if not self.cache:
            return {
                'size': 0,
                'oldest_age_seconds': 0,
                'newest_age_seconds': 0
            }
        
        current_time = time.time()
        timestamps = [entry['timestamp'] for entry in self.cache.values()]
        
        return {
            'size': len(self.cache),
            'oldest_age_seconds': current_time - min(timestamps),
            'newest_age_seconds': current_time - max(timestamps)
        }


# Global cache instance for the application
_global_cache = None


def get_cache(ttl_seconds: int = 300) -> CacheManager:
    """
    Get or create global cache instance.
    
    Args:
        ttl_seconds: TTL for cache entries
    
    Returns:
        CacheManager instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheManager(ttl_seconds)
    return _global_cache


if __name__ == "__main__":
    # Test the cache manager
    logging.basicConfig(level=logging.DEBUG)
    
    cache = CacheManager(ttl_seconds=2)  # 2 second TTL for testing
    
    # Test set and get
    cache.set('test_key', {'value': 'test_data'})
    result = cache.get('test_key')
    print(f"Retrieved: {result}")
    
    # Test expiration
    print("Waiting 3 seconds for expiration...")
    time.sleep(3)
    result = cache.get('test_key')
    print(f"After expiration: {result}")
    
    # Test stats
    cache.set('key1', {'data': 1})
    cache.set('key2', {'data': 2})
    stats = cache.get_stats()
    print(f"Cache stats: {stats}")
