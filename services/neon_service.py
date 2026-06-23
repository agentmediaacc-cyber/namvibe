import os
import time
import threading
import json
import functools
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Optional, List, Dict, Union
import uuid
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from datetime import datetime, timezone

import psycopg2
from psycopg2 import pool, sql, extensions
from psycopg2.extras import Json, RealDictCursor
from psycopg2 import errors as pg_errors
from services.circuit_breaker import CircuitBreaker
from services.env_service import get_env, load_project_env
from services.logging_service import log_error, log_warning, log_info, log_metric
from services.log_rate_limit_service import sql_fingerprint, should_log

# CHAIN_STATIC_SCHEMA_CACHE
# Avoid slow pg_attribute/pg_class schema checks during hot requests.
CHAIN_STATIC_COLUMNS = {
    "chain_profiles": {
        "id", "auth_user_id", "email", "username", "display_name", "full_name",
        "avatar_url", "thumbnail_url", "town", "city",
        "location", "region", "country", "country_origin", "current_country", "current_location",
        "cover_url", "cover_path", "banner_url", "banner_path",
        "avatar_size_bytes", "cover_size_bytes", "avatar_mime_type", "cover_mime_type",
        "avatar_storage_bucket", "cover_storage_bucket", "avatar_storage_path",
        "cover_storage_path", "avatar_updated_at", "cover_updated_at",
        "is_verified", "verified", "is_online", "is_online_status", "is_creator", "creator_category",
        "dating_mode_enabled", "is_premium", "wallet_balance", "profile_completed",
        "followers_count", "following_count", "posts_count", "reels_count", "friends_count", "saved_count",
        "tagged_count", "bio", "is_public", "photo_url",
        "deleted_at", "created_at", "updated_at", "bio",
        "visibility", "profile_visibility", "profile_type", "terms_accepted_at",
        "privacy_accepted_at", "privacy_accepted", "privacy_version", "terms_version",
        "who_can_message", "who_can_call", "who_can_see_status",
        "message_only_after_match", "tour_seen"
    },
    "chain_posts": {
        "id", "profile_id", "body", "caption", "content", "post_type", "link_url",
        "town_tag", "visibility", "media_url", "video_url", "thumbnail_url",
        "media_bucket", "media_path", "mime_type", "size_bytes",
        "likes_count", "comments_count", "shares_count", "category",
        "status", "is_archived", "is_pinned", "scheduled_at",
        "deleted_at", "created_at", "updated_at"
    },
    "chain_reels": {
        "id", "profile_id", "caption", "video_url", "thumbnail_url", "media_url",
        "storage_bucket", "storage_path", "media_bucket", "media_path",
        "music_title", "status", "visibility", "processing_status",
        "mime_type", "file_size", "size_bytes",
        "likes_count", "comments_count", "shares_count", "views_count",
        "is_archived", "is_pinned", "scheduled_at",
        "deleted_at", "created_at", "updated_at"
    },
    "chain_friend_requests": {
        "id", "sender_profile_id", "recipient_profile_id",
        "receiver_profile_id",
        "status", "message", "created_at", "updated_at", "responded_at"
    },
    "chain_friends": {
        "id", "profile_id_1", "profile_id_2",
        "profile_id", "friend_profile_id",
        "status", "created_at", "updated_at", "deleted_at"
    },
    "chain_follows": {
        "id", "follower_profile_id", "following_profile_id",
        "created_at", "updated_at", "deleted_at"
    },
    "chain_follow_requests": {
        "id", "requester_profile_id", "target_profile_id",
        "status", "message", "created_at", "updated_at", "responded_at"
    },
    "chain_blocks": {
        "id", "blocker_profile_id", "blocked_profile_id",
        "reason", "created_at", "updated_at", "deleted_at"
    },
    "chain_status_posts": {
        "id", "profile_id", "caption", "media_url", "video_url", "media_type",
        "storage_bucket", "storage_path", "visibility", "expires_at",
        "likes_count", "views_count", "comments_count",
        "mime_type", "size_bytes", "status_type",
        "deleted_at", "created_at", "updated_at"
    },
    "chain_stories": {
        "id", "profile_id", "caption",  "thumbnail_url",
        "deleted_at", "created_at", "updated_at"
    },
    "chain_live_rooms": {
        "id", "profile_id",   "title", 
        "category", "status", "is_live", "viewer_count", 
        "cover_url", "thumbnail_url",  "entry_fee", 
        "deleted_at", "created_at", "updated_at"
    },
    "chain_notifications": {
        "id", "recipient_profile_id", "actor_profile_id", "event_type",
        "title", "body", "entity_type", "entity_id", "action_url",
        "is_read", "deleted_at", "created_at", "updated_at"
    },
    "chain_video_events": {
        "id", "viewer_profile_id", "video_type", "video_id", "creator_profile_id",
        "event_type", "watch_ms", "created_at"
    },
    "chain_ip_reputation": {
        "ip_address", "is_blocked", "created_at", "updated_at"
    },
    "chain_wallets": {
        "id", "profile_id", "coin_balance", "gift_earnings", "pending_withdrawal",
        "status", "withdrawal_status", "created_at", "updated_at"
    },
    "chain_creator_tools": {
        "id", "profile_id", "studio_enabled", "monetization_enabled",
        "creator_notes", "featured_links", "created_at", "updated_at"
    },
    "chain_user_settings": {
        "id", "profile_id", "allow_messages", "allow_video_calls",
        "show_online_status", "profile_visibility", "created_at", "updated_at"
    },
    "chain_account_security": {
        "id", "profile_id", "password_set", "recovery_enabled",
        "created_at", "updated_at"
    },
    "chain_login_events": {
        "id", "profile_id", "auth_user_id", "provider", "email",
        "ip_address", "user_agent", "status", "created_at"
    },
    "chain_media_albums": {
        "id", "profile_id", "title", "description", "cover_url",
        "visibility", "created_at", "updated_at"
    },
}


