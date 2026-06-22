import os
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from services.neon_service import fast_query, write_query, get_pool_status
from services.logging_service import log_error

PLATFORM_FEE_PCT = 5

def _db():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    s = get_pool_status()
    return bool(s.get("pool_ready") or s.get("recent_success"))

def _utcnow():
    return datetime.now(timezone.utc)

def _cents(v):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError, OverflowError):
        return 0

def _apply_fee(gross_cents):
    fee = _cents(gross_cents * PLATFORM_FEE_PCT / 100)
    net = gross_cents - fee
    return fee, net

def record_earnings(creator_profile_id, source_type, source_id, amount_cents, status="pending"):
    if not _db():
        return {"ok": True, "amount_cents": amount_cents}
    try:
        write_query(
            "INSERT INTO chain_creator_earnings (id, creator_profile_id, source_type, source_id, amount, currency, status, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (str(uuid4()), creator_profile_id, source_type, source_id, amount_cents, 'NAD', status, _utcnow().isoformat())
        )
        return {"ok": True, "amount_cents": amount_cents}
    except Exception as e:
        log_error("record_earnings_failed", creator_profile_id=creator_profile_id, error=str(e))
        return {"ok": False, "error": str(e)}

def mark_available(earnings_id):
    if not _db():
        return {"ok": True}
    try:
        write_query("UPDATE chain_creator_earnings SET status = 'available' WHERE id = %s AND status = 'pending'", (earnings_id,))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def mark_withdrawn(earnings_id):
    if not _db():
        return {"ok": True}
    try:
        write_query("UPDATE chain_creator_earnings SET status = 'withdrawn' WHERE id = %s AND status = 'available'", (earnings_id,))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def reverse_earnings(earnings_id):
    if not _db():
        return {"ok": True}
    try:
        write_query("UPDATE chain_creator_earnings SET status = 'reversed' WHERE id = %s AND status IN ('pending', 'available')", (earnings_id,))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_earnings_summary(creator_profile_id):
    if not _db():
        return {"pending_cents": 0, "available_cents": 0, "withdrawn_cents": 0, "reversed_cents": 0, "total_gross": 0}
    rows = fast_query(
        "SELECT status, COALESCE(SUM(amount), 0) AS total FROM chain_creator_earnings WHERE creator_profile_id = %s GROUP BY status",
        (creator_profile_id,), default=[]
    )
    summary = {"pending_cents": 0, "available_cents": 0, "withdrawn_cents": 0, "reversed_cents": 0, "total_gross": 0}
    for r in rows:
        s = r["status"]
        summary["total_gross"] += _cents(r["total"])
        key = f"{s}_cents"
        if key in summary:
            summary[key] = _cents(r["total"])
    return summary

def get_earnings_history(creator_profile_id, limit=50, offset=0):
    if not _db():
        return []
    rows = fast_query(
        "SELECT * FROM chain_creator_earnings WHERE creator_profile_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
        (creator_profile_id, limit, offset), default=[]
    )
    result = []
    for r in rows:
        entry = dict(r)
        entry["id"] = str(r["id"])
        entry["creator_profile_id"] = str(r["creator_profile_id"])
        if r.get("source_id"):
            entry["source_id"] = str(r["source_id"])
        result.append(entry)
    return result
