"""Stories 2.0 Engine — highlights, analytics, privacy, close friends, interactions."""

import time
import json
import threading
from datetime import datetime, timezone, timedelta
from services.neon_service import fast_query, write_query

# ── Performance tracking ──
_PERF_CACHE = {}
_PERF_LOCK = threading.Lock()


def _track_timing(metric, ms):
    try:
        from services.performance_monitor import track_timing
        track_timing(metric, ms)
    except Exception:
        pass


def _track_cache(metric):
    try:
        from services.performance_monitor import track_counter
        track_counter(metric, 1)
    except Exception:
        pass


# ── Story Feed ──

def get_story_feed(viewer_id, limit=50):
    """Get grouped story feed: active stories from followed + own + public users with visibility checks."""
    t0 = time.time()
    try:
        viewer_id_int = int(viewer_id) if viewer_id else None
    except (ValueError, TypeError):
        viewer_id_int = None

    following_ids = []
    if viewer_id_int:
        rows = fast_query(
            "SELECT following_profile_id FROM chain_follows WHERE follower_profile_id = %s",
            (viewer_id_int,), default=[],
        )
        following_ids = [str(r[0]) if isinstance(r, (list, tuple)) else str(r["following_profile_id"]) for r in rows]

    close_friends = set()
    hidden_from = set()
    if viewer_id_int:
        cf = fast_query(
            "SELECT friend_id FROM chain_story_close_friends WHERE profile_id = %s",
            (viewer_id_int,), default=[],
        )
        close_friends = {str(r[0]) if isinstance(r, (list, tuple)) else str(r["friend_id"]) for r in cf}
        hf = fast_query(
            "SELECT hidden_user_id FROM chain_story_hidden_from WHERE profile_id = %s",
            (viewer_id_int,), default=[],
        )
        hidden_from = {str(r[0]) if isinstance(r, (list, tuple)) else str(r["hidden_user_id"]) for r in hf}

    now = _utcnow_iso()
    params = [now]
    sql = """
        SELECT s.*, p.display_name, p.username, p.avatar_url, p.is_verified
        FROM chain_status_posts s
        JOIN chain_profiles p ON p.id = s.profile_id
        WHERE s.expires_at > %s AND s.deleted_at IS NULL
    """

    if viewer_id_int:
        sql += """ AND (
            s.profile_id = %s
            OR (s.visibility = 'public')
            OR (s.visibility = 'followers' AND s.profile_id = ANY(%s))
            OR (s.visibility = 'close_friends' AND s.profile_id = ANY(%s))
            OR (s.visibility = 'custom' AND s.profile_id = ANY(%s))
        )"""
        params.extend([viewer_id_int,
                      following_ids if following_ids else [0],
                      list(close_friends) if close_friends else [0],
                      list(close_friends) if close_friends else [0],
        ])
    else:
        sql += " AND s.visibility = 'public'"

    if hidden_from and viewer_id_int:
        sql += " AND s.profile_id != ALL(%s)"
        params.append(list(hidden_from))

    sql += " ORDER BY s.created_at DESC LIMIT %s"
    params.append(limit)

    rows = fast_query(sql, tuple(params), default=[])

    viewed = set()
    if viewer_id_int:
        vrows = fast_query(
            "SELECT story_id FROM chain_story_views WHERE viewer_id = %s",
            (viewer_id_int,), default=[],
        )
        viewed = {str(r[0]) if isinstance(r, (list, tuple)) else str(r["story_id"]) for r in vrows}

    stories = []
    for r in rows:
        sid = str(r["id"])
        story = _normalize_story_row(r)
        story["viewed"] = sid in viewed
        story["can_reply"] = True
        if viewer_id_int:
            story["viewer_follows_creator"] = str(r.get("profile_id")) in following_ids
            story["is_close_friend"] = str(r.get("profile_id")) in close_friends
        else:
            story["viewer_follows_creator"] = False
            story["is_close_friend"] = False
        stories.append(story)

    _track_timing("stories.feed.ms", (time.time() - t0) * 1000)
    return stories


