"""Phase 67 — Production-grade caching layer with safe Redis fallback."""

import os, functools, json, hashlib
from datetime import datetime, timezone

try:
    from services.redis_service import cache_get, cache_set, cache_delete
    REDIS_AVAILABLE = bool(os.getenv('REDIS_URL') or os.getenv('CHAIN_REDIS_URL'))
except Exception:
    REDIS_AVAILABLE = False
    def cache_get(k): return None
    def cache_set(k, v, ttl=300): return None
    def cache_delete(k): return None

_IN_MEMORY_CACHE = {}

def _cache_key(prefix, *args):
    raw = f"{prefix}:" + ":".join(str(a) for a in args)
    if len(raw) > 200:
        return f"{prefix}:" + hashlib.md5(raw.encode()).hexdigest()
    return raw

def cached(prefix, ttl=300):
    """Decorator: cache function return by prefix + args. Falls back to local memory."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = _cache_key(prefix, *args, *sorted(kwargs.items()))
            if REDIS_AVAILABLE:
                try:
                    val = cache_get(key)
                    if val is not None:
                        if isinstance(val, (bytes, memoryview)):
                            val = val.decode()
                        if isinstance(val, str):
                            try:
                                return json.loads(val)
                            except (json.JSONDecodeError, TypeError):
                                pass
                        return val
                except Exception:
                    pass
            if key in _IN_MEMORY_CACHE:
                entry = _IN_MEMORY_CACHE[key]
                if (datetime.now(timezone.utc).timestamp() - entry['ts']) < ttl:
                    return entry['val']
            result = fn(*args, **kwargs)
            if REDIS_AVAILABLE:
                try:
                    cache_set(key, json.dumps(result, default=str), ex=ttl)
                except Exception:
                    pass
            _IN_MEMORY_CACHE[key] = {'val': result, 'ts': datetime.now(timezone.utc).timestamp()}
            if len(_IN_MEMORY_CACHE) > 5000:
                _trim_memory_cache()
            return result
        return wrapper
    return decorator

def _trim_memory_cache():
    cutoff = datetime.now(timezone.utc).timestamp() - 3600
    stale = [k for k, v in _IN_MEMORY_CACHE.items() if v['ts'] < cutoff]
    for k in stale:
        _IN_MEMORY_CACHE.pop(k, None)

def invalidate(prefix, *args):
    key = _cache_key(prefix, *args)
    _IN_MEMORY_CACHE.pop(key, None)
    if REDIS_AVAILABLE:
        try:
            cache_delete(key)
        except Exception:
            pass

def invalidate_prefix(prefix):
    pattern = f"{prefix}:"
    stale = [k for k in _IN_MEMORY_CACHE.keys() if k.startswith(pattern)]
    for k in stale:
        _IN_MEMORY_CACHE.pop(k, None)
    if REDIS_AVAILABLE:
        try:
            import services.redis_service as rs
            rs.cache_delete(pattern + '*')
        except Exception:
            pass

def get_cache_stats():
    """Return cache statistics for monitoring."""
    return {
        'redis_available': REDIS_AVAILABLE,
        'memory_cache_entries': len(_IN_MEMORY_CACHE),
        'memory_cache_keys': list(_IN_MEMORY_CACHE.keys())[:100],
    }
