import json
import os
import re
import ssl
import time
import uuid
from urllib.parse import urlparse
from datetime import datetime, timezone

import redis

from services.circuit_breaker import CircuitBreaker
from services.env_service import get_env, load_project_env
from services.log_sanitizer import sanitize_connection_url, safe_connection_error, safe_exception_summary
from services.logging_service import log_warning, safe_print


load_project_env()
_DEFAULT_LOCAL_REDIS_URL = "redis://localhost:6379/0"
_ENV = get_env("FLASK_ENV", "development")
_REDIS_URL_RAW = (get_env("REDIS_URL") or (_DEFAULT_LOCAL_REDIS_URL if _ENV != "production" else "")).strip()
_REDIS_URL = _REDIS_URL_RAW
_LOCAL_REDIS_HOST = get_env("CHAIN_LOCAL_REDIS_HOST", "127.0.0.1")
_LOCAL_REDIS_PORT = get_env("CHAIN_LOCAL_REDIS_PORT", "6379")
_LOCAL_REDIS_DB = get_env("CHAIN_LOCAL_REDIS_DB", "0")
_LOCAL_REDIS_URL = f"redis://{_LOCAL_REDIS_HOST}:{_LOCAL_REDIS_PORT}/{_LOCAL_REDIS_DB}"

_REDIS_URL_MASKED = sanitize_connection_url(_REDIS_URL)

def mask_redis_url(url):
    return sanitize_connection_url(url)

_SSL_CERT_REQS_MAP = {
    "none": ssl.CERT_NONE,
    "optional": ssl.CERT_OPTIONAL,
    "required": ssl.CERT_REQUIRED,
}
_RAW_SSL_REQS = (get_env("REDIS_SSL_CERT_REQS") or "").strip().lower()
_REDIS_SSL_CERT_REQS = _SSL_CERT_REQS_MAP.get(_RAW_SSL_REQS)

_LOG_THROTTLE = {}
_MEMORY_FALLBACK = {}
_SET_FALLBACK = {}
_TTL_FALLBACK = {}
_RECONNECT_BACKOFF = {
    "attempts": 0,
    "retry_after": 0.0,
}


def log_redis_warning(key, message, interval_seconds=60):
    now = time.monotonic()
    if _LOG_THROTTLE.get(key, 0) > now:
        return False
    _LOG_THROTTLE[key] = now + max(int(interval_seconds), 1)
    safe_print(message)
    return True


