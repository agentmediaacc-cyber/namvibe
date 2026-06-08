import json
import os
import random
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status
from services.logging_service import log_info

_PT_COLS = "id, profile_id, device_session_id, platform, token, active, created_at, updated_at"


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _row_to_token(row):
    return {
        "id": str(row["id"]),
        "profile_id": str(row["profile_id"]),
        "device_session_id": str(row["device_session_id"]) if row.get("device_session_id") else None,
        "platform": row.get("platform") or "web",
        "token": row.get("token") or "",
        "active": bool(row.get("active", True)),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def register_push_token(profile_id, token, platform="web", device_session_id=None):
    if not profile_id or not token:
        return {"ok": False, "error": "missing_fields"}
    try:
        if _db_available():
            sel_sql = "SELECT id FROM chain_push_tokens WHERE profile_id = %s AND token = %s LIMIT 1"
            if random.random() < 0.01:
                plan = fast_query("EXPLAIN ANALYZE " + sel_sql, (profile_id, token), timeout_ms=3000, default=[])
                if plan:
                    log_info("explain_analyze_push_token", plan="\n".join(r["QUERY PLAN"] for r in plan), profile_id=profile_id)
            existing = fast_query(sel_sql, (profile_id, token), default=[])
            if existing:
                write_query(
                    "UPDATE chain_push_tokens SET active = true, platform = %s, device_session_id = %s, updated_at = now() WHERE id = %s",
                    (platform, device_session_id, existing[0]["id"]),
                )
            else:
                write_query(
                    "INSERT INTO chain_push_tokens (profile_id, token, platform, device_session_id) VALUES (%s, %s, %s, %s)",
                    (profile_id, token, platform, device_session_id),
                )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def remove_push_token(profile_id, token):
    if not profile_id or not token:
        return {"ok": False, "error": "missing_fields"}
    try:
        if _db_available():
            write_query(
                "UPDATE chain_push_tokens SET active = false, updated_at = now() WHERE profile_id = %s AND token = %s",
                (profile_id, token),
            )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def deactivate_push_token(profile_id, token):
    return remove_push_token(profile_id, token)


def get_push_tokens(profile_id):
    if not profile_id:
        return []
    try:
        if _db_available():
            rows = fast_query(
                f"SELECT {_PT_COLS} FROM chain_push_tokens WHERE profile_id = %s ORDER BY created_at DESC",
                (profile_id,),
                default=[],
            )
            return [_row_to_token(r) for r in rows]
        return []
    except Exception:
        return []


def get_active_push_tokens(profile_id):
    if not profile_id:
        return []
    try:
        if _db_available():
            rows = fast_query(
                f"SELECT {_PT_COLS} FROM chain_push_tokens WHERE profile_id = %s AND active = true ORDER BY created_at DESC",
                (profile_id,),
                default=[],
            )
            return [_row_to_token(r) for r in rows]
        return []
    except Exception:
        return []
