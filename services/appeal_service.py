import os
from uuid import uuid4
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status

_FAKE_APPEALS = []


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


def submit_appeal(profile_id, appeal_type, target_id, reason, details=""):
    appeal_id = str(uuid4())
    appeal = {
        "id": appeal_id,
        "profile_id": profile_id,
        "appeal_type": appeal_type,
        "target_id": target_id,
        "reason": reason,
        "details": details,
        "status": "pending",
        "reviewer_id": None,
        "resolution_note": None,
        "created_at": _now(),
        "reviewed_at": None,
    }
    _FAKE_APPEALS.append(appeal)
    if _db_available():
        write_query(
            "INSERT INTO chain_appeals (id, profile_id, appeal_type, target_id, reason, details) VALUES (%s,%s,%s,%s,%s,%s)",
            (appeal_id, profile_id, appeal_type, target_id, reason, details)
        )
    return {"ok": True, "appeal": appeal}


def review_appeal(appeal_id, reviewer_id, status, resolution_note=""):
    for a in _FAKE_APPEALS:
        if a["id"] == appeal_id:
            a["status"] = status
            a["reviewer_id"] = reviewer_id
            a["resolution_note"] = resolution_note
            a["reviewed_at"] = _now()
    if _db_available():
        write_query(
            "UPDATE chain_appeals SET status=%s, reviewer_id=%s, resolution_note=%s, reviewed_at=now() WHERE id=%s",
            (status, reviewer_id, resolution_note, appeal_id)
        )
    return {"ok": True}


def get_user_appeals(profile_id):
    if not _db_available():
        return [a for a in _FAKE_APPEALS if a["profile_id"] == profile_id]
    rows = fast_query(
        "SELECT * FROM chain_appeals WHERE profile_id=%s ORDER BY created_at DESC",
        (profile_id,), default=[]
    )
    return [_row(r) for r in rows]


def get_pending_appeals(limit=50):
    if not _db_available():
        return [a for a in _FAKE_APPEALS if a["status"] == "pending"][:limit]
    rows = fast_query(
        "SELECT * FROM chain_appeals WHERE status='pending' ORDER BY created_at ASC LIMIT %s",
        (limit,), default=[]
    )
    return [_row(r) for r in rows]
