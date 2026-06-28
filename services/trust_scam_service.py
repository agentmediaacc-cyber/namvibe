"""Trust and scam detection service."""
from datetime import datetime, timezone, timedelta
from services.neon_service import fast_query, write_query
from services.logging_service import log_info

TRUST_LEVEL_ORDER = {"new": 0, "low": 1, "medium": 2, "high": 3, "verified": 4}

def calculate_trust_level(profile_id):
    rows = fast_query(
        "SELECT is_verified, report_count, suspicious_score, followers_count, "
        "friends_count, created_at, profile_completed FROM chain_profiles WHERE id = %s",
        (profile_id,), default=[]
    )
    if not rows:
        return "new"
    p = rows[0]
    if p.get("is_verified"):
        return "verified"
    age_days = 0
    if p.get("created_at"):
        age = datetime.now(timezone.utc) - p["created_at"].replace(tzinfo=timezone.utc) if hasattr(p["created_at"], 'replace') else datetime.now(timezone.utc) - p["created_at"]
        age_days = age.days
    score = 0
    if age_days > 365: score += 3
    elif age_days > 90: score += 2
    elif age_days > 30: score += 1
    if (p.get("followers_count") or 0) > 100: score += 2
    elif (p.get("followers_count") or 0) > 10: score += 1
    if (p.get("friends_count") or 0) > 10: score += 1
    if p.get("profile_completed"): score += 1
    if (p.get("report_count") or 0) > 5: score -= 2
    if (p.get("suspicious_score") or 0) > 10: score -= 3
    if score >= 5: return "high"
    if score >= 2: return "medium"
    if score >= 0: return "low"
    return "new"

def add_signal(profile_id, signal_type, notes=None):
    try:
        write_query(
            "INSERT INTO chain_trust_signals (id, profile_id, signal_type, notes) VALUES (gen_random_uuid(), %s, %s, %s)",
            (profile_id, signal_type, notes)
        )
        score_map = {"possible_fake": 5, "suspicious_messaging": 3, "many_reports": 4,
                     "duplicate_account": 8, "unusual_login": 2, "new_account": 1,
                     "high_trust": -5, "verified": -10}
        delta = score_map.get(signal_type, 0)
        if delta != 0:
            if delta > 0:
                write_query("UPDATE chain_profiles SET suspicious_score = COALESCE(suspicious_score, 0) + %s WHERE id = %s",
                           (abs(delta), profile_id))
            else:
                write_query("UPDATE chain_profiles SET suspicious_score = GREATEST(0, COALESCE(suspicious_score, 0) - %s) WHERE id = %s",
                           (abs(delta), profile_id))
        trust = calculate_trust_level(profile_id)
        write_query("UPDATE chain_profiles SET account_trust_level = %s WHERE id = %s", (trust, profile_id))
        log_info("trust_signal_added", profile_id=profile_id, signal_type=signal_type)
        return {"ok": True, "trust_level": trust}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_trust_summary(profile_id):
    rows = fast_query(
        "SELECT account_trust_level, is_verified, report_count, suspicious_score, "
        "completion_percentage, created_at FROM chain_profiles WHERE id = %s",
        (profile_id,), default=[]
    )
    signals = fast_query(
        "SELECT signal_type, score, notes, created_at FROM chain_trust_signals WHERE profile_id = %s ORDER BY created_at DESC LIMIT 20",
        (profile_id,), default=[]
    )
    p = rows[0] if rows else {}
    return {
        "trust_level": p.get("account_trust_level", "new"),
        "is_verified": bool(p.get("is_verified")),
        "report_count": p.get("report_count", 0),
        "suspicious_score": p.get("suspicious_score", 0),
        "completion_percentage": p.get("completion_percentage", 0),
        "account_age_days": (datetime.now(timezone.utc) - p["created_at"].replace(tzinfo=timezone.utc)).days if p.get("created_at") else 0,
        "signals": signals
    }

def increment_report_count(profile_id):
    write_query("UPDATE chain_profiles SET report_count = COALESCE(report_count, 0) + 1 WHERE id = %s", (profile_id,))
    count = fast_query("SELECT report_count FROM chain_profiles WHERE id = %s", (profile_id,), default=[{"report_count": 0}])
    if count and count[0].get("report_count", 0) >= 3:
        add_signal(profile_id, "many_reports", "Received 3+ reports")
