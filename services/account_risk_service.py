import os
from uuid import uuid4
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status

_FAKE_RISK = {}


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1" or os.getenv("CHAIN_TEST_FAKE_DB") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _clamp(value, low=0, high=100):
    return max(low, min(high, int(value or 0)))


def _default(profile_id):
    return {
        "id": str(uuid4()),
        "profile_id": profile_id,
        "risk_level": "low",
        "new_account": 0,
        "no_profile": 0,
        "report_count": 0,
        "restriction_count": 0,
        "mass_action_count": 0,
        "created_at": _now(),
        "updated_at": _now(),
    }


def _row(row):
    data = dict(row)
    data["id"] = str(data["id"])
    data["profile_id"] = str(data["profile_id"]) if data.get("profile_id") else None
    return data


def _calculate_risk_level(signals):
    total = sum(int(v) for v in signals.values())
    if total <= 20:
        return "low"
    elif total <= 50:
        return "medium"
    elif total <= 80:
        return "high"
    return "critical"


def get_or_create_risk(profile_id):
    if not profile_id:
        return None
    if not _db_available():
        _FAKE_RISK.setdefault(profile_id, _default(profile_id))
        return dict(_FAKE_RISK[profile_id])
    rows = fast_query("SELECT * FROM chain_account_risk WHERE profile_id = %s LIMIT 1", (profile_id,), default=[])
    if rows:
        return _row(rows[0])
    rows = fast_query(
        "INSERT INTO chain_account_risk (profile_id) VALUES (%s) ON CONFLICT (profile_id) DO UPDATE SET updated_at = now() RETURNING *",
        (profile_id,), default=[]
    )
    return _row(rows[0]) if rows else _default(profile_id)


def assess_account_risk(profile_id):
    risk = get_or_create_risk(profile_id)
    if not risk:
        return {"ok": False, "error": "no_risk_record"}
    signal_fields = ["new_account", "no_profile", "report_count", "restriction_count", "mass_action_count"]
    signals = {k: risk.get(k, 0) for k in signal_fields}
    new_level = _calculate_risk_level(signals)
    risk["risk_level"] = new_level
    risk["updated_at"] = _now()
    if not _db_available():
        _FAKE_RISK[profile_id] = dict(risk)
        return {"ok": True, "risk": risk}
    rows = fast_query(
        "UPDATE chain_account_risk SET risk_level = %s, updated_at = now() WHERE profile_id = %s RETURNING *",
        (new_level, profile_id), default=[]
    )
    return {"ok": True, "risk": _row(rows[0]) if rows else risk}


def update_risk_signal(profile_id, signal_name, increment=1):
    allowed = {"new_account", "no_profile", "report_count", "restriction_count", "mass_action_count"}
    if signal_name not in allowed:
        return {"ok": False, "error": "invalid_signal"}
    if not _db_available():
        risk = _FAKE_RISK.setdefault(profile_id, _default(profile_id))
        risk[signal_name] = risk.get(signal_name, 0) + increment
        result = assess_account_risk(profile_id)
        _FAKE_RISK[profile_id] = dict(result["risk"])
        return result
    rows = fast_query(
        f"UPDATE chain_account_risk SET {signal_name} = {signal_name} + %s, updated_at = now() WHERE profile_id = %s RETURNING *",
        (increment, profile_id), default=[]
    )
    if not rows:
        get_or_create_risk(profile_id)
        rows = fast_query(
            f"UPDATE chain_account_risk SET {signal_name} = {signal_name} + %s, updated_at = now() WHERE profile_id = %s RETURNING *",
            (increment, profile_id), default=[]
        )
    return assess_account_risk(profile_id)


def get_risk_level(profile_id):
    risk = get_or_create_risk(profile_id)
    if not risk:
        return {"ok": False, "error": "no_risk_record"}
    return {"ok": True, "profile_id": profile_id, "risk_level": risk.get("risk_level", "low")}
