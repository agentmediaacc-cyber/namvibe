import os
import time

try:
    from postgrest.exceptions import APIError
except Exception:  # pragma: no cover
    class APIError(Exception):
        pass

from utils.supabase_client import get_supabase_admin


_COLUMN_CACHE = {}
_TABLE_EXISTS_CACHE = {}
_WARNED_MESSAGES = set()
_SCHEMA_CACHE_TTL = 3600 * 24 # 24 hours


def prime_supabase_schema(table_names):
    """Pre-loads columns and existence for Supabase tables."""
    for table in table_names:
        table_exists(table)
        _load_columns(table)


def _fast_local_enabled():
    return os.getenv("CHAIN_FAST_LOCAL") == "1" and os.getenv("FLASK_ENV", "development") != "production"


def _schema_log(event, table, kind):
    if os.getenv("SUPABASE_SAFE_DEBUG") == "1" or _fast_local_enabled():
        print(f"[supabase_safe] {event} table={table} kind={kind}")


def _is_api_error(error):
    return isinstance(error, APIError) or error.__class__.__name__ == "APIError"


def _warn_once(key, message):
    if key in _WARNED_MESSAGES:
        return
    _WARNED_MESSAGES.add(key)
    if os.getenv("SUPABASE_SAFE_DEBUG") == "1":
        print(message)


def _apply_filters(query, filters):
    if not filters:
        return query

    for column, raw_value in filters.items():
        operator = "eq"
        value = raw_value

        if isinstance(raw_value, tuple) and len(raw_value) == 2:
            operator, value = raw_value

        if operator == "eq":
            query = query.eq(column, value)
        elif operator == "neq":
            query = query.neq(column, value)
        elif operator == "gt":
            query = query.gt(column, value)
        elif operator == "gte":
            query = query.gte(column, value)
        elif operator == "lt":
            query = query.lt(column, value)
        elif operator == "lte":
            query = query.lte(column, value)
        elif operator == "like":
            query = query.like(column, value)
        elif operator == "ilike":
            query = query.ilike(column, value)
        elif operator == "in":
            query = query.in_(column, value)
        elif operator == "is":
            query = query.is_(column, value)
        elif operator == "not.is":
            query = query.not_.is_(column, value)
        elif operator == "contains":
            query = query.contains(column, value)
        else:
            raise ValueError(f"Unsupported filter operator: {operator}")

    return query


def table_exists(table):
    now = time.time()
    if table in _TABLE_EXISTS_CACHE:
        entry = _TABLE_EXISTS_CACHE[table]
        if isinstance(entry, dict) and entry.get("expires_at", 0) > now:
            _schema_log("schema_cache_hit", table, "table_exists")
            return entry["exists"]
        if isinstance(entry, bool):
            _schema_log("schema_cache_hit", table, "table_exists")
            return entry

    _schema_log("schema_cache_miss", table, "table_exists")
    if _fast_local_enabled():
        _schema_log("schema_check_skipped_fast_local", table, "table_exists")
        _TABLE_EXISTS_CACHE[table] = {"exists": False, "expires_at": now + _SCHEMA_CACHE_TTL}
        return False

    try:
        admin = get_supabase_admin()
        admin.table(table).select("id").limit(1).execute()
        _TABLE_EXISTS_CACHE[table] = {"exists": True, "expires_at": now + _SCHEMA_CACHE_TTL}
        return True
    except Exception as error:
        if _is_api_error(error):
            _warn_once(f"table:{table}:api", f"[supabase_safe] table_exists({table}) -> False: {error}")
            _TABLE_EXISTS_CACHE[table] = {"exists": False, "expires_at": now + _SCHEMA_CACHE_TTL}
            return False
        _warn_once(f"table:{table}:transport", f"[supabase_safe] table_exists({table}) failed: {error}")
        _TABLE_EXISTS_CACHE[table] = {"exists": False, "expires_at": now + _SCHEMA_CACHE_TTL}
        return False