load_project_env()


def _is_production_env():
    return get_env("FLASK_ENV") == "production" or get_env("ENV") == "production"


if not _is_production_env():
    os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
    os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
    os.environ.setdefault("CHAIN_FAST_LOCAL", "1")


def _flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}

# Configuration from Environment
DATABASE_URL = (get_env("DATABASE_URL", "") or "").strip()
POOL_MIN = int(get_env("DB_POOL_MIN", "5") or "5")
POOL_MAX = int(get_env("DB_POOL_MAX", "40") or "40")
POOL_RECYCLE = int(get_env("DB_POOL_RECYCLE", "600") or "600") # 10 minutes
STATEMENT_TIMEOUT_DEFAULT = int(get_env("DB_STATEMENT_TIMEOUT", "30000") or "30000")

# State Management
_POOL = None
_POOL_LOCK = threading.Lock()
_CONN_CREATED_AT = {} # id(conn) -> float (timestamp)
_LAST_SUCCESS_AT = 0.0
_NEON_BREAKER = CircuitBreaker("neon", failure_threshold=5, recovery_seconds=30)
_DB_EXECUTOR = ThreadPoolExecutor(max_workers=POOL_MAX + 10, thread_name_prefix="neon_db")

# Schema Caching
_COLUMN_CACHE = {}
_TABLE_EXISTS_CACHE = {}
_COLUMN_CACHE_TTL = 3600 * 24 # 24 hours
_TABLE_EXISTS_CACHE_TTL = 3600 * 24
_HEALTH_CACHE = {"payload": None, "expires_at": 0.0}

