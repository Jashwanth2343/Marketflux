"""
Redis caching utility for MarketFlux.
Wraps all Redis calls in try/except — if Redis is down, the app works normally.
"""
import redis
import json
import os
import logging

logger = logging.getLogger(__name__)

_redis_client = None
_redis_failed = False

def _get_redis():
    """Lazy-init Redis connection."""
    global _redis_client, _redis_failed
    
    if _redis_failed:
        return None
        
    if _redis_client is None:
        try:
            client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                password=os.getenv("REDIS_PASSWORD") or None,
                db=0,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            # Test connection
            client.ping()
            _redis_client = client
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning(f"Redis unavailable, caching disabled: {e}")
            _redis_failed = True
            _redis_client = None
    return _redis_client


def cache_get(key: str):
    """Get a value from Redis cache. Returns None on miss or error."""
    try:
        client = _get_redis()
        if client is None:
            return None
        val = client.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


def cache_set(key: str, value, ttl: int = 300):
    """Set a value in Redis cache with TTL in seconds. Silently fails on error."""
    try:
        client = _get_redis()
        if client is None:
            return
        client.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def cache_delete(key: str):
    """Delete a key from Redis cache. Silently fails on error."""
    try:
        client = _get_redis()
        if client is None:
            return
        client.delete(key)
    except Exception:
        pass