def get_grouped_stories(viewer_id, limit=50):
    """Get stories grouped by creator for tray display."""
    stories = get_story_feed(viewer_id, limit=limit)
    groups = {}
    for s in stories:
        pid = s["profile_id"]
        if pid not in groups:
            groups[pid] = {
                "profile_id": pid,
                "display_name": s.get("display_name", ""),
                "username": s.get("username", ""),
                "avatar_url": s.get("avatar_url", ""),
                "is_verified": s.get("is_verified", False),
                "stories": [],
                "all_viewed": True,
            }
        groups[pid]["stories"].append(s)
        if not s.get("viewed", True):
            groups[pid]["all_viewed"] = False

    # Sort: own stories first, then unviewed, then viewed
    ordered = list(groups.values())
    if viewer_id:
        ordered.sort(key=lambda g: (
            0 if str(g["profile_id"]) == str(viewer_id) else (1 if not g["all_viewed"] else 2),
            -len(g["stories"]),
        ))
    return ordered


def get_story_detail(story_id, viewer_id):
    """Single story with viewer state (viewed, liked, reacted)."""
    t0 = time.time()
    row = fast_query(
        """SELECT s.*, p.display_name, p.username, p.avatar_url, p.is_verified
           FROM chain_status_posts s
           JOIN chain_profiles p ON p.id = s.profile_id
           WHERE s.id = %s AND s.deleted_at IS NULL""",
        (story_id,), default=None,
    )
    if not row:
        return None
    r = row[0] if isinstance(row, list) else row
    story = _normalize_story_row(r)
    story["viewed"] = False
    story["viewer_reaction"] = None

    if viewer_id:
        v = fast_query(
            "SELECT reaction FROM chain_story_views WHERE story_id = %s AND viewer_id = %s",
            (story_id, viewer_id), default=[],
        )
        if v:
            story["viewed"] = True
            story["viewer_reaction"] = v[0][0] if isinstance(v[0], (list, tuple)) else v[0].get("reaction")

    _track_timing("stories.viewer.ms", (time.time() - t0) * 1000)
    return story


def get_stories_by_creator(creator_id, viewer_id, limit=20):
    """Get all active stories for a specific creator."""
    stories = get_story_feed(viewer_id, limit=limit)
    return [s for s in stories if str(s["profile_id"]) == str(creator_id)]


# ── Story View Tracking ──

def record_story_view_v2(story_id, viewer_id, reaction=None, reply_text=None):
    """Record a story view with optional reaction/reply. ON CONFLICT updates reaction."""
    if not viewer_id or not story_id:
        return False
    try:
        write_query(
            """INSERT INTO chain_story_views (story_id, viewer_id, reaction, reply_text)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (story_id, viewer_id)
               DO UPDATE SET reaction = COALESCE(%s, chain_story_views.reaction),
                             reply_text = COALESCE(%s, chain_story_views.reply_text)""",
            (story_id, viewer_id, reaction, reply_text, reaction, reply_text),
        )
        write_query(
            "UPDATE chain_status_posts SET views_count = (SELECT COUNT(*) FROM chain_story_views WHERE story_id = %s) WHERE id = %s",
            (story_id, story_id),
        )
        _emit_story_activity(viewer_id, story_id, "story_viewed", {"reaction": reaction})
        if reaction:
            _emit_story_activity(viewer_id, story_id, "story_reacted", {"reaction": reaction})
        _notify_story_creator("story_viewed", viewer_id, story_id)
        return True
    except Exception as e:
        _log_error("record_story_view_v2", e)
        return False


def record_story_analytics_event(story_id, viewer_id, event_type, metadata=None):
    """Record a granular analytics event (forward, back, exit)."""
    if not story_id:
        return
    try:
        write_query(
            "INSERT INTO chain_story_analytics_events (story_id, viewer_id, event_type, metadata) VALUES (%s, %s, %s, %s)",
            (story_id, viewer_id, event_type, json.dumps(metadata or {})),
        )
        col_map = {"forward": "forward_count", "back": "back_count", "exit": "exit_count"}
        col = col_map.get(event_type)
        if col:
            write_query(
                f"UPDATE chain_status_posts SET {col} = COALESCE({col}, 0) + 1 WHERE id = %s",
                (story_id,),
            )
    except Exception:
        pass