def get_table_columns(table_name: str, timeout_ms=10000):
    """Retrieves column names for a table, prioritizing static cache."""
    if os.getenv("CHAIN_TRUST_PROFILE_SCHEMA", "1") == "1":
        static_cols = CHAIN_STATIC_COLUMNS.get(table_name)
        if static_cols:
            return set(static_cols)

    cached = _COLUMN_CACHE.get(table_name)
    now = time.time()
    if cached is not None and now < cached["expires_at"]:
        return cached["columns"]

    log_info("schema_cache_miss", table=table_name, kind="columns")
    query = """
        SELECT a.attname as column_name
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = %s AND n.nspname = 'public'
        AND a.attnum > 0 AND NOT a.attisdropped
    """
    rows = fast_query(query, (table_name,), timeout_ms=timeout_ms)
    columns = [r["column_name"] for r in rows] if rows else []
    
    _COLUMN_CACHE[table_name] = {
        "columns": columns,
        "expires_at": now + _COLUMN_CACHE_TTL
    }
    return columns



def is_circuit_open():
    """Compatibility helper used by auth/profile services."""
    try:
        return not _NEON_BREAKER.allow()
    except Exception:
        return False


def table_exists(table_name: str, timeout_ms=5000):
    """Checks if a table exists, prioritizing static cache."""
    if os.getenv("CHAIN_TRUST_PROFILE_SCHEMA", "1") == "1":
        if table_name in CHAIN_STATIC_COLUMNS:
            return True

    cached = _TABLE_EXISTS_CACHE.get(table_name)
    now = time.time()
    if cached is not None and now < cached["expires_at"]:
        return cached["exists"]

    log_info("schema_cache_miss", table=table_name, kind="table_exists")
    query = "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relname = %s LIMIT 1"
    res = fast_query(query, (table_name,), timeout_ms=timeout_ms)
    exists = bool(res)
    _TABLE_EXISTS_CACHE[table_name] = {
        "exists": exists,
        "expires_at": now + _TABLE_EXISTS_CACHE_TTL,
    }
    return exists

class NeonError(Exception):
    """Base exception for Neon service errors."""
    pass

class NeonWriteError(NeonError):
    pass

class CircuitOpenError(NeonError):
    pass

def _optimize_dsn(url: str) -> str:
    """Attempt to normalise a DATABASE_URL for Neon/pooling.

    This implementation is intentionally conservative: when the input does not
    cleanly parse as a postgres URL we return a stripped candidate rather than
    building a malformed DSN (which previously produced strings like
    'SET?sslmode=...' and caused psycopg2 to fail). The only real change here
    is to avoid fragile regex literals that embed unescaped quotes.
    """
    if not url:
        return url

    # Trim whitespace and try to extract a postgres URL if the input contains
    # extra shell tokens like 'set' or 'export'.
    s = url.strip()
    low = s.lower()
    if low.startswith('set ') or low.startswith('export ') or low == 'set':
        parts = s.split(None, 1)
        s = parts[-1] if parts else s

    # If a postgres scheme appears somewhere in the string, take the substring
    l = s.lower()
    idx = l.find('postgresql://')
    if idx == -1:
        idx = l.find('postgres://')
    if idx != -1:
        s = s[idx:]

    parsed = urlparse(s)
    if (parsed.scheme or '').lower() not in ('postgres', 'postgresql') or not parsed.hostname:
        return s

    # If query contains stray '?', normalise it
    if parsed.query and '?' in parsed.query:
        q = parsed.query.split('?', 1)[1]
        parsed = parsed._replace(query=q)

    hostname = parsed.hostname or ''

    # Prefer Neon pooler hostnames when it looks like a neon.tech host
    if 'neon.tech' in hostname and '-pooler' not in hostname:
        parts = hostname.split('.')
        if len(parts) >= 4 and parts[-3:] == ['aws', 'neon', 'tech']:
            parts[0] = f"{parts[0]}-pooler"
            new_hostname = '.'.join(parts)
            netloc = parsed.netloc
            if '@' in netloc:
                creds, hostpart = netloc.split('@', 1)
                if ':' in hostpart:
                    _host, port = hostpart.split(':', 1)
                    hostpart = f"{new_hostname}:{port}"
                else:
                    hostpart = new_hostname
                netloc = f"{creds}@{hostpart}"
            else:
                if ':' in netloc:
                    _host, port = netloc.split(':', 1)
                    netloc = f"{new_hostname}:{port}"
                else:
                    netloc = new_hostname
            parsed = parsed._replace(netloc=netloc)

    # Merge defaults with existing query params
    existing_qs = dict(parse_qsl(parsed.query, keep_blank_values=True))
    defaults = {
        'sslmode': 'require',
        'application_name': 'chain_app_backend',
        'connect_timeout': '5',
        'keepalives': '1',
        'keepalives_idle': '30',
        'keepalives_interval': '10',
        'keepalives_count': '5',
    }
    merged = {**defaults, **existing_qs}
    safe_merged = {k: str(v) for k, v in merged.items()}
    new_query = urlencode(safe_merged)
    parsed = parsed._replace(query=new_query)
    return urlunparse(parsed)


