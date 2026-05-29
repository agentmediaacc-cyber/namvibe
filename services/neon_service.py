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

from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool, sql, extensions
from psycopg2.extras import Json, RealDictCursor
from services.circuit_breaker import CircuitBreaker
from services.logging_service import log_error, log_warning, log_info, log_metric

load_dotenv(dotenv_path=".env")

# Configuration from Environment
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
POOL_MIN = int(os.getenv("DB_POOL_MIN", "2"))
POOL_MAX = int(os.getenv("DB_POOL_MAX", "15"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "300")) # 5 minutes
STATEMENT_TIMEOUT_DEFAULT = int(os.getenv("DB_STATEMENT_TIMEOUT", "5000"))

# State Management
_POOL = None
_POOL_LOCK = threading.Lock()
_CONN_CREATED_AT = {} # id(conn) -> float (timestamp)
_LAST_SUCCESS_AT = 0.0
_NEON_BREAKER = CircuitBreaker("neon", failure_threshold=5, recovery_seconds=30)
_DB_EXECUTOR = ThreadPoolExecutor(max_workers=POOL_MAX + 5, thread_name_prefix="neon_db")

# Caches
_COLUMN_CACHE = {}
_COLUMN_CACHE_TTL = 300
_HEALTH_CACHE = {"expires_at": 0.0, "payload": None}

class NeonError(Exception):
    """Base exception for Neon service errors."""
    pass

class NeonWriteError(NeonError):
    pass

class CircuitOpenError(NeonError):
    pass

def _optimize_dsn(url: str) -> str:
    """Optimizes Neon connection URL for stability and pooling."""
    if not url:
        return url
    
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    
    # Optimization 1: Use Neon pooler if missing and host matches pattern
    if "neon.tech" in hostname and "-pooler" not in hostname:
        parts = hostname.split('.')
        # Standard Neon hostname: [project-id].[region].aws.neon.tech
        if len(parts) >= 4 and parts[-3:] == ['aws', 'neon', 'tech']:
            parts[0] = f"{parts[0]}-pooler"
            new_hostname = ".".join(parts)
            url = url.replace(hostname, new_hostname)
            parsed = urlparse(url)
    
    # Optimization 2: Force SSL and set common parameters
    query = dict(parse_qsl(parsed.query))
    query["sslmode"] = "require"
    query["application_name"] = "chain_app_backend"
    query["connect_timeout"] = "5"
    
    # TCP Keepalives for long-lived pool connections
    query["keepalives"] = "1"
    query["keepalives_idle"] = "30"
    query["keepalives_interval"] = "10"
    query["keepalives_count"] = "5"
    
    parsed = parsed._replace(query=urlencode(query))
    return urlunparse(parsed)