# ── Story Reactions ──

def react_to_story_v2(story_id, viewer_id, reaction):
    """Set emoji reaction on a story (like, love, laugh, wow, sad, angry)."""
    if not viewer_id or not story_id:
        return False
    try:
        write_query(
            "UPDATE chain_story_views SET reaction = %s WHERE story_id = %s AND viewer_id = %s",
            (reaction, story_id, viewer_id),
        )
        write_query(
            "UPDATE chain_status_posts SET reaction_count = (SELECT COUNT(*) FROM chain_story_views WHERE story_id = %s AND reaction IS NOT NULL) WHERE id = %s",
            (story_id, story_id),
        )
        _emit_story_activity(viewer_id, story_id, "story_reacted", {"reaction": reaction})
        _notify_story_creator("story_reacted", viewer_id, story_id)
        return True
    except Exception as e:
        _log_error("react_to_story_v2", e)
        return False


# ── Story Replies ──

def reply_to_story_v2(story_id, viewer_id, reply_text):
    """Reply to a story — creates a message thread reply + increments count."""
    if not viewer_id or not story_id or not reply_text:
        return False
    try:
        write_query(
            "UPDATE chain_story_views SET reply_text = %s WHERE story_id = %s AND viewer_id = %s",
            (reply_text, story_id, viewer_id),
        )
        write_query(
            "UPDATE chain_status_posts SET reply_count = (SELECT COUNT(*) FROM chain_story_views WHERE story_id = %s AND reply_text IS NOT NULL) WHERE id = %s",
            (story_id, story_id),
        )
        _emit_story_activity(viewer_id, story_id, "story_replied", {"reply_text": reply_text[:100]})
        _notify_story_creator("story_replied", viewer_id, story_id)

        # Create a message reply for private reply flow
        try:
            story = fast_query("SELECT profile_id FROM chain_status_posts WHERE id = %s", (story_id,), default=[])
            if story:
                owner_id = story[0][0] if isinstance(story[0], (list, tuple)) else story[0].get("profile_id")
                if str(owner_id) != str(viewer_id):
                    from services.messaging_service import send_message
                    send_message(
                        sender_id=viewer_id,
                        recipient_id=owner_id,
                        body=f"📸 Re: your story — {reply_text[:200]}",
                        message_type="story_reply",
                        metadata={"story_id": story_id},
                    )
        except Exception:
            pass
        return True
    except Exception as e:
        _log_error("reply_to_story_v2", e)
        return False


# ── Story Highlights ──

