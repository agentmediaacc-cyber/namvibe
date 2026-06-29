import time
import random
from collections import defaultdict, deque
from datetime import datetime, timezone

_MEMORY_METRICS = defaultdict(lambda: {"count": 0, "total_ms": 0, "min_ms": float("inf"), "max_ms": 0})
_SLOW_QUERIES = deque(maxlen=50)
_CACHE_HITS = 0
_CACHE_MISSES = 0
_LOCK = None


def _redis():
    try:
        from services.redis_service import get_redis
        r = get_redis()
        if r:
            return r
    except Exception:
        pass
    return None


def _redlock():
    global _LOCK
    if _LOCK is not None:
        return _LOCK
    try:
        import threading
        _LOCK = threading.Lock()
    except Exception:
        _LOCK = False
    return _LOCK


def track_timing(name, duration_ms, metadata=None):
    lock = _redlock()
    if lock:
        lock.acquire()
    try:
        _MEMORY_METRICS[name]["count"] += 1
        _MEMORY_METRICS[name]["total_ms"] += duration_ms
        _MEMORY_METRICS[name]["min_ms"] = min(_MEMORY_METRICS[name]["min_ms"], duration_ms)
        _MEMORY_METRICS[name]["max_ms"] = max(_MEMORY_METRICS[name]["max_ms"], duration_ms)
    finally:
        if lock:
            lock.release()

    if duration_ms > 500:
        r = _redis()
        if r:
            try:
                import json
                payload = json.dumps({
                    "name": name,
                    "duration_ms": duration_ms,
                    "metadata": metadata or {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                r.lpush("perf:slow", payload)
                r.ltrim("perf:slow", 0, 99)
            except Exception:
                pass


def track_counter(name, count=1):
    r = _redis()
    if r:
        try:
            r.incrby(f"perf:counter:{name}", count)
            r.expire(f"perf:counter:{name}", 86400)
        except Exception:
            r = None

    if not r:
        if name not in _MEMORY_METRICS:
            _MEMORY_METRICS[name] = {"count": 0, "total_ms": 0, "min_ms": float("inf"), "max_ms": 0}
        _MEMORY_METRICS[name]["count"] += count


def record_cache_hit():
    global _CACHE_HITS
    _CACHE_HITS += 1


def record_cache_miss():
    global _CACHE_MISSES
    _CACHE_MISSES += 1


def slow_query_warning(operation, query_preview, duration_ms):
    if duration_ms < 100:
        return
    _SLOW_QUERIES.append({
        "operation": operation,
        "query_preview": query_preview[:200] if query_preview else "",
        "duration_ms": duration_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    r = _redis()
    if r:
        try:
            import json
            payload = json.dumps({
                "operation": operation,
                "query_preview": query_preview[:200] if query_preview else "",
                "duration_ms": duration_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            r.lpush("perf:slow_queries", payload)
            r.ltrim("perf:slow_queries", 0, 99)
        except Exception:
            pass


def get_performance_snapshot():
    r = _redis()
    slow_list = []
    slow_queries = []
    counters = {}

    if r:
        try:
            import json
            raw = r.lrange("perf:slow", 0, 19)
            if raw:
                slow_list = [json.loads(item) for item in raw]
            raw_q = r.lrange("perf:slow_queries", 0, 19)
            if raw_q:
                slow_queries = [json.loads(item) for item in raw_q]
            keys = r.keys("perf:counter:*")
            if keys:
                for key in keys:
                    name = key.split(":", 2)[2] if ":" in key else key
                    val = r.get(key)
                    if val is not None:
                        try:
                            counters[name] = int(val)
                        except Exception:
                            counters[name] = val
        except Exception:
            pass

    timing_metrics = {}
    for name, m in dict(_MEMORY_METRICS).items():
        if m["count"] > 0:
            timing_metrics[name] = {
                "count": m["count"],
                "total_ms": m["total_ms"],
                "avg_ms": round(m["total_ms"] / m["count"], 2),
                "min_ms": m["min_ms"] if m["min_ms"] != float("inf") else 0,
                "max_ms": m["max_ms"],
            }

    cache_ratio = 0
    total_cache = _CACHE_HITS + _CACHE_MISSES
    if total_cache > 0:
        cache_ratio = round((_CACHE_HITS / total_cache) * 100, 1)

    return {
        "timing_metrics": timing_metrics,
        "slow_operations": slow_list,
        "slow_queries": slow_queries,
        "counters": counters,
        "cache": {
            "hits": _CACHE_HITS,
            "misses": _CACHE_MISSES,
            "hit_ratio_pct": cache_ratio,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
