import os
from uuid import uuid4
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status

_FAKE_FLAGS = []


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1" or os.getenv("CHAIN_TEST_FAKE_DB") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _row(row):
    data = dict(row)
    data["id"] = str(data["id"])
    data["profile_id"] = str(data["profile_id"]) if data.get("profile_id") else None
    return data


def flag_content(profile_id, content_type, content_id, flag_type, severity="medium", flagged_by=None, reason=""):
    flag_id = str(uuid4())
    flag = {
        "id": flag_id,
        "profile_id": profile_id,
        "content_type": content_type,
        "content_id": content_id,
        "flag_type": flag_type,
        "severity": severity,
        "flagged_by": flagged_by,
        "reason": reason,
        "status": "active",
        "created_at": _now(),
        "resolved_at": None,
    }
    _FAKE_FLAGS.append(flag)
    if _db_available():
        write_query(
            "INSERT INTO chain_content_flags (id, profile_id, content_type, content_id, flag_type, severity, flagged_by, reason) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (flag_id, profile_id, content_type, content_id, flag_type, severity, flagged_by, reason)
        )
    return {"ok": True, "flag": flag}


def resolve_flag(flag_id, resolution="resolved"):
    for f in _FAKE_FLAGS:
        if f["id"] == flag_id:
            f["status"] = "resolved"
            f["resolved_at"] = _now()
    if _db_available():
        write_query("UPDATE chain_content_flags SET status='resolved', resolved_at=now() WHERE id=%s", (flag_id,))
    return {"ok": True}


def get_content_flags(content_type=None, content_id=None, status="active"):
    if not _db_available():
        results = list(_FAKE_FLAGS)
        if content_type:
            results = [f for f in results if f["content_type"] == content_type]
        if content_id:
            results = [f for f in results if f["content_id"] == content_id]
        if status:
            results = [f for f in results if f["status"] == status]
        return results
    where = []
    params = []
    if content_type:
        where.append("content_type = %s")
        params.append(content_type)
    if content_id:
        where.append("content_id = %s")
        params.append(content_id)
    if status:
        where.append("status = %s")
        params.append(status)
    sql = "SELECT * FROM chain_content_flags" + ((" WHERE " + " AND ".join(where)) if where else "") + " ORDER BY created_at DESC"
    rows = fast_query(sql, tuple(params), default=[])
    return [_row(r) for r in rows]


def is_content_flagged(content_type, content_id):
    if not _db_available():
        return any(f["content_type"] == content_type and f["content_id"] == content_id and f["status"] == "active" for f in _FAKE_FLAGS)
    rows = fast_query(
        "SELECT 1 FROM chain_content_flags WHERE content_type=%s AND content_id=%s AND status='active' LIMIT 1",
        (content_type, content_id), default=[]
    )
    return bool(rows)