def create_highlight(profile_id, title, cover_url=None, story_ids=None):
    """Create a new story highlight."""
    if not profile_id:
        return None
    try:
        sort_order = fast_query(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM chain_story_highlights WHERE profile_id = %s",
            (profile_id,), default=[(0,)],
        )
        order = sort_order[0][0] if sort_order else 0
        row = write_query(
            """INSERT INTO chain_story_highlights (profile_id, title, cover_url, sort_order)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (profile_id, title, cover_url or "", order),
        )
        highlight_id = None
        if row and hasattr(row, 'fetchone'):
            highlight_id = row.fetchone()[0]
        if not highlight_id:
            hl = fast_query(
                "SELECT id FROM chain_story_highlights WHERE profile_id = %s ORDER BY id DESC LIMIT 1",
                (profile_id,), default=[],
            )
            highlight_id = hl[0][0] if hl else None

        if highlight_id and story_ids:
            add_stories_to_highlight(highlight_id, story_ids)
        return {"id": highlight_id, "title": title, "cover_url": cover_url or "", "sort_order": order}
    except Exception as e:
        _log_error("create_highlight", e)
        return None


def get_highlights(profile_id, viewer_id=None):
    """Get all highlights for a profile with their stories."""
    if not profile_id:
        return []
    try:
        rows = fast_query(
            """SELECT h.*, COALESCE(
                (SELECT s.thumbnail_url FROM chain_story_highlight_items hi
                 JOIN chain_status_posts s ON s.id = hi.story_id
                 WHERE hi.highlight_id = h.id ORDER BY hi.sort_order LIMIT 1), '') AS cover
               FROM chain_story_highlights h
               WHERE h.profile_id = %s
               ORDER BY h.sort_order ASC""",
            (profile_id,), default=[],
        )
        highlights = []
        for r in rows:
            hl = {
                "id": r["id"] if isinstance(r, dict) else r[0],
                "profile_id": r["profile_id"] if isinstance(r, dict) else r[1],
                "title": r["title"] if isinstance(r, dict) else r[2],
                "cover_url": (r.get("cover_url") or r.get("cover") or "") if isinstance(r, dict) else (r[3] or r[-1] or ""),
                "sort_order": r["sort_order"] if isinstance(r, dict) else r[4],
                "story_count": 0,
            }
            hl["story_count"] = fast_query(
                "SELECT COUNT(*) FROM chain_story_highlight_items WHERE highlight_id = %s",
                (hl["id"],), default=[(0,)],
            )[0][0] or 0
            highlights.append(hl)
        return highlights
    except Exception as e:
        _log_error("get_highlights", e)
        return []


def get_highlight_detail(highlight_id, viewer_id=None):
    """Get highlight with its stories."""
    try:
        row = fast_query(
            "SELECT * FROM chain_story_highlights WHERE id = %s", (highlight_id,), default=None,
        )
        if not row:
            return None
        r = row[0] if isinstance(row, list) else row
        hl = {
            "id": r["id"] if isinstance(r, dict) else r[0],
            "profile_id": r["profile_id"] if isinstance(r, dict) else r[1],
            "title": r["title"] if isinstance(r, dict) else r[2],
            "cover_url": r.get("cover_url", "") if isinstance(r, dict) else (r[3] or ""),
            "sort_order": r["sort_order"] if isinstance(r, dict) else r[4],
        }
        items = fast_query(
            """SELECT hi.*, s.*, p.display_name, p.username, p.avatar_url
               FROM chain_story_highlight_items hi
               JOIN chain_status_posts s ON s.id = hi.story_id
               JOIN chain_profiles p ON p.id = s.profile_id
               WHERE hi.highlight_id = %s
               ORDER BY hi.sort_order ASC""",
            (highlight_id,), default=[],
        )
        hl["stories"] = [_normalize_story_row(i) for i in items]
        return hl
    except Exception as e:
        _log_error("get_highlight_detail", e)
        return None


def update_highlight(highlight_id, title=None, cover_url=None):
    """Update highlight title/cover."""
    try:
        if title:
            write_query("UPDATE chain_story_highlights SET title = %s, updated_at = now() WHERE id = %s",
                       (title, highlight_id))
        if cover_url:
            write_query("UPDATE chain_story_highlights SET cover_url = %s, updated_at = now() WHERE id = %s",
                       (cover_url, highlight_id))
        return True
    except Exception as e:
        _log_error("update_highlight", e)
        return False


def delete_highlight(highlight_id, profile_id):
    """Delete a highlight (owner only)."""
    try:
        write_query(
            "DELETE FROM chain_story_highlights WHERE id = %s AND profile_id = %s",
            (highlight_id, profile_id),
        )
        return True
    except Exception:
        return False


def reorder_highlights(profile_id, highlight_ids):
    """Reorder highlights by provided ID list."""
    try:
        for idx, hid in enumerate(highlight_ids):
            write_query(
                "UPDATE chain_story_highlights SET sort_order = %s WHERE id = %s AND profile_id = %s",
                (idx, hid, profile_id),
            )
        return True
    except Exception:
        return False


def add_stories_to_highlight(highlight_id, story_ids):
    """Add stories to a highlight."""
    try:
        for i, sid in enumerate(story_ids):
            write_query(
                """INSERT INTO chain_story_highlight_items (highlight_id, story_id, sort_order)
                   VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                (highlight_id, sid, i),
            )
        return True
    except Exception:
        return False


