"""Stories V2 service with polls, reactions, replies, and 24h expiry."""
from datetime import datetime, timezone, timedelta
import json
from services.neon_service import fast_query, write_query
from services.status_service import get_status, delete_status, expire_old_statuses
from engines.cache_engine import cache_key, get_cache, set_cache, delete_cache

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def get_stories_feed(viewer_id=None):
    """Get stories feed with proper visibility filtering.
    
    Visibility rules:
    - public: everyone can see
    - followers: only followers can see
    - private: only owner can see
    """
    now = _utcnow_iso()
    profile_id_param = str(viewer_id) if viewer_id else None
    
    # Check cache first (short TTL for fresh stories)
    cache_key_str = cache_key("stories_feed", profile_id_param or "public", 30, 0)
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached
    
    # Optimized query: use LEFT JOIN for viewer count instead of a subquery,
    # batch the follow checks via a CTE when viewer is known, and only SELECT
    # the columns that are actually needed instead of all.
    params = [now]
    
    if profile_id_param:
        # For authenticated users, precompute followed profiles in a CTE
        query = f"""
            WITH follow_map AS (
                SELECT following_profile_id FROM chain_follows
                WHERE follower_profile_id = %s AND deleted_at IS NULL
            )
            SELECT s.id, s.profile_id, s.body, s.media_url, s.media_type, s.visibility,
                   s.expires_at, s.created_at, s.updated_at,
                   p.username, p.avatar_url, p.is_verified,
                   COALESCE(s.likes_count, 0) AS likes_count,
                   COALESCE(s.comments_count, 0) AS comments_count,
                   COALESCE(s.views_count, 0) AS views_count,
                   COUNT(sv.story_id) AS viewer_count
            FROM chain_status_posts s
            JOIN chain_profiles p ON s.profile_id = p.id
            LEFT JOIN chain_story_views sv ON sv.story_id = s.id
            WHERE s.expires_at > %s AND s.deleted_at IS NULL
              AND (
                  s.profile_id = %s
                  OR s.visibility = 'public'
                  OR (s.visibility = 'followers' AND s.profile_id IN (SELECT following_profile_id FROM follow_map))
              )
            GROUP BY s.id, s.profile_id, s.body, s.media_url, s.media_type, s.visibility,
                     s.expires_at, s.created_at, s.updated_at,
                     p.username, p.avatar_url, p.is_verified,
                     s.likes_count, s.comments_count, s.views_count
            ORDER BY s.created_at DESC
            LIMIT 50
        """
        params = [profile_id_param, now, profile_id_param]
    else:
        # No viewer - only public stories, simplified query
        query = """
            SELECT s.id, s.profile_id, s.body, s.media_url, s.media_type, s.visibility,
                   s.expires_at, s.created_at, s.updated_at,
                   p.username, p.avatar_url, p.is_verified,
                   COALESCE(s.likes_count, 0) AS likes_count,
                   COALESCE(s.comments_count, 0) AS comments_count,
                   COALESCE(s.views_count, 0) AS views_count,
                   COUNT(sv.story_id) AS viewer_count
            FROM chain_status_posts s
            JOIN chain_profiles p ON s.profile_id = p.id
            LEFT JOIN chain_story_views sv ON sv.story_id = s.id
            WHERE s.expires_at > %s AND s.deleted_at IS NULL
              AND s.visibility = 'public'
            GROUP BY s.id, s.profile_id, s.body, s.media_url, s.media_type, s.visibility,
                     s.expires_at, s.created_at, s.updated_at,
                     p.username, p.avatar_url, p.is_verified,
                     s.likes_count, s.comments_count, s.views_count
            ORDER BY s.created_at DESC
            LIMIT 50
        """
        params = [now]
    
    results = fast_query(query, params, timeout_ms=2000, default=[]) or []
    
    # Cache for 30 seconds (stories are time-sensitive)
    set_cache(cache_key_str, results, ttl=30)
    return results

