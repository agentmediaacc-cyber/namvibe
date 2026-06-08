import os
from uuid import uuid4
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status

_FAKE_FRAUD_EVENTS = []
_PAIR_ACTIONS = {}


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1" or os.getenv("CHAIN_TEST_FAKE_DB") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _severity(score):
    if score >= 90:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _result(score, reasons):
    return {"ok": True, "fraud": score >= 70, "score": min(100, score), "severity": _severity(score), "reasons": reasons}


def analyze_wallet_transaction(profile_id, amount_cents, counterparty_profile_id=None, transaction_type="wallet"):
    score = 0
    reasons = []
    if profile_id and counterparty_profile_id and profile_id == counterparty_profile_id:
        score += 95
        reasons.append("self_payment_attempt")
    if amount_cents and int(amount_cents) >= 5000000:
        score += 55
        reasons.append("very_large_amount")
    key = (profile_id, counterparty_profile_id, transaction_type)
    _PAIR_ACTIONS[key] = _PAIR_ACTIONS.get(key, 0) + 1
    if _PAIR_ACTIONS[key] >= 5:
        score += 30
        reasons.append("repeated_pair_activity")
    return _result(score, reasons)


def analyze_tip(sender_profile_id, receiver_profile_id, amount_cents):
    return analyze_wallet_transaction(sender_profile_id, amount_cents, receiver_profile_id, "tip")


def analyze_gift(sender_profile_id, receiver_profile_id, amount_cents=0):
    return analyze_wallet_transaction(sender_profile_id, amount_cents, receiver_profile_id, "gift")


def analyze_subscription(subscriber_profile_id, creator_profile_id, price_cents=0):
    result = analyze_wallet_transaction(subscriber_profile_id, price_cents, creator_profile_id, "subscription")
    if price_cents == 0:
        result["score"] = max(0, result["score"] - 10)
        result["severity"] = _severity(result["score"])
        result["fraud"] = result["score"] >= 70
    return result


def analyze_payout_request(creator_profile_id, amount_cents, available_balance_cents=None, failed_attempts=0):
    score = 0
    reasons = []
    if amount_cents and int(amount_cents) >= 5000000:
        score += 55
        reasons.append("very_large_payout")
    if available_balance_cents is not None and int(amount_cents or 0) > int(available_balance_cents or 0):
        score += 90
        reasons.append("payout_over_available_balance")
    if failed_attempts >= 3:
        score += 35
        reasons.append("many_failed_payout_attempts")
    return _result(score, reasons)


def record_fraud_event(profile_id, event_type, score=0, severity=None, wallet_transaction_id=None, payout_request_id=None, metadata=None):
    event = {
        "id": str(uuid4()),
        "profile_id": profile_id,
        "wallet_transaction_id": wallet_transaction_id,
        "payout_request_id": payout_request_id,
        "event_type": event_type,
        "score": int(score or 0),
        "severity": severity or _severity(score or 0),
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _FAKE_FRAUD_EVENTS.append(event)
    if _db_available():
        try:
            import json
            write_query(
                "INSERT INTO chain_fraud_events (id, profile_id, wallet_transaction_id, payout_request_id, event_type, score, severity, metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                (event["id"], profile_id, wallet_transaction_id, payout_request_id, event_type, event["score"], event["severity"], json.dumps(metadata or {}))
            )
        except Exception:
            pass
    return {"ok": True, "event": event}


def get_fraud_summary(profile_id=None):
    events = [e for e in _FAKE_FRAUD_EVENTS if not profile_id or e.get("profile_id") == profile_id]
    return {"ok": True, "events": events[-100:], "count": len(events), "max_score": max([e["score"] for e in events], default=0)}


def is_high_risk_wallet_action(analysis):
    return bool(analysis and analysis.get("score", 0) >= 70)