def remove_story_from_highlight(highlight_id, story_id):
    """Remove a story from a highlight."""
    try:
        write_query(
            "DELETE FROM chain_story_highlight_items WHERE highlight_id = %s AND story_id = %s",
            (highlight_id, story_id),
        )
        return True
    except Exception:
        return False


# ── Close Friends ──

def add_close_friend(profile_id, friend_id):
    """Add a user to close friends list."""
    try:
        write_query(
            "INSERT INTO chain_story_close_friends (profile_id, friend_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (profile_id, friend_id),
        )
        return True
    except Exception:
        return False


def remove_close_friend(profile_id, friend_id):
    """Remove a user from close friends list."""
    try:
        write_query(
            "DELETE FROM chain_story_close_friends WHERE profile_id = %s AND friend_id = %s",
            (profile_id, friend_id),
        )
        return True
    except Exception:
        return False


def get_close_friends(profile_id):
    """Get list of close friends."""
    try:
        rows = fast_query(
            """SELECT cf.friend_id, p.display_name, p.username, p.avatar_url
               FROM chain_story_close_friends cf
               JOIN chain_profiles p ON p.id = cf.friend_id
               WHERE cf.profile_id = %s
               ORDER BY cf.created_at DESC""",
            (profile_id,), default=[],
        )
        return [{"id": r[0], "display_name": r[1], "username": r[2], "avatar_url": r[3]} for r in rows]
    except Exception:
        return []


# ── Hidden Users ──

def hide_story_from(profile_id, hidden_user_id):
    """Hide your stories from a specific user."""
    try:
        write_query(
            "INSERT INTO chain_story_hidden_from (profile_id, hidden_user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (profile_id, hidden_user_id),
        )
        return True
    except Exception:
        return False


def unhide_story_from(profile_id, hidden_user_id):
    """Stop hiding stories from a user."""
    try:
        write_query(
            "DELETE FROM chain_story_hidden_from WHERE profile_id = %s AND hidden_user_id = %s",
            (profile_id, hidden_user_id),
        )
        return True
    except Exception:
        return False


def get_hidden_users(profile_id):
    """Get list of users hidden from."""
    try:
        rows = fast_query(
            """SELECT hf.hidden_user_id, p.display_name, p.username, p.avatar_url
               FROM chain_story_hidden_from hf
               JOIN chain_profiles p ON p.id = hf.hidden_user_id
               WHERE hf.profile_id = %s
               ORDER BY hf.created_at DESC""",
            (profile_id,), default=[],
        )
        return [{"id": r[0], "display_name": r[1], "username": r[2], "avatar_url": r[3]} for r in rows]
    except Exception:
        return []


# ── Story Analytics ──

def get_story_analytics(story_id, viewer_id):
    """Get analytics for a single story (owner only)."""
    if not viewer_id:
        return None
    try:
        story = fast_query(
            "SELECT profile_id FROM chain_status_posts WHERE id = %s", (story_id,), default=[]
        )
        if not story or str(story[0][0] if isinstance(story[0], (list, tuple)) else story[0]["profile_id"]) != str(viewer_id):
            return None

        views = fast_query(
            """SELECT v.*, p.display_name, p.username, p.avatar_url
               FROM chain_story_views v
               JOIN chain_profiles p ON p.id = v.viewer_id
               WHERE v.story_id = %s
               ORDER BY v.created_at DESC LIMIT 100""",
            (story_id,), default=[],
        )

        events = fast_query(
            "SELECT event_type, COUNT(*) AS cnt FROM chain_story_analytics_events WHERE story_id = %s GROUP BY event_type",
            (story_id,), default=[],
        )
        event_map = {r[0]: r[1] for r in events} if events else {}

        reactions = fast_query(
            "SELECT reaction, COUNT(*) AS cnt FROM chain_story_views WHERE story_id = %s AND reaction IS NOT NULL GROUP BY reaction",
            (story_id,), default=[],
        )
        reaction_map = {r[0]: r[1] for r in reactions} if reactions else {}

        return {
            "total_views": len(views),
            "unique_viewers": len(set(str(v.get("viewer_id") if isinstance(v, dict) else v[1]) for v in views)),
            "forward_taps": event_map.get("forward", 0),
            "back_taps": event_map.get("back", 0),
            "exits": event_map.get("exit", 0),
            "reactions": reaction_map,
            "total_reactions": sum(reaction_map.values()),
            "replies": sum(1 for v in views if (v.get("reply_text") if isinstance(v, dict) else v[5])),
            "viewers": [
                {
                    "viewer_id": str(v.get("viewer_id") if isinstance(v, dict) else v[1]),
                    "display_name": v.get("display_name") if isinstance(v, dict) else v[6],
                    "username": v.get("username") if isinstance(v, dict) else v[7],
                    "avatar_url": v.get("avatar_url") if isinstance(v, dict) else v[8],
                    "reaction": v.get("reaction") if isinstance(v, dict) else v[3],
                    "reply_text": v.get("reply_text") if isinstance(v, dict) else v[4],
                    "viewed_at": str(v.get("created_at") if isinstance(v, dict) else v[2]),
                }
                for v in views
            ],
        }
    except Exception as e:
        _log_error("get_story_analytics", e)
        return None