class RedisManager:
    def __init__(self):
        self.url = _REDIS_URL
        self.namespace = "chain"
        self.client = None
        self.client_backend = None
        self.client_meta = {}
        self.pubsub_client = None
        self.last_error = None
        self.last_connected_at = None
        self.last_failure_at = None
        self.failure_times = []
        self.health_cache = {"expires_at": 0.0, "payload": None}
        self.breaker = CircuitBreaker("redis", failure_threshold=3, recovery_seconds=30)
        self.allow_local_fallback = (get_env("CHAIN_REDIS_ALLOW_LOCAL_FALLBACK") or "").strip().lower() in {"1", "true", "yes", "on"}

    def _remember_failure(self, error):
        now = time.monotonic()
        self.last_error = str(error)[:240]
        self.last_failure_at = datetime.now(timezone.utc).isoformat()
        self.failure_times = [ts for ts in self.failure_times if now - ts <= 30]
        self.failure_times.append(now)
        self.breaker.failure(error)
        delay = min(30, max(2, 2 ** min(len(self.failure_times), 4)))
        _RECONNECT_BACKOFF["attempts"] = len(self.failure_times)
        _RECONNECT_BACKOFF["retry_after"] = time.monotonic() + delay
        log_redis_warning("redis_unavailable", safe_connection_error(error, endpoint=self.url))

    def _remember_success(self):
        self.last_error = None
        self.last_connected_at = datetime.now(timezone.utc).isoformat()
        self.failure_times = []
        _RECONNECT_BACKOFF["attempts"] = 0
        _RECONNECT_BACKOFF["retry_after"] = 0.0
        self.breaker.success()

    def fallback_enabled(self):
        return not bool(self.url) or self.client is None

    def _ttl_valid(self, key):
        expires_at = _TTL_FALLBACK.get(key)
        if expires_at and expires_at <= time.monotonic():
            _MEMORY_FALLBACK.pop(key, None)
            _SET_FALLBACK.pop(key, None)
            _TTL_FALLBACK.pop(key, None)
            return False
        return True

    def _memory_get(self, key):
        return _MEMORY_FALLBACK.get(key) if self._ttl_valid(key) else None

    def _memory_set(self, key, value, ttl=None):
        _MEMORY_FALLBACK[key] = value
        if ttl:
            _TTL_FALLBACK[key] = time.monotonic() + int(ttl)
        else:
            _TTL_FALLBACK.pop(key, None)
        return True

    def get_client(self):
        if not self.url:
            return None
        if self.client is not None:
            return self.client
        if time.monotonic() < _RECONNECT_BACKOFF.get("retry_after", 0):
            return None
        if not self.breaker.allow():
            return None
        def _connect(url, backend_label):
            kwargs = dict(
                decode_responses=True,
                socket_timeout=10,
                socket_connect_timeout=10,
                retry_on_timeout=True,
                health_check_interval=15,
            )
            client_url = url
            if url.startswith("rediss://") and _REDIS_SSL_CERT_REQS is not None:
                ssl_label = _RAW_SSL_REQS or "none"
                sep = "&" if "?" in url else "?"
                client_url = f"{url}{sep}ssl_cert_reqs={ssl_label}"
            client = redis.from_url(client_url, **kwargs)
            client.ping()
            self.client = client
            self.client_backend = backend_label
            try:
                parsed = urlparse(url)
                path = (parsed.path or "").lstrip("/")
                db = int(path) if path.isdigit() else 0
                self.client_meta = {
                    "host": parsed.hostname,
                    "port": parsed.port,
                    "db": db,
                    "ssl": parsed.scheme == "rediss",
                }
            except Exception:
                self.client_meta = {}
            self._remember_success()
            return client

        def _connect_local(host, port, db, backend_label):
            client = redis.Redis(
                host=host,
                port=int(port),
                db=int(db),
                decode_responses=True,
                socket_timeout=10,
                socket_connect_timeout=10,
                retry_on_timeout=True,
                health_check_interval=15,
            )
            client.ping()
            self.client = client
            self.client_backend = backend_label
            self.client_meta = {
                "host": host,
                "port": int(port),
                "db": int(db),
                "ssl": False,
            }
            self._remember_success()
            return client

        try:
            return _connect(self.url, "redis_remote")
        except Exception as error:
            self.client = None
            self.client_backend = None
            self.client_meta = {}
            self.reset_pubsub()
            self._remember_failure(error)
            local_url = _LOCAL_REDIS_URL
            if self.allow_local_fallback and self.url != local_url:
                try:
                    safe_print(f"[redis_service] Primary Redis unavailable; falling back to local Redis backend: {safe_exception_summary(error)}")
                    return _connect_local(_LOCAL_REDIS_HOST, _LOCAL_REDIS_PORT, _LOCAL_REDIS_DB, "redis_local")
                except Exception as local_error:
                    self.client = None
                    self.client_backend = None
                    self.client_meta = {}
                    self.reset_pubsub()
                    self._remember_failure(local_error)
                    import traceback
                    safe_print(f"[redis_service] Local Redis fallback failed: {safe_exception_summary(local_error)}")
                    safe_print(traceback.format_exc())
                    return None
            return None

    def backend_state(self):
        if self.client_backend:
            return self.client_backend
        if self.client is None and self.url and self.allow_local_fallback:
            return "memory_degraded"
        if not self.url:
            return "none"
        return "memory_degraded"

    def reset_pubsub(self):
        if self.pubsub_client is not None:
            try:
                self.pubsub_client.close()
            except Exception:
                pass
        self.pubsub_client = None

    def _safe_json(self, value):
        try:
            return json.dumps(value, default=str)
        except Exception:
            return json.dumps(str(value))

    def is_available(self):
        return self.get_client() is not None

    def is_ready(self):
        return self.is_available()

    def get_json(self, key, default=None):
        return self.get_json_result(key, default=default)["value"]

    def get_json_result(self, key, default=None):
        client = self.get_client()
        namespaced = namespaced_key(key)
        if not client:
            value = self._memory_get(namespaced)
            return {
                "success": value is not None,
                "backend": self.backend_state(),
                "persistent": self.backend_state() in {"redis_remote", "redis_local"},
                "shared": self.backend_state() in {"redis_remote", "redis_local"},
                "value": value if value is not None else default,
                "error": self.last_error,
            }
        try:
            raw = client.get(namespaced)
            value = json.loads(raw) if raw else default
            return {
                "success": raw is not None,
                "backend": self.backend_state(),
                "persistent": True,
                "shared": True,
                "value": value,
                "error": None,
            }
        except Exception as error:
            self.client = None
            self._remember_failure(error)
            value = self._memory_get(namespaced)
            return {
                "success": value is not None,
                "backend": self.backend_state(),
                "persistent": False,
                "shared": False,
                "value": value if value is not None else default,
                "error": type(error).__name__,
            }

    def set_json(self, key, value, ttl=60):
        return self.set_json_result(key, value, ttl=ttl)["success"]

    def set_json_result(self, key, value, ttl=60, require_shared=False):
        client = self.get_client()
        namespaced = namespaced_key(key)
        if not client:
            ok = self._memory_set(namespaced, value, ttl=ttl)
            backend = self.backend_state()
            return {
                "success": ok,
                "backend": backend,
                "persistent": False,
                "shared": False,
                "degraded": True,
                "error": self.last_error,
            }
        try:
            raw = self._safe_json(value)
            if ttl:
                client.setex(namespaced, int(ttl), raw)
            else:
                client.set(namespaced, raw)
            self._memory_set(namespaced, value, ttl=ttl)
            self._remember_success()
            return {
                "success": True,
                "backend": self.backend_state(),
                "persistent": True,
                "shared": True,
                "degraded": False,
                "error": None,
            }
        except Exception as error:
            self.client = None
            self._remember_failure(error)
            ok = self._memory_set(namespaced, value, ttl=ttl)
            backend = "memory_degraded"
            return {
                "success": ok,
                "backend": backend,
                "persistent": False,
                "shared": False,
                "degraded": True,
                "error": type(error).__name__,
            }

    def mget_json(self, keys, default=None):
        """Bulk get multiple pre-namespaced keys. Returns {key: parsed_value or default}."""
        client = self.get_client()
        namespaced_map = {k: namespaced_key(k) for k in keys}
        if not client:
            return {k: (self._memory_get(nk) if self._memory_get(nk) is not None else default)
                    for k, nk in namespaced_map.items()}
        try:
            raw_values = client.mget(list(namespaced_map.values()))
            result = {}
            for k, raw in zip(keys, raw_values):
                if raw is not None:
                    try:
                        result[k] = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        result[k] = default
                else:
                    result[k] = default
            self._remember_success()
            return result
        except Exception as error:
            self.client = None
            self._remember_failure(error)
            return {k: (self._memory_get(nk) if self._memory_get(nk) is not None else default)
                    for k, nk in namespaced_map.items()}

    def set_json_bulk(self, items, ttl=60):
        """Bulk set using pipeline. items is [(pre_namespaced_key, value)]."""
        client = self.get_client()
        if not client:
            for key, value in items:
                self._memory_set(namespaced_key(key), value, ttl=ttl)
            return True
        try:
            pipe = client.pipeline()
            for key, value in items:
                nk = namespaced_key(key)
                raw = self._safe_json(value)
                pipe.setex(nk, int(ttl), raw)
                self._memory_set(nk, value, ttl=ttl)
            pipe.execute()
            self._remember_success()
            return True
        except Exception as error:
            self.client = None
            self._remember_failure(error)
            for key, value in items:
                self._memory_set(namespaced_key(key), value, ttl=ttl)
            return True

    def delete(self, key):
        return self.delete_result(key)["success"]

    def delete_result(self, key):
        client = self.get_client()
        namespaced = namespaced_key(key)
        _MEMORY_FALLBACK.pop(namespaced, None)
        _SET_FALLBACK.pop(namespaced, None)
        _TTL_FALLBACK.pop(namespaced, None)
        if not client:
            return {
                "success": True,
                "backend": self.backend_state(),
                "persistent": False,
                "shared": False,
                "error": None,
            }
        try:
            client.delete(namespaced)
            self._remember_success()
            return {
                "success": True,
                "backend": self.backend_state(),
                "persistent": True,
                "shared": True,
                "error": None,
            }
        except Exception as error:
            self.client = None
            self._remember_failure(error)
            return {
                "success": False,
                "backend": self.backend_state(),
                "persistent": False,
                "shared": False,
                "error": type(error).__name__,
            }

    def acquire_lock(self, key, ttl=10):
        client = self.get_client()
        namespaced = namespaced_key(key)
        if not client or self.backend_state() not in {"redis_remote", "redis_local"}:
            return {
                "success": False,
                "backend": self.backend_state(),
                "shared": False,
                "persistent": False,
                "token": None,
            }
        token = uuid.uuid4().hex
        try:
            ok = client.set(namespaced, token, nx=True, ex=int(ttl))
            return {
                "success": bool(ok),
                "backend": self.backend_state(),
                "shared": True,
                "persistent": True,
                "token": token if ok else None,
            }
        except Exception as error:
            self.client = None
            self._remember_failure(error)
            return {
                "success": False,
                "backend": self.backend_state(),
                "shared": False,
                "persistent": False,
                "token": None,
                "error": type(error).__name__,
            }

    def release_lock(self, key, token):
        client = self.get_client()
        namespaced = namespaced_key(key)
        if not client or not token:
            return {"success": False, "backend": self.backend_state(), "shared": False, "persistent": False}
        try:
            script = """
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            end
            return 0
            """
            deleted = client.eval(script, 1, namespaced, token)
            return {"success": bool(deleted), "backend": self.backend_state(), "shared": True, "persistent": True}
        except Exception as error:
            self.client = None
            self._remember_failure(error)
            return {"success": False, "backend": self.backend_state(), "shared": False, "persistent": False, "error": type(error).__name__}

    def publish(self, channel, payload):
        client = self.get_client()
        if not client:
            return False
        last_error = None
        for attempt in range(3):
            try:
                client.publish(pubsub_channel(channel), self._safe_json(payload))
                self._remember_success()
                if attempt > 0:
                    log_redis_warning("redis_publish_retry_succeeded",
                                      f"[redis_service] publish succeeded on retry attempt {attempt + 1}")
                return True
            except Exception as error:
                last_error = error
                self.client = None
                self.reset_pubsub()
                self._remember_failure(error)
                # Exponential backoff: 50ms, 200ms, 1s — do not block for long
                if attempt < 2:
                    backoff = 0.05 * (4 ** attempt)
                    time.sleep(min(backoff, 1.0))
        log_warning("redis_publish_failed",
                    f"[redis_service] publish failed after 3 attempts for channel={channel}: {last_error}")
        return False

    def subscribe(self, *channels):
        client = self.get_client()
        if not client:
            return None
        try:
            self.pubsub_client = client.pubsub(ignore_subscribe_messages=True)
            self.pubsub_client.subscribe(*(pubsub_channel(channel) for channel in channels))
            self._remember_success()
            return self.pubsub_client
        except Exception as error:
            self.reset_pubsub()
            self._remember_failure(error)
            return None

    def incr_with_ttl(self, key, ttl):
        client = self.get_client()
        namespaced = namespaced_key(key)
        if not client:
            value = int(self._memory_get(namespaced) or 0) + 1
            self._memory_set(namespaced, value, ttl=ttl)
            return value
        try:
            value = client.incr(namespaced)
            if ttl:
                client.expire(namespaced, int(ttl))
            self._remember_success()
            return int(value)
        except Exception as error:
            self.client = None
            self._remember_failure(error)
            value = int(self._memory_get(namespaced) or 0) + 1
            self._memory_set(namespaced, value, ttl=ttl)
            return value

    def set_add(self, key, member, ttl=None):
        namespaced = namespaced_key(key)
        bucket = _SET_FALLBACK.setdefault(namespaced, set())
        bucket.add(member)
        if ttl:
            _TTL_FALLBACK[namespaced] = time.monotonic() + int(ttl)
        client = self.get_client()
        if not client:
            return True
        try:
            client.sadd(namespaced, member)
            if ttl:
                client.expire(namespaced, int(ttl))
            self._remember_success()
            return True
        except Exception as error:
            self.client = None
            self._remember_failure(error)
            return True

    def set_remove(self, key, member):
        namespaced = namespaced_key(key)
        _SET_FALLBACK.setdefault(namespaced, set()).discard(member)
        client = self.get_client()
        if not client:
            return True
        try:
            client.srem(namespaced, member)
            self._remember_success()
            return True
        except Exception as error:
            self.client = None
            self._remember_failure(error)
            return False

    def set_members(self, key):
        namespaced = namespaced_key(key)
        if not self._ttl_valid(namespaced):
            return set()
        client = self.get_client()
        if not client:
            return set(_SET_FALLBACK.get(namespaced, set()))
        try:
            members = set(client.smembers(namespaced))
            _SET_FALLBACK[namespaced] = set(members)
            self._remember_success()
            return members
        except Exception as error:
            self.client = None
            self._remember_failure(error)
            return set(_SET_FALLBACK.get(namespaced, set()))

    def get_ttl(self, key):
        namespaced = namespaced_key(key)
        client = self.get_client()
        if not client:
            expires_at = _TTL_FALLBACK.get(namespaced)
            if not expires_at:
                return -2
            return max(int(expires_at - time.monotonic()), -2)
        try:
            return int(client.ttl(namespaced))
        except Exception as error:
            self.client = None
            self._remember_failure(error)
            return -2

    def get_health(self):
        now = time.monotonic()
        cached = self.health_cache.get("payload")
        if cached is not None and self.health_cache.get("expires_at", 0) > now:
            return dict(cached)
        started = time.perf_counter()
        connected = False
        error = self.last_error
        client = self.get_client()
        if client:
            try:
                client.ping()
                connected = True
                self._remember_success()
                error = None
            except Exception as exc:
                self.client = None
                self._remember_failure(exc)
                error = self.last_error
        scheme = ""
        ssl_reqs_label = None
        if self.url:
            scheme = sanitize_connection_url(self.url)
        if _REDIS_SSL_CERT_REQS is not None:
            ssl_reqs_label = _RAW_SSL_REQS if _RAW_SSL_REQS else "none"

        payload = {
            "status": "ok" if connected else "degraded",
            "connected": connected or self.backend_state() == "memory_degraded",
            "fallback": not connected,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": "[masked]" if error else None,
            "last_connected_at": self.last_connected_at,
            "last_failure_at": self.last_failure_at,
            "circuit_state": self.breaker.get_state(),
            "redis_url_scheme": scheme,
            "ssl_cert_reqs": ssl_reqs_label,
            "backend": self.client_backend if connected else self.backend_state(),
            "redis_host": self.client_meta.get("host"),
            "redis_port": self.client_meta.get("port"),
            "redis_db": self.client_meta.get("db"),
            "local_redis_host": _LOCAL_REDIS_HOST,
            "local_redis_port": int(_LOCAL_REDIS_PORT),
            "local_redis_db": int(_LOCAL_REDIS_DB),
            "shared": self.client_backend in {"redis_remote", "redis_local"},
            "persistent": self.client_backend in {"redis_remote", "redis_local"},
            "retry_after_seconds": max(0, int(_RECONNECT_BACKOFF.get("retry_after", 0) - time.monotonic())) if _RECONNECT_BACKOFF.get("retry_after", 0) else 0,
        }
        self.health_cache["payload"] = dict(payload)
        self.health_cache["expires_at"] = now + 30
        return payload

    def reconnect(self):
        self.client = None
        self.reset_pubsub()
        return self.get_client()


