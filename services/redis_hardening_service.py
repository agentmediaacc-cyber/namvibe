import os
import time
from collections import deque

_MEMORY = {}
_LISTS = {}
_CIRCUIT = {"open_until": 0.0, "failures": 0, "last_error": None}
_CLIENT = None


def _testing():
    return (
        os.getenv("FLASK_TESTING") == "1"
        or os.getenv("CHAIN_FAST_LOCAL") == "1"
        or os.getenv("CHAIN_TEST_FAKE_DB") == "1"
    )


def _circuit_open():
    return time.time() < _CIRCUIT.get("open_until", 0)


def _record_failure(error):
    _CIRCUIT["failures"] = int(_CIRCUIT.get("failures") or 0) + 1
    _CIRCUIT["last_error"] = str(error)
    if _CIRCUIT["failures"] >= 2:
        _CIRCUIT["open_until"] = time.time() + 30


def _record_success():
    _CIRCUIT["failures"] = 0
    _CIRCUIT["open_until"] = 0.0
    _CIRCUIT["last_error"] = None


def get_redis_client():
    global _CLIENT
    if _testing() or _circuit_open():
        return None
    if _CLIENT is not None:
        return _CLIENT
    try:
        import redis
        url = os.getenv("REDIS_URL") or os.getenv("CHAIN_REDIS_URL") or "redis://localhost:6379/0"
        _CLIENT = redis.Redis.from_url(
            url,
            socket_connect_timeout=float(os.getenv("CHAIN_REDIS_CONNECT_TIMEOUT", "0.25")),
            socket_timeout=float(os.getenv("CHAIN_REDIS_SOCKET_TIMEOUT", "0.25")),
            decode_responses=True,
        )
        _CLIENT.ping()
        _record_success()
        return _CLIENT
    except Exception as error:
        _CLIENT = None
        _record_failure(error)
        return None


def redis_available():
    return get_redis_client() is not None


def safe_redis_get(key, default=None):
    client = get_redis_client()
    if client:
        try:
            return client.get(key)
        except Exception as error:
            _record_failure(error)
    return _MEMORY.get(key, default)


def safe_redis_set(key, value, ex=None):
    client = get_redis_client()
    if client:
        try:
            client.set(key, value, ex=ex)
            return {"ok": True, "backend": "redis"}
        except Exception as error:
            _record_failure(error)
    _MEMORY[key] = value
    return {"ok": True, "backend": "memory"}


def safe_redis_delete(key):
    client = get_redis_client()
    if client:
        try:
            client.delete(key)
            return {"ok": True, "backend": "redis"}
        except Exception as error:
            _record_failure(error)
    _MEMORY.pop(key, None)
    return {"ok": True, "backend": "memory"}


def safe_redis_lpush(key, value):
    client = get_redis_client()
    if client:
        try:
            client.lpush(key, value)
            return {"ok": True, "backend": "redis"}
        except Exception as error:
            _record_failure(error)
    _LISTS.setdefault(key, deque()).appendleft(value)
    return {"ok": True, "backend": "memory"}


def safe_redis_rpop(key):
    client = get_redis_client()
    if client:
        try:
            return client.rpop(key)
        except Exception as error:
            _record_failure(error)
    queue = _LISTS.setdefault(key, deque())
    return queue.pop() if queue else None


def safe_redis_publish(channel, message):
    client = get_redis_client()
    if client:
        try:
            return {"ok": True, "backend": "redis", "receivers": client.publish(channel, message)}
        except Exception as error:
            _record_failure(error)
    _LISTS.setdefault(f"pub:{channel}", deque()).append(message)
    return {"ok": True, "backend": "memory", "receivers": 0}


def safe_redis_subscribe_health():
    return {"ok": True, "available": redis_available(), "circuit_open": _circuit_open()}


def get_redis_health():
    available = redis_available()
    return {
        "ok": True,
        "available": available,
        "connected": available,
        "status": "ok" if available else "fallback",
        "fallback": not available,
        "circuit_open": _circuit_open(),
        "failures": int(_CIRCUIT.get("failures") or 0),
        "last_error": _CIRCUIT.get("last_error"),
        "backend": "redis" if available else "memory",
    }