def get_creator_story_stats(creator_id, requesting_profile_id=None):
    """Aggregate story stats for a creator (own stats only)."""
    if not creator_id or str(creator_id) != str(requesting_profile_id):
        return {
            "total_stories": 0, "total_views": 0, "total_reactions": 0,
            "total_replies": 0, "avg_completion_rate": 0,
        }
    try:
        stats = fast_query(
            """SELECT COUNT(*) AS total,
                      COALESCE(SUM(views_count), 0) AS total_views,
                      COALESCE(SUM(reaction_count), 0) AS total_reactions,
                      COALESCE(SUM(reply_count), 0) AS total_replies
               FROM chain_status_posts
               WHERE profile_id = %s AND deleted_at IS NULL AND expires_at > now()""",
            (creator_id,), default=[(0, 0, 0, 0)],
        )
        r = stats[0] if stats else (0, 0, 0, 0)
        completion = fast_query(
            "SELECT COALESCE(AVG(completion_rate), 0) FROM chain_status_posts WHERE profile_id = %s AND deleted_at IS NULL AND expires_at > now()",
            (creator_id,), default=[(0,)],
        )
        return {
            "total_stories": r[0] or 0,
            "total_views": r[1] or 0,
            "total_reactions": r[2] or 0,
            "total_replies": r[3] or 0,
            "avg_completion_rate": round(completion[0][0] if completion else 0, 4),
        }
    except Exception as e:
        _log_error("get_creator_story_stats", e)
        return {}


# ── Privacy ──

def can_view_story_v2(story_id, viewer_id):
    """Comprehensive privacy check returning (allowed, reason)."""
    if not story_id:
        return False, "not_found"
    try:
        story = fast_query(
            "SELECT * FROM chain_status_posts WHERE id = %s AND deleted_at IS NULL",
            (story_id,), default=None,
        )
        if not story:
            return False, "not_found"
        s = story[0] if isinstance(story, list) else story
        if isinstance(s, dict):
            sid = str(s["profile_id"])
            visibility = s.get("visibility", "public")
        else:
            sid = str(s[1])
            visibility = str(s[5]) if len(s) > 5 else "public"

        expires_at = s.get("expires_at") if isinstance(s, dict) else s[4]
        if expires_at:
            parsed = _parse_dt(expires_at)
            if parsed and parsed < datetime.now(timezone.utc):
                return False, "expired"

        if not viewer_id:
            return visibility == "public", "private_story" if visibility != "public" else "ok"

        if str(viewer_id) == sid:
            return True, "ok"

        if visibility == "private":
            return False, "private_story"

        if visibility == "public":
            hidden = fast_query(
                "SELECT 1 FROM chain_story_hidden_from WHERE profile_id = %s AND hidden_user_id = %s",
                (sid, viewer_id), default=[],
            )
            if hidden:
                return False, "hidden_from_user"
            return True, "ok"

        if visibility == "followers":
            is_following = fast_query(
                "SELECT 1 FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s",
                (viewer_id, sid), default=[],
            )
            if not is_following:
                return False, "not_following"
            hidden = fast_query(
                "SELECT 1 FROM chain_story_hidden_from WHERE profile_id = %s AND hidden_user_id = %s",
                (sid, viewer_id), default=[],
            )
            if hidden:
                return False, "hidden_from_user"
            return True, "ok"

        if visibility == "close_friends":
            is_cf = fast_query(
                "SELECT 1 FROM chain_story_close_friends WHERE profile_id = %s AND friend_id = %s",
                (sid, viewer_id), default=[],
            )
            if not is_cf:
                return False, "not_close_friend"
            return True, "ok"

        if visibility == "custom":
            is_cf2 = fast_query(
                "SELECT 1 FROM chain_story_close_friends WHERE profile_id = %s AND friend_id = %s",
                (sid, viewer_id), default=[],
            )
            if not is_cf2:
                return False, "not_in_custom_list"
            return True, "ok"

        return True, "ok"
    except Exception:
        return False, "error"