redis_manager = RedisManager()


def namespaced_key(*parts):
    clean = [str(part).strip(":") for part in parts if part not in (None, "")]
    return ":".join(["chain"] + clean)


def pubsub_channel(*parts):
    return namespaced_key("socket", *parts)


def cache_key(*parts):
    return namespaced_key("cache", *parts)


def presence_key(*parts):
    return namespaced_key("presence", *parts)


def queue_key(*parts):
    return namespaced_key("queue", *parts)


def typing_key(*parts):
    return namespaced_key("typing", *parts)


def socket_key(*parts):
    return namespaced_key("socket", *parts)


def feed_key(*parts):
    return namespaced_key("feed", *parts)


def notif_key(*parts):
    return namespaced_key("notif", *parts)


def metrics_key(*parts):
    return namespaced_key("metrics", *parts)


def invalidate_namespace(prefix):
    client = redis_manager.get_client()
    if not client:
        return 0
    deleted = 0
    pattern = namespaced_key(prefix, "*")
    try:
        for key in client.scan_iter(pattern):
            client.delete(key)
            deleted += 1
    except Exception as error:
        redis_manager._remember_failure(error)
    return deleted


def get_redis():
    return redis_manager.get_client()


def get_pubsub_client():
    return redis_manager.get_client()


def reset_pubsub():
    redis_manager.reset_pubsub()