def _get_dsn_kwargs():
    """Returns kwargs for psycopg2 connection."""
    optimized_url = _optimize_dsn(DATABASE_URL)
    return {
        "dsn": optimized_url,
        "cursor_factory": RealDictCursor
    }

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
    Acquires a healthy connection from the pool.
    Includes pre-ping and recycling logic.
    """
    # Backward compatibility for statement_timeout_ms
    timeout_ms = kwargs.get("statement_timeout_ms", timeout_ms)
    
    pool_inst = _pool_instance()
    if not pool_inst:
        raise CircuitOpenError("Database connection pool is unavailable (circuit open or unconfigured)")

    conn = None
    now = time.time()
    
    # Try to get a healthy connection
    for attempt in range(3):
        try:
            conn = pool_inst.getconn()
            conn_id = id(conn)
            
            # 1. Connection Recycling (if too old, discard and get another)
            created_at = _CONN_CREATED_AT.get(conn_id, 0)
            if created_at > 0 and (now - created_at) > POOL_RECYCLE:
                log_info("neon_conn_recycle", age_sec=int(now - created_at))
                pool_inst.putconn(conn, close=True)
                _CONN_CREATED_AT.pop(conn_id, None)
                conn = pool_inst.getconn()
                conn_id = id(conn)
                _CONN_CREATED_AT[conn_id] = now
            
            # Track new connections
            if conn_id not in _CONN_CREATED_AT:
                _CONN_CREATED_AT[conn_id] = now

            # 2. Pre-Ping (verify connection is alive)
            if not _is_connection_alive(conn):
                log_warning("neon_conn_dead_on_checkout")
                pool_inst.putconn(conn, close=True)
                _CONN_CREATED_AT.pop(conn_id, None)
                continue # Try again
                
            # 3. Configure connection timeouts
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {int(timeout_ms)}")
                cur.execute("SET idle_in_transaction_session_timeout = '30s'")
                
            return conn
            
        except Exception as e:
            if conn:
                try:
                    pool_inst.putconn(conn, close=True)
                except: pass
                _CONN_CREATED_AT.pop(id(conn), None)
            
            if attempt == 2:
                _NEON_BREAKER.failure(e)
                log_error("neon_conn_acquire_failed", error=e, attempt=attempt+1)
                raise NeonError(f"Failed to acquire database connection: {e}")
            
            time.sleep(0.05 * (attempt + 1)) # Small backoff

def release_connection(conn):
    """Safely returns a connection to the pool."""
    if not conn:
        return
    pool_inst = _pool_instance()
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

def _run_query(sql_text: str, params: Any = None, fetch: str = "all", timeout_ms: int = 2000):
    """Internal runner with connection management."""
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
                    log_warning("neon_slow_query", sql=sql_text[:200], latency_ms=latency)
                
                # Automatically fetch if RETURNING is present, or if explicitly requested
                is_returning = "RETURNING" in sql_text.upper()
                
                if fetch == "all" or (fetch == "write" and is_returning):
                    return [dict(row) for row in cur.fetchall()]
                if fetch == "one":
                    row = cur.fetchone()
                    return dict(row) if row else None
                
                return {"rowcount": cur.rowcount}
                
    except Exception as e:
        _NEON_BREAKER.failure(e)
        log_error("neon_query_error", error=e, sql=sql_text[:200])
        if fetch == "write":
            raise NeonWriteError(str(e))
        return [] if fetch == "all" else None
    finally:
        release_connection(conn)

def fast_query(sql_text: str, params: Any = None, timeout_ms: int = 500, default: Any = None):
    """Route-safe query helper with strict timeout protection."""
    if not _NEON_BREAKER.allow():
        return default if default is not None else []

    future = _DB_EXECUTOR.submit(_run_query, sql_text, params, "all", timeout_ms)
    try:
        results = future.result(timeout=timeout_ms / 1000.0)
        return results if results is not None else (default if default is not None else [])
    except (FutureTimeoutError, Exception) as e:
        if isinstance(e, FutureTimeoutError):
            log_warning("neon_wall_timeout", timeout_ms=timeout_ms, sql=sql_text[:100])
        return default if default is not None else []

def write_query(sql_text: str, params: Any = None, timeout_ms: int = 5000):
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
        _NEON_BREAKER.failure(e)
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

    try:
        start = time.perf_counter()
        res = fast_query("SELECT 1", timeout_ms=500)
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

def get_table_columns(table_name: str, timeout_ms=500):
    """Retrieves column names for a table with local caching."""
    now = time.time()
    if table_name in _COLUMN_CACHE:
        entry = _COLUMN_CACHE[table_name]
        if now < entry["expires_at"]:
            return entry["columns"]

    query = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s AND table_schema = 'public'
    """
    rows = fast_query(query, (table_name,), timeout_ms=timeout_ms)
    columns = [r["column_name"] for r in rows] if rows else []
    
    if columns:
        _COLUMN_CACHE[table_name] = {
            "columns": columns,
            "expires_at": now + _COLUMN_CACHE_TTL
        }
    return columns

def is_circuit_open():
    return not _NEON_BREAKER.allow()

def table_exists(table_name: str, timeout_ms=500):
    """Checks if a table exists in the public schema."""
    query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        )
    """
    res = fast_query(query, (table_name,), timeout_ms=timeout_ms)
    return res[0]["exists"] if res else False

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
get_cached_table_columns = get_table_columns