# ── Story creation ──

def create_story_v2(profile_id, media_type="image", media_url=None, caption="",
                    visibility="public", duration_seconds=10, background_color=None,
                    text_content=None, music_title=None, music_url=None,
                    location_name=None, mentions=None, hashtags=None, link_url=None):
    """Create a story with full metadata."""
    if not profile_id:
        return None, "profile_required"
    if not media_url and not text_content:
        return None, "media_or_text_required"

    now = _utcnow_iso()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

    try:
        import uuid
        story_id = str(uuid.uuid4())
        mentions_json = json.dumps(mentions or [])
        hashtags_json = json.dumps(hashtags or [])

        write_query(
            """INSERT INTO chain_status_posts
               (id, profile_id, media_type, caption, visibility, expires_at,
                background_color, text_content, music_title, music_url,
                location_name, mentions, hashtags, link_url, media_url, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)""",
            (story_id, profile_id, media_type, caption, visibility, expires_at,
             background_color, text_content, music_title, music_url,
             location_name, mentions_json, hashtags_json, link_url, media_url or ""),
        )
        _emit_story_activity(profile_id, story_id, "story_created", {
            "media_type": media_type, "visibility": visibility,
        })
        return {"id": story_id, "expires_at": expires_at}, None
    except Exception as e:
        _log_error("create_story_v2", e)
        return None, str(e)


# ── Story deletion ──

def delete_story_v2(story_id, profile_id):
    """Soft delete a story (owner only)."""
    try:
        write_query(
            "UPDATE chain_status_posts SET deleted_at = now() WHERE id = %s AND profile_id = %s",
            (story_id, profile_id),
        )
        return True
    except Exception:
        return False


# ── Story viewers ──

def get_story_viewers(story_id, requesting_profile_id=None):
    """Get viewers list (owner only returns detailed, others get count)."""
    try:
        story = fast_query("SELECT profile_id FROM chain_status_posts WHERE id = %s", (story_id,), default=[])
        if not story:
            return {"viewers": [], "count": 0}
        owner_id = story[0][0] if isinstance(story[0], (list, tuple)) else story[0]["profile_id"]
        is_owner = str(owner_id) == str(requesting_profile_id) if requesting_profile_id else False

        rows = fast_query(
            """SELECT v.viewer_id, v.reaction, v.reply_text, v.created_at,
                      p.display_name, p.username, p.avatar_url
               FROM chain_story_views v
               JOIN chain_profiles p ON p.id = v.viewer_id
               WHERE v.story_id = %s
               ORDER BY v.created_at DESC LIMIT 50""",
            (story_id,), default=[],
        )
        count = len(rows) if rows else 0
        if not rows:
            return {"viewers": [], "count": 0}
        if is_owner:
            viewers = [
                {
                    "viewer_id": str(r[0]),
                    "display_name": r[4],
                    "username": r[5],
                    "avatar_url": r[6],
                    "reaction": r[1],
                    "reply_text": r[2],
                    "viewed_at": str(r[3]),
                }
                for r in rows
            ]
        else:
            viewers = [{"viewer_id": str(r[0])} for r in rows]
        return {"viewers": viewers, "count": count}
    except Exception as e:
        _log_error("get_story_viewers", e)
        return {"viewers": [], "count": 0}


