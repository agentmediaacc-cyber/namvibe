"""Query functions for premium profile feature tables.

Heavy data (achievements, collections, badges, timeline) -> Supabase via safe_select
Lite data (education, work, skills, visitors, activity, favorites) -> Neon via fast_query
"""

from services.neon_service import fast_query
from services.supabase_safe import safe_select


def get_education(profile_id, limit=20):
    """From chain_education (Neon)."""
    return fast_query(
        "SELECT * FROM chain_education WHERE profile_id = %s ORDER BY end_year DESC NULLS FIRST, start_year DESC LIMIT %s",
        (profile_id, limit),
        default=[]
    )


def get_work_experience(profile_id, limit=20):
    """From chain_work_experience (Neon)."""
    return fast_query(
        "SELECT * FROM chain_work_experience WHERE profile_id = %s ORDER BY end_year DESC NULLS FIRST, start_year DESC LIMIT %s",
        (profile_id, limit),
        default=[]
    )


def get_skills(profile_id, limit=50):
    """From chain_user_skills (Neon)."""
    return fast_query(
        "SELECT * FROM chain_user_skills WHERE profile_id = %s ORDER BY is_top DESC, proficiency DESC LIMIT %s",
        (profile_id, limit),
        default=[]
    )


def get_visitors(profile_id, limit=18):
    """From chain_profile_visitors (Neon), joined with chain_profiles for display."""
    return fast_query(
        """
        SELECT v.*, p.username, p.display_name, p.avatar_url
        FROM chain_profile_visitors v
        JOIN chain_profiles p ON p.id = v.visitor_id
        WHERE v.profile_id = %s
        ORDER BY v.visited_at DESC
        LIMIT %s
        """,
        (profile_id, limit),
        default=[]
    )


def get_activity_log(profile_id, limit=50):
    """From chain_activity_log (Neon)."""
    return fast_query(
        "SELECT * FROM chain_activity_log WHERE profile_id = %s ORDER BY created_at DESC LIMIT %s",
        (profile_id, limit),
        default=[]
    )


def get_favorites(profile_id):
    """From chain_user_favorites (Neon), grouped by type."""
    rows = fast_query(
        "SELECT * FROM chain_user_favorites WHERE profile_id = %s ORDER BY sort_order, label",
        (profile_id,),
        default=[]
    )
    grouped = {}
    for r in rows:
        grouped.setdefault(r.get("favorite_type"), []).append(r)
    return grouped


def get_favorites_by_type(profile_id, fav_type, limit=20):
    """From chain_user_favorites (Neon), filtered by type."""
    return fast_query(
        "SELECT * FROM chain_user_favorites WHERE profile_id = %s AND favorite_type = %s ORDER BY sort_order, label LIMIT %s",
        (profile_id, fav_type, limit),
        default=[]
    )


def get_achievements(profile_id):
    """From chain_achievements (Supabase)."""
    try:
        return safe_select("chain_achievements", filters={"profile_id": profile_id}, order_column="unlocked_at", order_desc=True) or []
    except Exception:
        return []


def get_collections(profile_id):
    """From chain_collections (Supabase), with item count."""
    try:
        return safe_select("chain_collections", filters={"profile_id": profile_id, "is_hidden": False}, order_column="sort_order", order_desc=False) or []
    except Exception:
        return []


def get_badges(profile_id):
    """From chain_profile_badges (Supabase)."""
    try:
        return safe_select("chain_profile_badges", filters={"profile_id": profile_id, "is_visible": True}, order_column="earned_at", order_desc=True) or []
    except Exception:
        return []


def get_timeline(profile_id, limit=30):
    """From chain_profile_timeline (Supabase)."""
    try:
        return safe_select("chain_profile_timeline", filters={"profile_id": profile_id}, order_column="event_date", order_desc=True, limit=limit) or []
    except Exception:
        return []


def log_activity(profile_id, activity_type, activity_label=None, target_type=None, target_id=None, metadata=None):
    """Insert into chain_activity_log (Neon)."""
    from services.neon_service import write_query
    return write_query(
        "INSERT INTO chain_activity_log (profile_id, activity_type, activity_label, target_type, target_id, metadata) VALUES (%s, %s, %s, %s, %s, %s)",
        (profile_id, activity_type, activity_label, target_type, target_id, metadata or "{}")
    )


def record_visitor(profile_id, visitor_id):
    """Upsert into chain_profile_visitors (Neon)."""
    from services.neon_service import write_query
    return write_query(
        "INSERT INTO chain_profile_visitors (profile_id, visitor_id, visited_at) VALUES (%s, %s, now()) "
        "ON CONFLICT (profile_id, visitor_id) DO UPDATE SET visited_at = now()",
        (profile_id, visitor_id)
    )