def _safe_optimize_dsn(url: str) -> str:
    """Wrapper around _optimize_dsn that avoids raising on bad inputs.

    If _optimize_dsn would return an invalid/non-postgres value, prefer the
    original environment value (stripped). This prevents accidental DSNs like
    'SET?sslmode=...' from being produced when a non-URL string is present in env.
    """
    try:
        out = _optimize_dsn(url or "")
        if not out:
            return (url or "").strip()
        return out
    except Exception:
        return (url or "").strip()

def _get_dsn_kwargs():
    """Returns kwargs for psycopg2 connection."""
    optimized_url = _safe_optimize_dsn(DATABASE_URL)
    # Validate the optimized URL looks like a Postgres DSN. If not, fall back
    # to the original environment value (stripped). This avoids producing
    # malformed DSNs such as 'SET?sslmode=...' when env content is unexpected.
    dsn_candidate = (optimized_url or "").strip()
    if not dsn_candidate.lower().startswith(("postgres://", "postgresql://")):
        dsn_candidate = (DATABASE_URL or "").strip()
    return {
        "dsn": dsn_candidate,
        "cursor_factory": RealDictCursor,
    }


def _is_connection_error(error: Exception) -> bool:
    if isinstance(error, (CircuitOpenError, psycopg2.OperationalError, psycopg2.InterfaceError, pool.PoolError)):
        return True
    text = str(error).lower()
    connection_markers = (
        "connection refused",
        "connection already closed",
        "server closed the connection",
        "terminating connection",
        "timeout expired",
        "could not connect",
        "connection pool",
        "ssl syscall error",
        "network is unreachable",
        "ssl connection closed unexpectedly",
        "ssl error",
        "connection has been closed",
        "connection closed",
    )
    return any(marker in text for marker in connection_markers)


def _record_query_failure(error: Exception) -> None:
    if _is_connection_error(error):
        _NEON_BREAKER.failure(error)
    else:
        log_warning("neon_query_non_connection_error", error=str(error)[:240])


def safe_row_get(row: Any, key_or_index: Any, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key_or_index, default)
    try:
        return row[key_or_index]
    except (IndexError, KeyError, TypeError):
        return default

def _is_connection_alive(conn) -> bool:
    """Performs a lightweight ping on the connection."""
    if not conn or conn.closed:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception:
        return False

def _discard_broken_connection(conn):
    """Safely discards a broken connection from the pool (e.g. SSL closed)."""
    if not conn:
        return
    pool_inst = _POOL
    if not pool_inst:
        try: conn.close()
        except: pass
        return
    conn_id = id(conn)
    _CONN_CREATED_AT.pop(conn_id, None)
    try:
        pool_inst.putconn(conn, close=True)
        log_info("neon_conn_recycled", reason="ssl_connection_closed")
    except Exception:
        try: conn.close()
        except: pass

