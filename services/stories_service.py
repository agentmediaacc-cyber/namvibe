"""Stories V2 service with polls, reactions, replies, and 24h expiry."""
from datetime import datetime, timezone, timedelta
import json
from services.neon_service import fast_query, write_query
from services.status_service import get_status, delete_status, expire_old_statuses

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def get_stories_feed(viewer_id=None):
    now = _utcnow_iso()
    query = """
        SELECT s.*, p.username, p.avatar_url, p.is_verified,
               COALESCE(s.likes_count, 0) AS likes_count,
               COALESCE(s.comments_count, 0) AS comments_count,
               COALESCE(s.views_count, 0) AS views_count,
               (SELECT COUNT(*) FROM chain_story_views WHERE story_id = s.id) AS viewer_count
        FROM chain_status_posts s
        JOIN chain_profiles p ON s.profile_id = p.id
        WHERE s.expires_at > %s AND s.deleted_at IS NULL
          AND s.visibility = 'public'
        ORDER BY s.created_at DESC
        LIMIT 50
    """
    return fast_query(query, (now,), timeout_ms=2000, default=[]) or []

def get_story_with_views(story_id):
    story = get_status(story_id)
    if not story:
        return None
    views = fast_query(
        """SELECT v.*, p.username, p.avatar_url
           FROM chain_story_views v
           JOIN chain_profiles p ON v.viewer_id = p.id
           WHERE v.story_id = %s ORDER BY v.created_at DESC LIMIT 50""",
        (story_id,), timeout_ms=2000, default=[]
    )
    story["views"] = views or []
    polls = fast_query(
        "SELECT * FROM chain_story_polls WHERE story_id = %s ORDER BY created_at DESC",
        (story_id,), timeout_ms=2000, default=[]
    )
    story["polls"] = polls or []
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
        return True
    except Exception:
        return False

def reply_to_story(story_id, viewer_id, reply_text):
    try:
        write_query(
            "UPDATE chain_story_views SET reply_text = %s WHERE story_id = %s AND viewer_id = %s",
            (reply_text, story_id, viewer_id)
        )
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
    poll = fast_query("SELECT * FROM chain_story_polls WHERE id = %s", (poll_id,), timeout_ms=2000, default=[])
    if not poll:
        return None
    poll = poll[0]
    votes = fast_query(
        "SELECT option_index, COUNT(*) AS count FROM chain_story_poll_votes WHERE poll_id = %s GROUP BY option_index",
        (poll_id,), timeout_ms=2000, default=[]
    )
    poll["votes"] = votes or []
    return poll
