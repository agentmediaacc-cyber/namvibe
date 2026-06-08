import os
import json
from uuid import uuid4
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status

_FAKE_REQUESTS = []


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1" or os.getenv("CHAIN_TEST_FAKE_DB") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _now():
    return datetime.now(timezone.utc).isoformat()


def submit_verification_request(creator_profile_id, submitted_data=None, verification_type="creator"):
    if not creator_profile_id:
        return {"ok": False, "error": "profile_required"}
    existing = get_creator_verification_status(creator_profile_id)
    if existing.get("status") == "pending":
        return {"ok": False, "error": "pending_request_exists", "request": existing.get("request")}
    req = {"id": str(uuid4()), "creator_profile_id": creator_profile_id, "verification_type": verification_type, "status": "pending", "submitted_data": submitted_data or {}, "admin_note": None, "reviewed_by_profile_id": None, "submitted_at": _now(), "reviewed_at": None}
    _FAKE_REQUESTS.append(req)
    if _db_available():
        write_query(
            "INSERT INTO chain_creator_verification_requests (id, creator_profile_id, verification_type, submitted_data) VALUES (%s,%s,%s,%s::jsonb)",
            (req["id"], creator_profile_id, verification_type, json.dumps(submitted_data or {}))
        )
    return {"ok": True, "request": req}


def get_verification_request(request_id):
    if _db_available():
        rows = fast_query("SELECT * FROM chain_creator_verification_requests WHERE id=%s LIMIT 1", (request_id,), default=[])
        return dict(rows[0]) if rows else None
    return next((r for r in _FAKE_REQUESTS if r["id"] == request_id), None)


def get_creator_verification_status(creator_profile_id):
    if _db_available():
        rows = fast_query("SELECT * FROM chain_creator_verification_requests WHERE creator_profile_id=%s ORDER BY submitted_at DESC LIMIT 1", (creator_profile_id,), default=[])
        req = dict(rows[0]) if rows else None
    else:
        req = next((r for r in reversed(_FAKE_REQUESTS) if r["creator_profile_id"] == creator_profile_id), None)
    return {"ok": True, "status": req["status"] if req else "not_submitted", "request": req}


def approve_creator_verification(request_id, admin_profile_id=None, note=None):
    req = get_verification_request(request_id)
    if not req:
        return {"ok": False, "error": "request_not_found"}
    req.update({"status": "approved", "admin_note": note, "reviewed_by_profile_id": admin_profile_id, "reviewed_at": _now()})
    from services.trust_score_service import increase_trust_score
    increase_trust_score(req["creator_profile_id"], 10)
    if _db_available():
        write_query("UPDATE chain_creator_verification_requests SET status='approved', admin_note=%s, reviewed_by_profile_id=%s, reviewed_at=now() WHERE id=%s", (note, admin_profile_id, request_id))
    try:
        from services.push_notification_service import queue_push_event
        queue_push_event(req["creator_profile_id"], "creator_verification_approved", "Verification approved", "Your creator verification was approved.")
    except Exception:
        pass
    return {"ok": True, "request": req}


def reject_creator_verification(request_id, admin_profile_id=None, note=None):
    req = get_verification_request(request_id)
    if not req:
        return {"ok": False, "error": "request_not_found"}
    req.update({"status": "rejected", "admin_note": note, "reviewed_by_profile_id": admin_profile_id, "reviewed_at": _now()})
    if _db_available():
        write_query("UPDATE chain_creator_verification_requests SET status='rejected', admin_note=%s, reviewed_by_profile_id=%s, reviewed_at=now() WHERE id=%s", (note, admin_profile_id, request_id))
    try:
        from services.fraud_detection_service import record_fraud_event
        record_fraud_event(req["creator_profile_id"], "creator_verification_rejected", 15, "low", metadata={"note": note})
        from services.push_notification_service import queue_push_event
        queue_push_event(req["creator_profile_id"], "creator_verification_rejected", "Verification rejected", note or "Your creator verification was rejected.")
    except Exception:
        pass
    return {"ok": True, "request": req}


def list_verification_requests(status=None, limit=50):
    if _db_available():
        if status:
            rows = fast_query("SELECT * FROM chain_creator_verification_requests WHERE status=%s ORDER BY submitted_at DESC LIMIT %s", (status, limit), default=[])
        else:
            rows = fast_query("SELECT * FROM chain_creator_verification_requests ORDER BY submitted_at DESC LIMIT %s", (limit,), default=[])
        return [dict(r) for r in rows]
    rows = [r for r in _FAKE_REQUESTS if not status or r["status"] == status]
    return rows[-limit:]
