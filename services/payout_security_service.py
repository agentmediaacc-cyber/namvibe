import json, os
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from services.neon_service import fast_query, write_query, get_pool_status

def _db():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    s = get_pool_status()
    return bool(s.get("pool_ready") or s.get("recent_success"))

def _utcnow():
    return datetime.now(timezone.utc)

def validate_payout_status_transition(current_status, new_status):
    valid = {
        "pending": ["approved", "rejected", "cancelled"],
        "approved": ["paid", "failed", "cancelled"],
        "rejected": ["cancelled"],
        "paid": [],
        "failed": ["pending"],
        "cancelled": [],
    }
    allowed = valid.get(current_status, [])
    if new_status not in allowed:
        return {"ok": False, "error": f"Cannot transition from {current_status} to {new_status}"}
    return {"ok": True}

def check_duplicate_payout_by_reference(payout_reference):
    if not payout_reference or not _db():
        return {"ok": False, "duplicate": False}
    rows = fast_query(
        "SELECT id, status FROM chain_payout_requests WHERE payout_reference = %s AND status IN ('paid', 'approved') LIMIT 1",
        (payout_reference,), default=[]
    )
    if rows:
        return {"ok": True, "duplicate": True, "existing_id": str(rows[0]["id"]), "status": rows[0]["status"]}
    return {"ok": True, "duplicate": False}

def check_duplicate_payout_by_idempotency(idempotency_key, profile_id):
    if not idempotency_key or not _db():
        return {"ok": False, "duplicate": False}
    rows = fast_query(
        "SELECT id, status FROM chain_payout_requests WHERE idempotency_key = %s AND profile_id = %s LIMIT 1",
        (idempotency_key, profile_id), default=[]
    )
    if rows:
        return {"ok": True, "duplicate": True, "existing_id": str(rows[0]["id"]), "status": rows[0]["status"]}
    return {"ok": True, "duplicate": False}

def check_daily_withdrawal_limit(profile_id, amount_cents, max_daily_cents=5000000):
    if not _db():
        return {"ok": True}
    today = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    rows = fast_query(
        "SELECT COALESCE(SUM(amount_cents), 0) AS total FROM chain_payout_requests WHERE profile_id = %s AND created_at >= %s AND status IN ('pending', 'approved', 'paid')",
        (profile_id, today), default=[{"total": 0}]
    )
    total = int(rows[0]["total"]) if rows else 0
    if total + amount_cents > max_daily_cents:
        return {"ok": False, "error": "daily_withdrawal_limit_exceeded", "limit_cents": max_daily_cents, "used_cents": total}
    return {"ok": True}

def check_velocity(profile_id, action_type, max_count=10, window_minutes=60):
    if not _db():
        return {"ok": True}
    since = (_utcnow() - timedelta(minutes=window_minutes)).isoformat()
    rows = fast_query(
        "SELECT COUNT(*) AS cnt FROM chain_payment_audit_logs WHERE actor_id = %s AND action = %s AND created_at >= %s",
        (profile_id, action_type, since), default=[{"cnt": 0}]
    )
    count = int(rows[0]["cnt"]) if rows else 0
    if count >= max_count:
        return {"ok": False, "error": "rate_limit_exceeded", "count": count, "max": max_count}
    return {"ok": True}

def log_admin_action(admin_id, action, entity_type, entity_id, old_status=None, new_status=None, amount_cents=None, notes=None):
    if not _db():
        return
    try:
        from flask import request as flask_request
        ip = flask_request.headers.get("X-Forwarded-For", flask_request.remote_addr) if flask_request else None
        ua = flask_request.headers.get("User-Agent") if flask_request else None
    except Exception:
        ip = None
        ua = None
    write_query(
        "INSERT INTO chain_payment_audit_logs (id, actor_id, action, entity_type, entity_id, old_status, new_status, amount_cents, ip_address, user_agent, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (str(uuid4()), admin_id, action, entity_type, entity_id, old_status, new_status, amount_cents, ip, ua, notes)
    )

def log_fraud_flag(profile_id, flag_type, severity, reason, related_type=None, related_id=None):
    if not _db():
        return
    write_query(
        "INSERT INTO chain_fraud_flags (id, profile_id, flag_type, severity, reason, status, related_type, related_id) VALUES (%s, %s, %s, %s, %s, 'open', %s, %s)",
        (str(uuid4()), profile_id, flag_type, severity, reason, related_type, related_id)
    )
