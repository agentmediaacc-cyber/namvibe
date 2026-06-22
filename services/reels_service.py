"""Reels service with watch-time tracking, events, comments, and save."""
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.reels_engine import list_reels, get_reel, create_reel, record_reel_view, like_reel, share_reel, delete_reel

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def get_reel_feed(limit=20, offset=0):
    rows = fast_query("""
        SELECT r.*, p.username, p.avatar_url, p.is_verified,
               COALESCE(r.views_count, 0) AS views_count,
               COALESCE(r.likes_count, 0) AS likes_count,
               COALESCE(r.comments_count, 0) AS comments_count,
               COALESCE(r.shares_count, 0) AS shares_count,
               r.duration_seconds, r.music_title, r.caption
        FROM chain_reels r
        JOIN chain_profiles p ON r.profile_id = p.id
        WHERE r.status = 'published' AND r.visibility = 'public'
          AND r.processing_status = 'ready' AND r.deleted_at IS NULL
        ORDER BY r.created_at DESC
        LIMIT %s OFFSET %s
    """, (limit, offset), timeout_ms=2000, default=[])
    return rows or []

def track_reel_event(reel_id, user_id, event_type, watch_ms=0):
    try:
        write_query(
            "INSERT INTO chain_reel_events (reel_id, user_id, event_type, watch_ms) VALUES (%s, %s, %s, %s)",
            (reel_id, user_id, event_type, watch_ms)
        )
        return True
    except Exception:
        return False

def get_reel_comments(reel_id, limit=20):
    rows = fast_query("""
        SELECT c.*, p.username, p.avatar_url
        FROM chain_reel_comments c
        JOIN chain_profiles p ON c.profile_id = p.id
        WHERE c.reel_id = %s
        ORDER BY c.created_at DESC
        LIMIT %s
    """, (reel_id, limit), timeout_ms=2000, default=[])
    return rows or []

def add_reel_comment(profile_id, reel_id, body):
    from services.engagement_service import add_comment
    return add_comment(profile_id, "reel", reel_id, body)

def toggle_reel_like(profile_id, reel_id):
    from services.engagement_service import toggle_like
    return toggle_like(profile_id, "reel", reel_id)

def toggle_reel_save(profile_id, reel_id):
    from services.engagement_service import toggle_save
    return toggle_save(profile_id, "reel", reel_id)

def is_following_creator(follower_id, creator_id):
    if not follower_id or not creator_id:
        return False
    rows = fast_query(
        "SELECT id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s AND deleted_at IS NULL",
        (follower_id, creator_id), timeout_ms=2000, default=[]
    )
    return bool(rows)

def batch_is_following(follower_id, creator_ids):
    if not follower_id or not creator_ids:
        return set()
    rows = fast_query(
        "SELECT following_profile_id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = ANY(%s) AND deleted_at IS NULL",
        (follower_id, list(creator_ids)), timeout_ms=500, default=[]
    )
    return {r["following_profile_id"] for r in rows}