def _pool_instance():
    """Returns the singleton connection pool instance, initializing if needed."""
    global _POOL
    if not DATABASE_URL:
        return None
        
    if not _NEON_BREAKER.allow():
        return None

    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                try:
                    # Debug: log the optimized DSN masked for diagnosis (no secrets)
                    try:
                        from urllib.parse import urlparse
                        optimized = _optimize_dsn(DATABASE_URL) or ""
                        p = urlparse(optimized)
                        host = p.hostname or ''
                        db = p.path.lstrip('/')
                        # If the optimized DSN does not look like a Postgres URL
                        # (no postgres scheme or no hostname) then skip pool
                        # initialization rather than passing an invalid DSN to
                        # psycopg2 which previously caused errors like
                        # "missing \"=\" after \"SET\" in connection info string".
                        scheme = (p.scheme or '').lower()
                        if scheme not in ('postgres', 'postgresql') or not host:
                            log_warning("neon_pool_init_skipped_invalid_dsn", host=host, db=db)
                            return None
                        log_info("neon_pool_init_dsn", host=host, db=db)
                    except Exception:
                        pass
                    start_time = time.perf_counter()
                    _POOL = pool.ThreadedConnectionPool(
                        minconn=POOL_MIN,
                        maxconn=POOL_MAX,
                        **_get_dsn_kwargs()
                    )
                    latency = (time.perf_counter() - start_time) * 1000
                    log_info("neon_pool_initialized", minconn=POOL_MIN, maxconn=POOL_MAX, latency_ms=latency)
                    log_metric("db.pool.init_ms", latency)
                except Exception as e:
                    _NEON_BREAKER.failure(e)
                    log_error("neon_pool_init_failed", error=e)
                    return None
    return _POOL

def get_connection(timeout_ms: int = 5000, **kwargs):
    """
    Acquires a connection from the pool.
    Includes recycling logic. Pre-ping removed for performance.
    """
    # Backward compatibility for statement_timeout_ms
    timeout_ms = kwargs.get("statement_timeout_ms", timeout_ms)
    
    pool_inst = _pool_instance()
    if not pool_inst:
        raise CircuitOpenError("Database connection pool is unavailable")

    conn = None
    now = time.time()
    
    # Try to get a healthy connection
    for attempt in range(2):
        try:
            conn = pool_inst.getconn()
            conn_id = id(conn)
            
            # Connection Recycling
            created_at = _CONN_CREATED_AT.get(conn_id, 0)
            if created_at > 0 and (now - created_at) > POOL_RECYCLE:
                pool_inst.putconn(conn, close=True)
                _CONN_CREATED_AT.pop(conn_id, None)
                conn = pool_inst.getconn()
                conn_id = id(conn)
                _CONN_CREATED_AT[conn_id] = now
            
            if conn_id not in _CONN_CREATED_AT:
                _CONN_CREATED_AT[conn_id] = now

            # Configure connection timeouts
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {int(timeout_ms)}")
                
            return conn
            
        except Exception as e:
            if conn:
                try: pool_inst.putconn(conn, close=True)
                except: pass
                _CONN_CREATED_AT.pop(id(conn), None)
            
            if attempt == 1:
                _NEON_BREAKER.failure(e)
                log_error("neon_conn_acquire_failed", error=e)
                raise NeonError(f"Failed to acquire database connection: {e}")
            
            time.sleep(0.01)

def release_connection(conn):
    """Safely returns a connection to the pool."""
    if not conn:
        return
    pool_inst = _POOL
    if not pool_inst:
        try: conn.close()
        except: pass
        return
    
    try:
        # Ensure any pending transaction is rolled back before returning
        if not conn.autocommit:
            conn.rollback()
        pool_inst.putconn(conn)
    except Exception as e:
        log_error("neon_conn_release_failed", error=e)
        try:
            pool_inst.putconn(conn, close=True)
        except: pass