def get_story_with_views(story_id):
    story = get_status(story_id)
    if not story:
        return None
    
    # Cache story views for 10 seconds
    cache_key_str = cache_key("story_views", story_id, 10, 0)
    cached = get_cache(cache_key_str)
    if cached is not None:
        story["views"] = cached
    else:
        views = fast_query(
            """SELECT v.viewer_id, v.reaction, v.reply_text, v.created_at, p.username, p.avatar_url
               FROM chain_story_views v
               LEFT JOIN chain_profiles p ON v.viewer_id = p.id
               WHERE v.story_id = %s ORDER BY v.created_at DESC LIMIT 50""",
            (story_id,), timeout_ms=2000, default=[]
        )
        story["views"] = views or []
        set_cache(cache_key_str, story["views"], ttl=10)
    
    # Cache polls for 30 seconds
    cache_key_str = cache_key("story_polls", story_id, 30, 0)
    cached_polls = get_cache(cache_key_str)
    if cached_polls is not None:
        story["polls"] = cached_polls
    else:
        polls = fast_query(
            "SELECT id, question, options_json, created_at FROM chain_story_polls WHERE story_id = %s ORDER BY created_at DESC",
            (story_id,), timeout_ms=2000, default=[]
        )
        story["polls"] = polls or []
        set_cache(cache_key_str, story["polls"], ttl=30)
    
    return story

def record_story_view(story_id, viewer_id, reaction=None):
    try:
        write_query(
            "INSERT INTO chain_story_views (story_id, viewer_id, reaction) VALUES (%s, %s, %s)",
            (story_id, viewer_id, reaction)
        )
        write_query(
            "UPDATE chain_status_posts SET views_count = COALESCE(views_count, 0) + 1 WHERE id = %s",
            (story_id,)
        )
        # Invalidate cache for this story's views
        delete_cache(cache_key("story_views", story_id, 10, 0))
        try:
            from services.socketio_service import emit_to_profile
            story = fast_query(
                "SELECT profile_id FROM chain_status_posts WHERE id = %s",
                (story_id,), timeout_ms=1000, default=[]
            )
            if story and str(story[0].get('profile_id', '')) != str(viewer_id):
                emit_to_profile(story[0]['profile_id'], "status:viewed", {
                    "status_id": story_id,
                    "viewer_id": viewer_id
                })
        except Exception:
            pass
        return True
    except Exception:
        return False

def react_to_story(story_id, viewer_id, reaction):
    try:
        write_query(
            "UPDATE chain_story_views SET reaction = %s WHERE story_id = %s AND viewer_id = %s",
            (reaction, story_id, viewer_id)
        )
        write_query(
            "UPDATE chain_status_posts SET likes_count = COALESCE(likes_count, 0) + 1 WHERE id = %s",
            (story_id,)
        )
        # Invalidate caches
        delete_cache(cache_key("story_views", story_id, 10, 0))
        delete_cache(cache_key("stories_feed", "public", 30, 0))
        return True
    except Exception:
        return False

def reply_to_story(story_id, viewer_id, reply_text):
    try:
        write_query(
            "UPDATE chain_story_views SET reply_text = %s WHERE story_id = %s AND viewer_id = %s",
            (reply_text, story_id, viewer_id)
        )
        delete_cache(cache_key("story_views", story_id, 10, 0))
        return True
    except Exception:
        return False

def create_story_poll(story_id, question, options, created_by, expires_at=None):
    import uuid
    poll_id = str(uuid.uuid4())
    if not expires_at:
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    try:
        write_query(
            "INSERT INTO chain_story_polls (id, story_id, question, options_json, created_by, expires_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (poll_id, story_id, question, json.dumps(options), created_by, expires_at)
        )
        delete_cache(cache_key("story_polls", story_id, 30, 0))
        return poll_id
    except Exception:
        return None

def vote_story_poll(poll_id, user_id, option_index):
    try:
        write_query(
            "INSERT INTO chain_story_poll_votes (poll_id, user_id, option_index) VALUES (%s, %s, %s)",
            (poll_id, user_id, option_index)
        )
        return True
    except Exception:
        return False

def get_poll_results(poll_id):
    cache_key_str = cache_key("poll_results", poll_id, 30, 0)
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached
    
    poll = fast_query("SELECT id, question, options_json FROM chain_story_polls WHERE id = %s", (poll_id,), timeout_ms=2000, default=[])
    if not poll:
        return None
    poll = poll[0]
    votes = fast_query(
        "SELECT option_index, COUNT(*) AS count FROM chain_story_poll_votes WHERE poll_id = %s GROUP BY option_index",
        (poll_id,), timeout_ms=2000, default=[]
    )
    poll["votes"] = votes or []
    set_cache(cache_key_str, poll, ttl=30)
    return poll