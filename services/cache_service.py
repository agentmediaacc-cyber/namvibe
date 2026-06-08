import time

from services.redis_service import cache_delete, cache_get, cache_set, get_redis_health


def get(key, default=None):
    value = cache_get(key)
    return value if value is not None else default


def set(key, value, ttl=60):
    cache_set(key, value, ttl=ttl)
    return value


def delete(key):
    return cache_delete(key)


def remember(key, loader, ttl=60, default=None):
    started = time.perf_counter()
    cached = get(key)
    if cached is not None:
        return cached, True, (time.perf_counter() - started) * 1000
    value = loader()
    if value is None:
        value = default
    set(key, value, ttl=ttl)
    return value, False, (time.perf_counter() - started) * 1000


def status():
    health = get_redis_health()
    return {
        "backend": "redis" if health.get("connected") else "memory",
        "redis_connected": bool(health.get("connected")),
        "fallback": bool(health.get("fallback")),
        "latency_ms": health.get("latency_ms", 0),
    }
