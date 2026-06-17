"""Creator verification badge service."""
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query

_VERIFIED_CACHE = {}

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

BADGE_TYPES = {"blue", "business", "government", "artist", "creator"}

def get_verification_badge(user_id):
    if not user_id:
        return None
    key = str(user_id)
    if key in _VERIFIED_CACHE:
        return _VERIFIED_CACHE[key]
    rows = fast_query(
        "SELECT badge_type, status FROM chain_creator_verifications WHERE user_id = %s AND status = 'approved' LIMIT 1",
        (user_id,), timeout_ms=2000, default=[]
    )
    result = rows[0] if rows else None
    _VERIFIED_CACHE[key] = result
    return result

def clear_verification_cache(user_id=None):
    if user_id:
        _VERIFIED_CACHE.pop(str(user_id), None)
    else:
        _VERIFIED_CACHE.clear()

def request_verification(user_id, badge_type, evidence_url=None):
    import uuid
    if badge_type not in BADGE_TYPES:
        return None, "Invalid badge type"
    vid = str(uuid.uuid4())
    try:
        write_query(
            "INSERT INTO chain_creator_verifications (id, user_id, badge_type, status, evidence_url) VALUES (%s, %s, %s, 'pending', %s)",
            (vid, user_id, badge_type, evidence_url)
        )
        clear_verification_cache(user_id)
        return vid, None
    except Exception as e:
        return None, str(e)

def review_verification(verification_id, reviewer_id, status):
    if status not in ("approved", "rejected"):
        return False
    try:
        write_query(
            "UPDATE chain_creator_verifications SET status = %s, reviewed_by = %s, reviewed_at = now() WHERE id = %s",
            (status, reviewer_id, verification_id)
        )
        # Clear cache for the affected user
        row = fast_query("SELECT user_id FROM chain_creator_verifications WHERE id = %s", (verification_id,), timeout_ms=2000, default=[])
        if row:
            clear_verification_cache(row[0].get("user_id"))
        return True
    except Exception:
        return False

def render_badge_html(badge_type, size=16):
    colors = {
        "blue": "#1E88E5",
        "business": "#FFB300",
        "government": "#E53935",
        "artist": "#8E24AA",
        "creator": "#00ACC1",
    }
    color = colors.get(badge_type, "#1E88E5")
    return f'<i class="fas fa-circle-check" style="color:{color};font-size:{size}px;" title="{badge_type.title()} Verified"></i>'
