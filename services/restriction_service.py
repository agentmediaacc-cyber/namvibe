import os
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from services.neon_service import fast_query, write_query, get_pool_status

_FAKE_RESTRICTIONS = []


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1" or os.getenv("CHAIN_TEST_FAKE_DB") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _calculate_expires_at(duration_minutes):
    if duration_minutes:
        return (datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)).isoformat()
    return None


def _row(row):
    data = dict(row)
    data["id"] = str(data["id"])
    data["profile_id"] = str(data["profile_id"]) if data.get("profile_id") else None
    return data


def restrict_user(profile_id, restricted_by=None, restriction_type="temporary", reason="", duration_minutes=1440):
    restriction_id = str(uuid4())
    expires_at = _calculate_expires_at(duration_minutes)
    restriction = {
        "id": restriction_id,
        "profile_id": profile_id,
        "restricted_by": restricted_by,
        "restriction_type": restriction_type,
        "reason": reason,
        "status": "active",
        "duration_minutes": duration_minutes,
        "expires_at": expires_at,
        "created_at": _now(),
        "updated_at": _now(),
    }
    _FAKE_RESTRICTIONS.append(restriction)
    if _db_available():
        write_query(
            "INSERT INTO chain_restrictions (id, profile_id, restricted_by, restriction_type, reason, status, duration_minutes, expires_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (restriction_id, profile_id, restricted_by, restriction_type, reason, "active", duration_minutes, expires_at)
        )
    return {"ok": True, "restriction": restriction}


def unrestrict_user(profile_id):
    for r in _FAKE_RESTRICTIONS:
        if r["profile_id"] == profile_id and r["status"] == "active":
            r["status"] = "removed"
            r["updated_at"] = _now()
    if _db_available():
        write_query("UPDATE chain_restrictions SET status='removed', updated_at=now() WHERE profile_id=%s AND status='active'", (profile_id,))
    return {"ok": True}


def is_restricted(profile_id):
    now_iso = _now()
    if not _db_available():
        for r in _FAKE_RESTRICTIONS:
            if r["profile_id"] == profile_id and r["status"] == "active":
                if r["expires_at"] is None or r["expires_at"] > now_iso:
                    return True
        return False
    rows = fast_query(
        "SELECT 1 FROM chain_restrictions WHERE profile_id=%s AND status='active' AND (expires_at IS NULL OR expires_at > now()) LIMIT 1",
        (profile_id,), default=[]
    )
    return bool(rows)


def get_active_restrictions(profile_id):
    now_iso = _now()
    if not _db_available():
        return [r for r in _FAKE_RESTRICTIONS if r["profile_id"] == profile_id and r["status"] == "active" and (r["expires_at"] is None or r["expires_at"] > now_iso)]
    rows = fast_query(
        "SELECT * FROM chain_restrictions WHERE profile_id=%s AND status='active' AND (expires_at IS NULL OR expires_at > now()) ORDER BY created_at DESC",
        (profile_id,), default=[]
    )
    return [_row(r) for r in rows]


def get_restriction_history(profile_id):
    if not _db_available():
        return [r for r in _FAKE_RESTRICTIONS if r["profile_id"] == profile_id]
    rows = fast_query(
        "SELECT * FROM chain_restrictions WHERE profile_id=%s ORDER BY created_at DESC",
        (profile_id,), default=[]
    )
    return [_row(r) for r in rows]


def expire_restrictions():
    now_iso = _now()
    for r in _FAKE_RESTRICTIONS:
        if r["status"] == "active" and r["expires_at"] and r["expires_at"] < now_iso:
            r["status"] = "expired"
            r["updated_at"] = now_iso
    if _db_available():
        write_query("UPDATE chain_restrictions SET status='expired', updated_at=now() WHERE status='active' AND expires_at < now()", ())
    return {"ok": True}