def _run_query(sql_text, params: Any = None, fetch: str = "all", timeout_ms: int = 2000):
    """Internal runner with connection management.
    
    Args:
        sql_text: SQL query string or psycopg2.sql.Composable object
        params: Query parameters (tuple or list)
        fetch: Fetch mode ("all", "one", "write", or "none")
        timeout_ms: Query timeout in milliseconds
    """
    global _LAST_SUCCESS_AT
    conn = None
    start_time = time.perf_counter()
    try:
        conn = get_connection(timeout_ms=timeout_ms)
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql_text, params)
                _NEON_BREAKER.success()
                _LAST_SUCCESS_AT = time.time()
                
                latency = (time.perf_counter() - start_time) * 1000
                if latency > 500:
                    # Convert Composable to string for fingerprinting if needed
                    sql_str = str(sql_text) if isinstance(sql_text, sql.Composable) else sql_text
                    fp = sql_fingerprint(sql_str)
                    if should_log(fp):
                        log_warning("neon_slow_query", sql=sql_str[:200], latency_ms=latency)
                
                # Automatically fetch if RETURNING is present, or if explicitly requested
                sql_str = str(sql_text) if isinstance(sql_text, sql.Composable) else sql_text
                is_returning = "RETURNING" in sql_str.upper()
                
                if fetch == "all" or (fetch == "write" and is_returning):
                    return [dict(row) for row in cur.fetchall()]
                if fetch == "one":
                    row = cur.fetchone()
                    return dict(row) if row else None
                
                # Some cursor implementations may not expose rowcount reliably;
                # fall back to None to avoid AttributeError and let callers handle it.
                return {"rowcount": getattr(cur, "rowcount", None)}
                
    except Exception as e:
        error_text = str(e).lower()
        is_ssl_closed = "ssl connection closed unexpectedly" in error_text or "connection closed" in error_text
        if is_ssl_closed and conn:
            _discard_broken_connection(conn)
            conn = None  # prevent double-release
            log_info("neon_ssl_closed_detected", sql=str(sql_text)[:100])
            # Retry once with fresh connection
            try:
                conn = get_connection(timeout_ms=timeout_ms)
                with conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(sql_text, params)
                        _NEON_BREAKER.success()
                        _LAST_SUCCESS_AT = time.time()
                        sql_str = str(sql_text) if isinstance(sql_text, sql.Composable) else sql_text
                        if fetch == "all" or (fetch == "write" and "RETURNING" in sql_str.upper()):
                            return [dict(row) for row in cur.fetchall()]
                        if fetch == "one":
                            row = cur.fetchone()
                            return dict(row) if row else None
                        # Same safe access for rowcount on retry path.
                        return {"rowcount": getattr(cur, "rowcount", None)}
            except Exception as retry_e:
                _record_query_failure(retry_e)
                log_error("neon_ssl_retry_failed", error=retry_e, sql=str(sql_text)[:100])
                if fetch == "write":
                    raise NeonWriteError(str(retry_e))
                return [] if fetch == "all" else None
        _record_query_failure(e)
        log_error("neon_query_error", error=e, sql=str(sql_text)[:200])
        if fetch == "write":
            raise NeonWriteError(str(e))
        return [] if fetch == "all" else None
    finally:
        if conn:
            release_connection(conn)

_run = _run_query

