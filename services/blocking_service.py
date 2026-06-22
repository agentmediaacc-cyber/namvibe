"""Blocking Service — safe block detection with dynamic schema discovery.

Avoids querying chain_profiles.blocked_profile_ids unless the column exists.
Prefers the chain_blocks table with soft-delete support.
Never crashes or logs errors for missing columns/tables.
"""

from typing import List, Optional

import re

from functools import lru_cache

from services.neon_service import fast_query, get_table_columns, table_exists, write_query

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def is_uuid(s):
    return bool(_UUID_RE.match(str(s))) if s else False


@lru_cache(maxsize=1)
def _blocks_table() -> str:
    """Detect available block table. Returns table name or empty string."""
    table = "chain_blocks"
    try:
        if not table_exists(table):
            return ""
        cols = set(get_table_columns(table) or [])
        if {"blocker_profile_id", "blocked_profile_id"}.issubset(cols):
            return table
    except Exception:
        return ""
    return ""


@lru_cache(maxsize=8)
def _has_deleted_at(table: str) -> bool:
    try:
        return "deleted_at" in set(get_table_columns(table) or [])
    except Exception:
        return False


def is_blocked(profile_id, target_profile_id) -> bool:
    """Check if profile_id has blocked target_profile_id (one direction)."""
    if not is_uuid(profile_id) or not is_uuid(target_profile_id):
        return False
    table = _blocks_table()
    if not table:
        return False
    try:
        if _has_deleted_at(table):
            rows = fast_query(
                f"SELECT 1 FROM {table} WHERE blocker_profile_id = %s AND blocked_profile_id = %s AND deleted_at IS NULL LIMIT 1",
                (profile_id, target_profile_id), timeout_ms=5000, default=[]
            )
        else:
            rows = fast_query(
                f"SELECT 1 FROM {table} WHERE blocker_profile_id = %s AND blocked_profile_id = %s LIMIT 1",
                (profile_id, target_profile_id), timeout_ms=5000, default=[]
            )
        return bool(rows)
    except Exception:
        return False


def is_blocked_any(profile_id, target_profile_id) -> bool:
    """Check if either profile has blocked the other (bidirectional)."""
    if not is_uuid(profile_id) or not is_uuid(target_profile_id):
        return False
    table = _blocks_table()
    if not table:
        return False
    try:
        if _has_deleted_at(table):
            rows = fast_query(
                f"SELECT 1 FROM {table} WHERE ((blocker_profile_id = %s AND blocked_profile_id = %s) OR (blocker_profile_id = %s AND blocked_profile_id = %s)) AND deleted_at IS NULL LIMIT 1",
                (profile_id, target_profile_id, target_profile_id, profile_id), timeout_ms=5000, default=[]
            )
        else:
            rows = fast_query(
                f"SELECT 1 FROM {table} WHERE (blocker_profile_id = %s AND blocked_profile_id = %s) OR (blocker_profile_id = %s AND blocked_profile_id = %s) LIMIT 1",
                (profile_id, target_profile_id, target_profile_id, profile_id), timeout_ms=5000, default=[]
            )
        return bool(rows)
    except Exception:
        return False


def get_blocked_ids(profile_id: str) -> List[str]:
    """Return list of profile IDs that this profile has blocked."""
    if not is_uuid(profile_id):
        return []
    table = _blocks_table()
    if not table:
        return []
    try:
        if _has_deleted_at(table):
            rows = fast_query(
                f"SELECT blocked_profile_id FROM {table} WHERE blocker_profile_id = %s AND deleted_at IS NULL",
                (profile_id,), timeout_ms=5000, default=[]
            )
        else:
            rows = fast_query(
                f"SELECT blocked_profile_id FROM {table} WHERE blocker_profile_id = %s",
                (profile_id,), timeout_ms=5000, default=[]
            )
        return [str(r["blocked_profile_id"]) for r in rows if r.get("blocked_profile_id")]
    except Exception:
        return []


def block_user(blocker_id: str, blocked_id: str) -> dict:
    """Block a user. Returns {'ok': True/False, 'error': optional}."""
    if not is_uuid(blocker_id) or not is_uuid(blocked_id):
        return {"ok": False, "error": "invalid_id"}
    if blocker_id == blocked_id:
        return {"ok": False, "error": "cannot_block_self"}
    table = _blocks_table()
    if not table:
        return {"ok": False, "error": "blocks_table_unavailable"}
    try:
        write_query(
            f"INSERT INTO {table} (blocker_profile_id, blocked_profile_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (blocker_id, blocked_id)
        )
        from services.relationship_cache_service import invalidate_relationship_state
        invalidate_relationship_state(blocker_id, blocked_id)
        invalidate_relationship_state(blocked_id, blocker_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def unblock_user(blocker_id: str, blocked_id: str) -> dict:
    """Unblock a user. Returns {'ok': True/False, 'error': optional}."""
    if not is_uuid(blocker_id) or not is_uuid(blocked_id):
        return {"ok": False, "error": "invalid_id"}
    table = _blocks_table()
    if not table:
        return {"ok": False, "error": "blocks_table_unavailable"}
    try:
        if _has_deleted_at(table):
            write_query(
                f"UPDATE {table} SET deleted_at = now() WHERE blocker_profile_id = %s AND blocked_profile_id = %s AND deleted_at IS NULL",
                (blocker_id, blocked_id)
            )
        else:
            write_query(
                f"DELETE FROM {table} WHERE blocker_profile_id = %s AND blocked_profile_id = %s",
                (blocker_id, blocked_id)
            )
        from services.relationship_cache_service import invalidate_relationship_state
        invalidate_relationship_state(blocker_id, blocked_id)
        invalidate_relationship_state(blocked_id, blocker_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
