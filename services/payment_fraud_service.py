import os, hashlib
from datetime import datetime, timezone, timedelta
from services.neon_service import fast_query, get_pool_status
from services.payout_security_service import log_fraud_flag

DAILY_TX_LIMIT_CENTS = 10000000
DAILY_WITHDRAWAL_LIMIT_CENTS = 5000000
VELOCITY_WINDOW_MINUTES = 60
MAX_TIP_GIFT_PER_HOUR = 20

def _db():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    s = get_pool_status()
    return bool(s.get("pool_ready") or s.get("recent_success"))

def _utcnow():
    return datetime.now(timezone.utc)

def check_daily_transaction_limit(profile_id, amount_cents, max_daily=DAILY_TX_LIMIT_CENTS):
    if not _db():
        return {"ok": True}
    today = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    rows = fast_query(
        "SELECT COALESCE(SUM(ABS(amount_cents)), 0) AS total FROM chain_wallet_transactions WHERE profile_id = %s AND created_at >= %s AND status = 'completed'",
        (profile_id, today), default=[{"total": 0}]
    )
    total = int(rows[0]["total"]) if rows else 0
    if total + amount_cents > max_daily:
        return {"ok": False, "error": "daily_transaction_limit_exceeded", "limit_cents": max_daily, "used_cents": total}
    return {"ok": True}

def check_rapid_gifting(sender_id, max_count=MAX_TIP_GIFT_PER_HOUR, window=VELOCITY_WINDOW_MINUTES):
    if not _db():
        return {"ok": True}
    since = (_utcnow() - timedelta(minutes=window)).isoformat()
    rows = fast_query(
        "SELECT COUNT(*) AS cnt FROM chain_wallet_transactions WHERE profile_id = %s AND transaction_type IN ('gift_sent', 'tip_sent') AND created_at >= %s AND status = 'completed'",
        (sender_id, since), default=[{"cnt": 0}]
    )
    count = int(rows[0]["cnt"]) if rows else 0
    if count >= max_count:
        log_fraud_flag(sender_id, "rapid_gifting", "medium", f"{count} gifts/tips in {window} minutes")
        return {"ok": False, "error": "too_many_transactions", "count": count, "max": max_count}
    return {"ok": True}

def check_large_amount(amount_cents, threshold_cents=1000000):
    if amount_cents >= threshold_cents:
        return {"ok": False, "flag": "large_amount", "amount_cents": amount_cents, "threshold_cents": threshold_cents}
    return {"ok": True}

def check_payout_eligibility(profile_id):
    if not _db():
        return {"ok": True}
    rows = fast_query("SELECT status FROM chain_wallets WHERE profile_id = %s LIMIT 1", (profile_id,), default=[])
    if rows and rows[0].get("status") == "locked":
        return {"ok": False, "error": "wallet_locked"}
    rows = fast_query(
        "SELECT id FROM chain_fraud_flags WHERE profile_id = %s AND status IN ('open', 'escalated') AND severity IN ('high', 'critical') LIMIT 1",
        (profile_id,), default=[]
    )
    if rows:
        return {"ok": False, "error": "payout_blocked_open_fraud_flag"}
    return {"ok": True}

def mask_account(account_str):
    s = str(account_str or "")
    if len(s) <= 4:
        return s
    return "*" * (len(s) - 4) + s[-4:]

def make_idempotency_key(*parts):
    raw = ":".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()