def fast_query(sql_text, params: Any = None, timeout_ms: int = 10000, default: Any = None):
    """Route-safe query helper with strict timeout protection.
    
    Args:
        sql_text: SQL query string or psycopg2.sql.Composable object
        params: Query parameters (tuple or list)
        timeout_ms: Query timeout in milliseconds
        default: Default value to return on failure
    """
    if not _NEON_BREAKER.allow():
        return default if default is not None else []

    # Early exit for simple health check pings in fast local mode
    if not _is_production_env() and _flag_enabled("CHAIN_FAST_LOCAL"):
        sql_str = str(sql_text) if isinstance(sql_text, sql.Composable) else sql_text
        if sql_str.strip().upper() == "SELECT 1":
            return [{"?column?": 1}] if default is None else default

    future = _DB_EXECUTOR.submit(_run, sql_text, params, "all", timeout_ms)
    try:
        results = future.result(timeout=timeout_ms / 1000.0)
        return results if results is not None else (default if default is not None else [])
    except (FutureTimeoutError, Exception) as e:
        if isinstance(e, FutureTimeoutError):
            sql_str = str(sql_text) if isinstance(sql_text, sql.Composable) else sql_text
            log_warning("neon_wall_timeout", timeout_ms=timeout_ms, sql=sql_str[:100])
        return default if default is not None else []

def write_query(sql_text, params: Any = None, timeout_ms: int = 5000):
    """Transaction-safe write helper."""
    return _run_query(sql_text, params, fetch="write", timeout_ms=timeout_ms)

def transaction_query(callback, timeout_ms=10000):
    """Runs a series of operations in a single transaction."""
    global _LAST_SUCCESS_AT
    conn = None
    try:
        conn = get_connection(timeout_ms=timeout_ms)
        conn.autocommit = False
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                result = callback(cur)
                conn.commit()
                _NEON_BREAKER.success()
                _LAST_SUCCESS_AT = time.time()
                return result
    except Exception as e:
        if conn: conn.rollback()
        _record_query_failure(e)
        log_error("neon_transaction_failed", error=e)
        raise NeonWriteError(str(e))
    finally:
        if conn:
            conn.autocommit = True
            release_connection(conn)

def fetch_all(query, params=None, timeout_ms=2000):
    return _run_query(query, params, "all", timeout_ms)

def fetch_one(query, params=None, timeout_ms=2000):
    return _run_query(query, params, "one", timeout_ms)

def execute(query, params=None, timeout_ms=2000):
    return _run_query(query, params, "none", timeout_ms)

def get_neon_health():
    """Detailed health check for Neon connectivity with caching."""
    now = time.time()
    if _HEALTH_CACHE["payload"] and _HEALTH_CACHE["expires_at"] > now:
        return _HEALTH_CACHE["payload"]

    is_local_fast = not _is_production_env() and (_flag_enabled("CHAIN_FAST_LOCAL") or _flag_enabled("CHAIN_DISABLE_DB_PING"))

    if is_local_fast:
        payload = {
            "status": "disabled",
            "connected": False,
            "latency_ms": 0,
            "circuit_state": _NEON_BREAKER.get_state(),
            "pool_ready": _POOL is not None,
            "configured": bool(DATABASE_URL),
            "ever_connected": _LAST_SUCCESS_AT > 0,
            "local_fast_mode": True,
        }
        _HEALTH_CACHE["payload"] = payload
        _HEALTH_CACHE["expires_at"] = now + 300 # 5 min cache for disabled state
        return payload

    try:
        start = time.perf_counter()
        res = fast_query("SELECT 1", timeout_ms=5000)
        latency = (time.perf_counter() - start) * 1000
        connected = bool(res)
        payload = {
            "status": "ok" if connected else "error",
            "connected": connected,
            "latency_ms": round(latency, 2),
            "circuit_state": _NEON_BREAKER.get_state(),
            "pool_ready": _POOL is not None,
            "configured": bool(DATABASE_URL),
            "ever_connected": _LAST_SUCCESS_AT > 0
        }
        _HEALTH_CACHE["payload"] = payload
        _HEALTH_CACHE["expires_at"] = now + 15 # 15s cache for health
        return payload
    except Exception as e:
        return {"status": "error", "error": str(e), "circuit_state": _NEON_BREAKER.get_state()}