def redis_available():
    return redis_manager.is_available()


def cache_get(key):
    return redis_manager.get_json(cache_key(key))


def cache_set(key, value, ttl=60):
    return redis_manager.set_json(cache_key(key), value, ttl=ttl)


def cache_mget(keys):
    """Bulk get multiple cache keys. keys is list of raw keys (without cache: prefix).
    Returns dict mapping each raw key to its parsed value or None."""
    return redis_manager.mget_json([cache_key(k) for k in keys], default=None)


def cache_set_bulk(items, ttl=60):
    """Bulk set multiple cache keys via pipeline.
    items is [(raw_key, value)] — raw keys without cache: prefix."""
    return redis_manager.set_json_bulk([(cache_key(k), v) for k, v in items], ttl=ttl)


def cache_delete(key):
    return redis_manager.delete(cache_key(key))


def set_json(key, value, ttl=None):
    return redis_manager.set_json(key, value, ttl=ttl or 60)


def get_json(key, default=None):
    return redis_manager.get_json(key, default=default)


def delete_key(key):
    return redis_manager.delete(key)


def set_add(key, member, ttl=None):
    return redis_manager.set_add(key, member, ttl=ttl)


def set_remove(key, member):
    return redis_manager.set_remove(key, member)


def set_members(key):
    return redis_manager.set_members(key)


