from engines.cache_engine import get_cache as local_get, set_cache as local_set, delete_cache as local_delete
from services.redis_service import cache_get, cache_set, cache_delete, invalidate_namespace, redis_available

def get_cache(key, default=None):
    """Retrieves value from Redis first, then local memory."""
    val = cache_get(key)
    if val is not None:
        return val
    return local_get(key, default)

def set_cache(key, value, ttl=60):
    """Sets value in both Redis and local memory."""
    cache_set(key, value, ttl)
    return local_set(key, value, ttl)

def delete_cache(key):
    """Deletes value from both Redis and local memory."""
    cache_delete(key)
    local_delete(key)


def invalidate_prefix(prefix):
    if redis_available():
        invalidate_namespace(prefix)

def cached(key, ttl=60):
    """Decorator for caching function results."""
    from functools import wraps
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            resolved_key = key(*args, **kwargs) if callable(key) else key
            if resolved_key:
                cached_value = get_cache(resolved_key)
                if cached_value is not None:
                    return cached_value
            value = func(*args, **kwargs)
            if resolved_key:
                set_cache(resolved_key, value, ttl=ttl)
            return value
        return wrapper
    return decorator