# ── Activity / Notifications ──

def _emit_story_activity(actor_id, story_id, verb, extra_meta=None):
    if not actor_id:
        return
    try:
        from services.activity_engine import emit_activity
        meta = {"story_id": story_id}
        if extra_meta:
            meta.update(extra_meta)
        emit_activity(
            actor_id=actor_id,
            verb=verb,
            entity_type="story",
            entity_id=story_id,
            metadata=meta,
        )
    except Exception:
        pass


def _notify_story_creator(verb, actor_id, story_id):
    """Notify story creator about engagement."""
    try:
        from services.notification_center_service import create_notification
        story = fast_query(
            "SELECT profile_id FROM chain_status_posts WHERE id = %s", (story_id,), default=[]
        )
        if story and story[0][0]:
            owner_id = story[0][0] if isinstance(story[0], (list, tuple)) else story[0]["profile_id"]
            if str(owner_id) != str(actor_id):
                notification_type = verb
                create_notification(
                    profile_id=owner_id,
                    notification_type=notification_type,
                    actor_id=actor_id,
                    entity_type="story",
                    entity_id=story_id,
                    grouped=True,
                )
    except Exception:
        pass


def _normalize_story_row(r):
    """Normalize a story DB row to a clean dict."""
    if hasattr(r, "_mapping"):
        r = dict(r._mapping)
    elif not isinstance(r, dict):
        cols = ["id", "profile_id", "media_type", "caption", "media_url", "visibility",
                "expires_at", "created_at", "background_color", "text_content",
                "music_title", "music_url", "location_name", "mentions", "hashtags",
                "link_url", "views_count", "likes_count", "reaction_count", "reply_count",
                "forward_count", "back_count", "exit_count", "completion_rate",
                "display_name", "username", "avatar_url", "is_verified"]
        r = dict(zip(cols, r)) if len(r) >= len(cols) else {k: "" for k in cols}

    return {
        "id": str(r.get("id", "")),
        "profile_id": str(r.get("profile_id", "")),
        "display_name": r.get("display_name", ""),
        "username": r.get("username", ""),
        "avatar_url": r.get("avatar_url", ""),
        "is_verified": bool(r.get("is_verified", False)),
        "media_type": r.get("media_type", "image"),
        "caption": r.get("caption", ""),
        "media_url": r.get("media_url", ""),
        "thumbnail_url": r.get("thumbnail_url", "") or r.get("media_url", ""),
        "visibility": r.get("visibility", "public"),
        "expires_at": str(r.get("expires_at", "")),
        "created_at": str(r.get("created_at", "")),
        "background_color": r.get("background_color", ""),
        "text_content": r.get("text_content", ""),
        "music_title": r.get("music_title", ""),
        "music_url": r.get("music_url", ""),
        "location_name": r.get("location_name", ""),
        "mentions": r.get("mentions", []),
        "hashtags": r.get("hashtags", []),
        "link_url": r.get("link_url", ""),
        "views_count": r.get("views_count", 0) or 0,
        "likes_count": r.get("likes_count", 0) or 0,
        "reaction_count": r.get("reaction_count", 0) or 0,
        "reply_count": r.get("reply_count", 0) or 0,
        "forward_count": r.get("forward_count", 0) or 0,
        "back_count": r.get("back_count", 0) or 0,
        "exit_count": r.get("exit_count", 0) or 0,
        "completion_rate": float(r.get("completion_rate", 0) or 0),
        "viewed": False,
        "viewer_reaction": None,
        "can_reply": True,
    }


# ── Helpers ──

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _log_error(context, exc):
    import logging
    logging.getLogger("stories_engine").exception("[%s] %s", context, exc)
