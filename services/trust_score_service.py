import os
from uuid import uuid4
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status

_FAKE_TRUST = {}


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1" or os.getenv("CHAIN_TEST_FAKE_DB") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _clamp(value, low=0, high=100):
    return max(low, min(high, int(value or 0)))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _default(profile_id):
    return {
        "id": str(uuid4()),
        "profile_id": profile_id,
        "trust_score": 70,
        "risk_score": 0,
        "spam_score": 0,
        "fraud_score": 0,
        "report_count": 0,
        "warning_count": 0,
        "restriction_count": 0,
        "last_reviewed_at": None,
        "updated_at": _now(),
        "created_at": _now(),
    }


def _row(row):
    data = dict(row)
    data["id"] = str(data["id"])
    data["profile_id"] = str(data["profile_id"]) if data.get("profile_id") else None
    return data


def get_or_create_trust_score(profile_id):
    if not profile_id:
        return None
    if not _db_available():
        _FAKE_TRUST.setdefault(profile_id, _default(profile_id))
        return dict(_FAKE_TRUST[profile_id])
    rows = fast_query("SELECT * FROM chain_trust_scores WHERE profile_id = %s LIMIT 1", (profile_id,), default=[])
    if rows:
        return _row(rows[0])
    rows = fast_query(
        "INSERT INTO chain_trust_scores (profile_id) VALUES (%s) ON CONFLICT (profile_id) DO UPDATE SET updated_at = now() RETURNING *",
        (profile_id,), default=[]
    )
    return _row(rows[0]) if rows else _default(profile_id)


def get_trust_score(profile_id):
    return get_or_create_trust_score(profile_id)


def update_trust_score(profile_id, **updates):
    score = get_or_create_trust_score(profile_id)
    if not score:
        return None
    allowed = {"trust_score", "risk_score", "spam_score", "fraud_score", "report_count", "warning_count", "restriction_count"}
    clean = {k: int(v) for k, v in updates.items() if k in allowed}
    if "trust_score" in clean:
        clean["trust_score"] = _clamp(clean["trust_score"])
    for key in ("risk_score", "spam_score", "fraud_score"):
        if key in clean:
            clean[key] = _clamp(clean[key])
    if not _db_available():
        _FAKE_TRUST[profile_id].update(clean)
        _FAKE_TRUST[profile_id]["updated_at"] = _now()
        return dict(_FAKE_TRUST[profile_id])
    if clean:
        assignments = ", ".join(f"{k} = %s" for k in clean)
        rows = fast_query(
            f"UPDATE chain_trust_scores SET {assignments}, updated_at = now() WHERE profile_id = %s RETURNING *",
            (*clean.values(), profile_id), default=[]
        )
        return _row(rows[0]) if rows else get_or_create_trust_score(profile_id)
    return score


def increase_risk_score(profile_id, amount=5):
    score = get_or_create_trust_score(profile_id)
    return update_trust_score(profile_id, risk_score=_clamp(score["risk_score"] + amount))


def decrease_trust_score(profile_id, amount=5):
    score = get_or_create_trust_score(profile_id)
    return update_trust_score(profile_id, trust_score=_clamp(score["trust_score"] - amount))


def increase_trust_score(profile_id, amount=2):
    score = get_or_create_trust_score(profile_id)
    return update_trust_score(profile_id, trust_score=_clamp(score["trust_score"] + amount))


def record_warning(profile_id, reason=None):
    score = get_or_create_trust_score(profile_id)
    return update_trust_score(profile_id, warning_count=score["warning_count"] + 1, trust_score=score["trust_score"] - 3)


def record_restriction(profile_id, reason=None):
    score = get_or_create_trust_score(profile_id)
    return update_trust_score(profile_id, restriction_count=score["restriction_count"] + 1, trust_score=score["trust_score"] - 10, risk_score=score["risk_score"] + 10)


def recalculate_trust_score(profile_id):
    score = get_or_create_trust_score(profile_id)
    trust = 70
    trust -= min(25, score["report_count"] * 4)
    trust -= min(20, score["spam_score"] // 4)
    trust -= min(35, score["fraud_score"] // 3)
    trust -= min(20, score["restriction_count"] * 10)
    trust -= min(10, score["warning_count"] * 3)
    return update_trust_score(profile_id, trust_score=_clamp(trust), risk_score=_clamp(score["spam_score"] + score["fraud_score"] + score["report_count"] * 5))


def get_trust_summary(profile_id):
    score = get_or_create_trust_score(profile_id)
    level = "high"
    if score["trust_score"] < 40 or score["risk_score"] >= 70:
        level = "critical"
    elif score["trust_score"] < 60 or score["risk_score"] >= 45:
        level = "medium"
    return {"ok": True, "profile_id": profile_id, "trust": score, "risk_level": level}