def get_ttl(key):
    return redis_manager.get_ttl(key)


def publish(channel, payload):
    return redis_manager.publish(channel, payload)


def subscribe(*channels):
    return redis_manager.subscribe(*channels)


def incr_with_ttl(key, ttl):
    return redis_manager.incr_with_ttl(key, ttl)


def get_redis_health():
    return redis_manager.get_health()


def redis_health():
    return get_redis_health()


def redis_is_ready():
    return redis_manager.is_ready()


def redis_safe_publish(channel, payload):
    return publish(channel, payload)


def redis_safe_get(key, default=None):
    return get_json(key, default=default)


def redis_safe_set(key, value, ttl=60):
    return set_json(key, value, ttl=ttl)


def get_reel_cache_backend_status():
    health = redis_manager.get_health()
    return {
        "backend": health.get("backend"),
        "shared": bool(health.get("shared")),
        "persistent": bool(health.get("persistent")),
        "available": bool(health.get("connected")),
        "retry_after_seconds": int(health.get("retry_after_seconds") or 0),
    }


def get_reel_cache_json(key, default=None):
    return redis_manager.get_json_result(key, default=default)


def set_reel_cache_json(key, value, ttl=60, require_shared=True):
    return redis_manager.set_json_result(key, value, ttl=ttl, require_shared=require_shared)


def delete_reel_cache(key):
    return redis_manager.delete_result(key)


def acquire_reel_cache_lock(key, ttl=10):
    return redis_manager.acquire_lock(key, ttl=ttl)


def release_reel_cache_lock(key, token):
    return redis_manager.release_lock(key, token)
