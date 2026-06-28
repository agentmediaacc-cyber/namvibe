"""Reels service with watch-time tracking, events, comments, and save."""
import os
import time
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.reels_engine import list_reels, get_reel, create_reel, record_reel_view, like_reel, share_reel, delete_reel

_REEL_EVENT_QUEUE = []
_REEL_EVENT_LOCK = __import__("threading").Lock()
_REEL_EVENT_FLUSH_INTERVAL = 30
_REEL_EVENT_LAST_FLUSH = 0
_REEL_EVENT_DEBOUNCE_SECONDS = 300

_DEBOUNCE_EVENTS = {}
_DEBOUNCE_EVENTS_LOCK = __import__("threading").Lock()

try:
    from services.redis_service import cache_get, cache_set
    _redis_available = True
except Exception:
    _redis_available = False

_CHAIN_TEST_MODE = os.environ.get("CHAIN_TEST_MODE") == "1"


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def get_reel_feed(limit=20, offset=0, viewer_id=None):
    """Get reels feed with proper visibility filtering.
    
    Visibility rules:
    - public: everyone can see
    - followers: only followers can see
    - private: only owner can see
    
    Caching:
    - Anonymous/public reels (no viewer_id) are cached with short TTL (15s)
    - Authenticated feeds bypass cache (privacy-sensitive)
    """
    profile_id_param = str(viewer_id) if viewer_id else None
    
    # Anonymous/public feed is safe to cache briefly
    if not profile_id_param and offset == 0:
        try:
            from services.redis_service import cache_get as _rget, cache_set as _rset
            cache_key = f"reel_feed:public:limit:{limit}"
            cached = _rget(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass
    
    # Base query
    query = """
        SELECT r.id, r.profile_id, r.caption, r.video_url, r.thumbnail_url, r.media_url,
               r.duration_seconds, r.music_title, r.created_at,
               p.username, p.avatar_url, p.is_verified,
               COALESCE(r.views_count, 0) AS views_count,
               COALESCE(r.likes_count, 0) AS likes_count,
               COALESCE(r.comments_count, 0) AS comments_count,
               COALESCE(r.shares_count, 0) AS shares_count
        FROM chain_reels r
        JOIN chain_profiles p ON r.profile_id = p.id
        WHERE r.status = 'published'
          AND r.processing_status = 'ready' AND r.deleted_at IS NULL
    """
    params = []
    
    # Add visibility filter based on viewer
    if profile_id_param:
        # Show: owner's own reels (any visibility) + public reels + followers reels from followed users
        query += """ AND (
            r.profile_id = %s
            OR r.visibility = 'public'
            OR (r.visibility = 'followers' AND EXISTS (
                SELECT 1 FROM chain_follows 
                WHERE follower_profile_id = %s AND following_profile_id = r.profile_id
            ))
        )"""
        params.extend([profile_id_param, profile_id_param])
    else:
        # No viewer - only public reels
        query += " AND r.visibility = 'public'"
    
    params.extend([limit, offset])
    query += " ORDER BY r.created_at DESC LIMIT %s OFFSET %s"
    result = fast_query(query, params, timeout_ms=2000, default=[]) or []
    
    # Cache anonymous/public feed briefly
    if not profile_id_param and offset == 0:
        try:
            from services.redis_service import cache_set as _rset
            cache_key = f"reel_feed:public:limit:{limit}"
            _rset(cache_key, result, ttl=15)
        except Exception:
            pass
    
    return result


def _event_debounce_key(reel_id, user_id, event_type):
    return f"reel_event:{reel_id}:{user_id or 'anon'}:{event_type}"


def _check_event_debounce(reel_id, user_id, event_type):
    if _CHAIN_TEST_MODE:
        return False
    key = _event_debounce_key(reel_id, user_id, event_type)
    if _redis_available:
        try:
            val = cache_get(key)
            if val is not None:
                return True
        except Exception:
            pass
    with _DEBOUNCE_EVENTS_LOCK:
        last = _DEBOUNCE_EVENTS.get(key)
        now = time.time()
        if last and (now - last) < _REEL_EVENT_DEBOUNCE_SECONDS:
            return True
        _DEBOUNCE_EVENTS[key] = now
        if len(_DEBOUNCE_EVENTS) > 10000:
            cutoff = now - _REEL_EVENT_DEBOUNCE_SECONDS
            _DEBOUNCE_EVENTS = {k: v for k, v in _DEBOUNCE_EVENTS.items() if v > cutoff}
        return False


def _mark_event_debounce(reel_id, user_id, event_type):
    if _CHAIN_TEST_MODE:
        return
    key = _event_debounce_key(reel_id, user_id, event_type)
    if _redis_available:
        try:
            cache_set(key, "1", ttl=_REEL_EVENT_DEBOUNCE_SECONDS)
        except Exception:
            pass


def _flush_reel_events():
    global _REEL_EVENT_LAST_FLUSH
    now = time.time()
    if now - _REEL_EVENT_LAST_FLUSH < _REEL_EVENT_FLUSH_INTERVAL:
        return
    with _REEL_EVENT_LOCK:
        if now - _REEL_EVENT_LAST_FLUSH < _REEL_EVENT_FLUSH_INTERVAL:
            return
        batch = list(_REEL_EVENT_QUEUE)
        _REEL_EVENT_QUEUE.clear()
        _REEL_EVENT_LAST_FLUSH = now
    if not batch:
        return
    def _do_flush():
        for row in batch:
            try:
                write_query(
                    "INSERT INTO chain_reel_events (reel_id, user_id, event_type, watch_ms) VALUES (%s, %s, %s, %s)",
                    (row[0], row[1], row[2], row[3]),
                )
            except Exception:
                pass
    __import__("threading").Thread(target=_do_flush, daemon=True).start()


def track_reel_event(reel_id, user_id, event_type, watch_ms=0):
    """Tracks a reel event with debounce and batched flush."""
    if _check_event_debounce(reel_id, user_id, event_type):
        return True
    _mark_event_debounce(reel_id, user_id, event_type)
    with _REEL_EVENT_LOCK:
        _REEL_EVENT_QUEUE.append((reel_id, user_id, event_type, watch_ms))
    _flush_reel_events()
    return True


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
