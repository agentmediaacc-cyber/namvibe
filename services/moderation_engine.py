import uuid
from services.neon_service import fast_query, write_query

_PROFANITY_KEYWORDS = {
    "damn",
    "hell",
    "idiot",
    "stupid",
}


def _normalize_text(value):
    return " ".join(str(value or "").lower().split())


def contains_profanity(text):
    normalized = _normalize_text(text)
    words = set(normalized.split())
    return any(keyword in words for keyword in _PROFANITY_KEYWORDS)


def detect_spam_burst(profile_id, body, window_seconds=60, threshold=4):
    normalized = _normalize_text(body)
    if not profile_id or not normalized:
        return False
    sql = """
        SELECT COUNT(*) AS count
        FROM chain_messages
        WHERE sender_profile_id = %s
          AND deleted_at IS NULL
          AND created_at >= now() - (%s || ' seconds')::interval
          AND LOWER(TRIM(COALESCE(body, ''))) = %s
    """
    rows = fast_query(sql, (profile_id, int(window_seconds), normalized), timeout_ms=1000, default=[])
    count = int((rows[0] or {}).get("count") or 0) if rows else 0
    return count >= int(threshold)


def moderation_cleanliness_score(status):
    normalized = (status or "clean").lower()
    return 1.0 if normalized == "clean" else 0.2


def auto_mute_placeholder(profile_id, repeated_reports):
    return {
        "profile_id": profile_id,
        "threshold": 5,
        "repeated_reports": int(repeated_reports or 0),
        "should_auto_mute": int(repeated_reports or 0) >= 5,
    }

def report_entity(reporter_profile_id, entity_type, entity_id, reason, details=None, target_profile_id=None):
    """Creates a safety report."""
    report_id = str(uuid.uuid4())
    sql = """
        INSERT INTO chain_reports (
            id, reporter_profile_id, target_profile_id, entity_type, entity_id, reason, details, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, now())
        RETURNING id
    """
    params = (report_id, reporter_profile_id, target_profile_id, entity_type, entity_id, reason, details)
    result = write_query(sql, params)
    escalation_sql = """
        SELECT COUNT(*) AS count
        FROM chain_reports
        WHERE entity_type = %s
          AND entity_id = %s
          AND created_at >= now() - interval '24 hours'
    """
    counts = fast_query(escalation_sql, (entity_type, entity_id), timeout_ms=1000, default=[])
    repeated_reports = int((counts[0] or {}).get("count") or 0) if counts else 0
    escalation = auto_mute_placeholder(target_profile_id, repeated_reports)
    if repeated_reports >= 3:
        print(f"[moderation_engine] escalation placeholder: {escalation}")
    return result

def block_profile(blocker_profile_id, blocked_profile_id):
    """Blocks a profile."""
    if blocker_profile_id == blocked_profile_id:
        return False
    
    sql = "INSERT INTO chain_blocks (id, blocker_profile_id, blocked_profile_id, created_at) VALUES (%s, %s, %s, now()) ON CONFLICT DO NOTHING"
    return write_query(sql, (str(uuid.uuid4()), blocker_profile_id, blocked_profile_id))

def mute_profile(muter_profile_id, muted_profile_id):
    """Mutes a profile."""
    if muter_profile_id == muted_profile_id:
        return False
    
    sql = "INSERT INTO chain_mutes (id, muter_profile_id, muted_profile_id, created_at) VALUES (%s, %s, %s, now()) ON CONFLICT DO NOTHING"
    return write_query(sql, (str(uuid.uuid4()), muter_profile_id, muted_profile_id))

def is_blocked(profile_a, profile_b):
    """Checks if there is a block between two users in either direction."""
    sql = """
        SELECT 1 FROM chain_blocks 
        WHERE ((blocker_profile_id = %s AND blocked_profile_id = %s) 
           OR (blocker_profile_id = %s AND blocked_profile_id = %s)) 
        AND deleted_at IS NULL
    """
    # Increased timeout and use fast_query with a larger limit
    rows = fast_query(sql, (profile_a, profile_b, profile_b, profile_a), timeout_ms=5000)
    return bool(rows)

def can_interact(profile_a, profile_b):
    """Checks if two profiles can interact (not blocked)."""
    return not is_blocked(profile_a, profile_b)

def restrict_profile(restricter_profile_id, restricted_profile_id):
    """Restricts a profile (messages from them are hidden/filtered)."""
    if restricter_profile_id == restricted_profile_id:
        return False
    sql = "INSERT INTO chain_restricted_users (restricter_profile_id, restricted_profile_id) VALUES (%s, %s) ON CONFLICT DO NOTHING"
    return write_query(sql, (restricter_profile_id, restricted_profile_id))

def unrestrict_profile(restricter_profile_id, restricted_profile_id):
    """Unrestricts a profile."""
    sql = "DELETE FROM chain_restricted_users WHERE restricter_profile_id = %s AND restricted_profile_id = %s"
    return write_query(sql, (restricter_profile_id, restricted_profile_id))

def is_restricted(profile_id, target_profile_id):
    """Checks if profile_id has restricted target_profile_id."""
    sql = "SELECT 1 FROM chain_restricted_users WHERE restricter_profile_id = %s AND restricted_profile_id = %s"
    return bool(fast_query(sql, (profile_id, target_profile_id)))