def _load_columns(table):
    now = time.time()
    if table in _COLUMN_CACHE:
        entry = _COLUMN_CACHE[table]
        if isinstance(entry, dict) and entry.get("expires_at", 0) > now:
            _schema_log("schema_cache_hit", table, "columns")
            return entry["columns"]
        if isinstance(entry, set):
            _schema_log("schema_cache_hit", table, "columns")
            return entry

    _schema_log("schema_cache_miss", table, "columns")
    if _fast_local_enabled():
        _schema_log("schema_check_skipped_fast_local", table, "columns")
        _COLUMN_CACHE[table] = {"columns": set(), "expires_at": now + _SCHEMA_CACHE_TTL}
        return set()

    admin = get_supabase_admin()
    columns = set()
    try:
        response = (
            admin.table("information_schema.columns")
            .select("column_name")
            .eq("table_schema", "public")
            .eq("table_name", table)
            .limit(500)
            .execute()
        )
        columns = {row["column_name"] for row in (response.data or []) if row.get("column_name")}
    except Exception:
        columns = set()

    _COLUMN_CACHE[table] = {"columns": columns, "expires_at": now + _SCHEMA_CACHE_TTL}
    return columns


def column_safe_payload(table, payload, fallback_columns=None):
    if payload is None:
        return {}

    safe_payload = {key: value for key, value in payload.items() if value is not None}
    known_columns = _load_columns(table)

    if known_columns:
        return {key: value for key, value in safe_payload.items() if key in known_columns}

    if fallback_columns:
        fallback_set = set(fallback_columns)
        return {key: value for key, value in safe_payload.items() if key in fallback_set}

    return safe_payload


def safe_select(table, columns="*", limit=20, filters=None, order_by="created_at", desc=True):
    if not table_exists(table):
        return []

    admin = get_supabase_admin()

    def build_query(include_order=True):
        query = admin.table(table).select(columns)
        query = _apply_filters(query, filters)
        if include_order and order_by:
            query = query.order(order_by, desc=desc)
        if limit is not None:
            query = query.limit(limit)
        return query

    try:
        return build_query(include_order=True).execute().data or []
    except Exception as first_error:
        if order_by:
            try:
                return build_query(include_order=False).execute().data or []
            except Exception as second_error:
                _warn_once(f"select:{table}", f"[supabase_safe] safe_select({table}) failed: {second_error}")
                return []
        _warn_once(f"select:{table}", f"[supabase_safe] safe_select({table}) failed: {first_error}")
        return []


def safe_count(table, filters=None):
    if not table_exists(table):
        return 0

    try:
        admin = get_supabase_admin()
        query = admin.table(table).select("id", count="exact").limit(1)
        query = _apply_filters(query, filters)
        result = query.execute()
        return result.count or 0
    except Exception as error:
        _warn_once(f"count:{table}", f"[supabase_safe] safe_count({table}) failed: {error}")
        return 0


def safe_insert(table, payload, fallback_columns=None):
    if not table_exists(table):
        return None

    try:
        admin = get_supabase_admin()
        safe_payload = column_safe_payload(table, payload, fallback_columns=fallback_columns)
        if safe_payload in ({}, []):
            return []
        result = admin.table(table).insert(safe_payload).execute()
        return result.data if result.data is not None else []
    except Exception as error:
        _warn_once(f"insert:{table}", f"[supabase_safe] safe_insert({table}) failed: {error}")
        return None


def safe_update(table, payload, eq=None, fallback_columns=None):
    if not table_exists(table):
        return None

    try:
        admin = get_supabase_admin()
        safe_payload = column_safe_payload(table, payload, fallback_columns=fallback_columns)
        if not safe_payload:
            return []
        query = admin.table(table).update(safe_payload)
        query = _apply_filters(query, eq)
        result = query.execute()
        return result.data if result.data is not None else []
    except Exception as error:
        _warn_once(f"update:{table}", f"[supabase_safe] safe_update({table}) failed: {error}")
        return None


def safe_delete(table, eq=None):
    if not table_exists(table):
        return None

    try:
        admin = get_supabase_admin()
        query = admin.table(table).delete()
        query = _apply_filters(query, eq)
        result = query.execute()
        return result.data if result.data is not None else []
    except Exception as error:
        _warn_once(f"delete:{table}", f"[supabase_safe] safe_delete({table}) failed: {error}")
        return None