def prime_neon_runtime():
    """Pre-warms the connection pool."""
    if not _is_production_env() and (_flag_enabled("CHAIN_FAST_LOCAL") or _flag_enabled("CHAIN_DISABLE_PREWARM") or _flag_enabled("CHAIN_DISABLE_DB_PING")):
        return None
    _DB_EXECUTOR.submit(_pool_instance)

def get_pool_status():
    """Returns basic pool status for monitoring."""
    return {
        "configured": bool(DATABASE_URL),
        "pool_ready": _POOL is not None,
        "circuit_open": not _NEON_BREAKER.allow(),
        "ever_connected": _LAST_SUCCESS_AT > 0,
        "recent_success": (time.time() - _LAST_SUCCESS_AT) < 60 if _LAST_SUCCESS_AT > 0 else False
    }

def table_exists(table_name: str, timeout_ms=2000):
    if os.getenv("CHAIN_TRUST_PROFILE_SCHEMA", "1") == "1":
        if table_name in CHAIN_STATIC_COLUMNS:
            return True

    cached = _TABLE_EXISTS_CACHE.get(table_name)
    now = time.time()
    if cached is not None and now < cached["expires_at"]:
        return cached["exists"]

    log_info("schema_cache_miss", table=table_name, kind="table_exists")
    query = "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relname = %s LIMIT 1"
    res = fast_query(query, (table_name,), timeout_ms=timeout_ms)
    exists = bool(res)
    _TABLE_EXISTS_CACHE[table_name] = {
        "exists": exists,
        "expires_at": now + _TABLE_EXISTS_CACHE_TTL,
    }
    return exists

def insert_row(table: str, payload: Dict[str, Any], returning: str = "id", timeout_ms: int = 2000):
    """Helper to insert a single row and return a column."""
    columns = list(payload.keys())
    values = list(payload.values())
    
    placeholders = ", ".join(["%s"] * len(columns))
    cols_str = ", ".join([f'"{c}"' for c in columns])
    
    sql_text = f'INSERT INTO "{table}" ({cols_str}) VALUES ({placeholders}) RETURNING {returning}'
    
    try:
        res = write_query(sql_text, values, timeout_ms=timeout_ms)
        if isinstance(res, list) and res:
            return res[0]
        return res
    except Exception as e:
        log_error("neon_insert_row_failed", table=table, error=e)
        return None

def fetch_one_with_connection(conn, query, params=None, timeout_ms=2000):
    """Fetches a single row using an existing connection."""
    try:
        if not conn:
            return None
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SET statement_timeout = {int(timeout_ms)}")
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        log_error("neon_fetch_one_conn_failed", error=e)
        return None

def fetch_all_with_connection(conn, query, params=None, timeout_ms=2000):
    """Fetches all rows using an existing connection."""
    try:
        if not conn:
            return []
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SET statement_timeout = {int(timeout_ms)}")
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        log_error("neon_fetch_all_conn_failed", error=e)
        return []

def get_tables_columns(table_names: List[str], timeout_ms=1000) -> Dict[str, List[str]]:
    """Retrieves column names for multiple tables."""
    results = {}
    if not table_names:
        return results
    
    # Simple loop; could be optimized with a single query if needed
    for table in table_names:
        results[table] = get_table_columns(table, timeout_ms=max(100, timeout_ms // len(table_names)))
    return results

# Aliases for backward compatibility

def is_circuit_open():
    """Returns True if the Neon circuit breaker is open (blocking requests)."""
    return not _NEON_BREAKER.allow()


def get_cached_table_columns(table_name: str, timeout_ms=5000):
    """Cached wrapper for table columns to avoid pg_attribute checks during requests."""
    static_cols = CHAIN_STATIC_COLUMNS.get(table_name)
    if static_cols:
        log_info("schema_cache_static_hit", table=table_name, kind="columns")
        return set(static_cols)
    return get_table_columns(table_name, timeout_ms=timeout_ms)