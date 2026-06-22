"""Story engagement: views, reactions, replies."""

from services.neon_service import write_query, fast_query
from services.notification_service import create_notification


def get_tray(profile_id, limit=20):
    """Fetch active (non-expired) stories from followed users."""
    following = _following_ids(profile_id)
    if not following:
        return []

    rows = fast_query(
        """SELECT s.id, s.profile_id, s.media_url, s.media_type, s.caption,
                  s.expires_at, s.created_at, s.views_count, s.likes_count,
                  COALESCE(pr.display_name, pr.username) AS creator_name,
                  pr.avatar_url AS creator_avatar
           FROM chain_status_posts s
           JOIN chain_profiles pr ON pr.id = s.profile_id
           WHERE s.profile_id = ANY(%s)
             AND s.expires_at > now()
             AND s.deleted_at IS NULL
           ORDER BY s.created_at DESC LIMIT %s""",
        (following, limit), default=[],
    )

    result = []
    for row in rows:
        story = _normalize_story(row)
        story["viewed"] = _has_viewed(story["id"], profile_id)
        result.append(story)
    return result


def record_view(story_id, viewer_id):
    try:
        write_query(
            """INSERT INTO chain_story_views (story_id, viewer_id)
               VALUES (%s, %s) ON CONFLICT (story_id, viewer_id) DO NOTHING""",
            (story_id, viewer_id),
        )
        write_query(
            """UPDATE chain_status_posts SET views_count = (
                SELECT COUNT(*) FROM chain_story_views WHERE story_id = %s
            ) WHERE id = %s""",
            (story_id, story_id),
        )
    except Exception:
        pass


def get_viewers(story_id):
    rows = fast_query(
        """SELECT v.viewer_id, v.viewed_at,
                  COALESCE(pr.display_name, pr.username) AS viewer_name,
                  pr.avatar_url AS viewer_avatar
           FROM chain_story_views v
           JOIN chain_profiles pr ON pr.id = v.viewer_id
           WHERE v.story_id = %s
           ORDER BY v.viewed_at DESC""",
        (story_id,), default=[],
    )
    result = []
    for r in rows:
        result.append({
            "viewer_id": str(r["viewer_id"]),
            "viewed_at": r["viewed_at"].isoformat() if r.get("viewed_at") else None,
            "viewer_name": r.get("viewer_name", ""),
            "viewer_avatar": r.get("viewer_avatar", ""),
        })
    return result


def set_reaction(story_id, user_id, reaction):
    try:
        existing = fast_query(
            "SELECT id, reaction FROM chain_story_reactions WHERE story_id = %s AND user_id = %s",
            (story_id, user_id), default=[],
        )
        if existing:
            write_query(
                "UPDATE chain_story_reactions SET reaction = %s, updated_at = now() WHERE id = %s",
                (reaction, existing[0]["id"]),
            )
        else:
            write_query(
                "INSERT INTO chain_story_reactions (story_id, user_id, reaction) VALUES (%s, %s, %s)",
                (story_id, user_id, reaction),
            )

        story = fast_query(
            "SELECT profile_id FROM chain_status_posts WHERE id = %s", (story_id,), default=[]
        )
        if story and str(story[0]["profile_id"]) != str(user_id):
            create_notification(
                profile_id=str(story[0]["profile_id"]),
                notification_type="story_reaction",
                title="New story reaction",
                body=f"{reaction} on your story",
                metadata={"story_id": story_id, "reaction": reaction},
            )
    except Exception:
        pass


def get_reactions(story_id):
    rows = fast_query(
        "SELECT user_id, reaction, created_at FROM chain_story_reactions WHERE story_id = %s ORDER BY created_at DESC",
        (story_id,), default=[],
    )
    return [
        {
            "user_id": str(r["user_id"]),
            "reaction": r["reaction"],
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
        }
        for r in rows
    ]


def send_reply(story_id, sender_id, body):
    owner = fast_query(
        "SELECT profile_id FROM chain_status_posts WHERE id = %s", (story_id,), default=[]
    )
    if not owner:
        return {"ok": False, "error": "story_not_found"}
    owner_id = str(owner[0]["profile_id"])

    if str(sender_id) == owner_id:
        return {"ok": False, "error": "cannot_reply_to_own_story"}

    try:
        write_query(
            """INSERT INTO chain_story_replies (story_id, sender_id, owner_id, body)
               VALUES (%s, %s, %s, %s)""",
            (story_id, sender_id, owner_id, body),
        )
        create_notification(
            profile_id=owner_id,
            notification_type="story_reply",
            title="Story reply",
            body=body[:100],
            metadata={"story_id": story_id, "sender_id": sender_id},
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def delete_story(story_id, profile_id):
    try:
        story = fast_query(
            "SELECT profile_id FROM chain_status_posts WHERE id = %s", (story_id,), default=[]
        )
        if not story:
            return {"ok": False, "error": "not_found"}
        if str(story[0]["profile_id"]) != str(profile_id):
            return {"ok": False, "error": "unauthorized"}
        write_query("UPDATE chain_status_posts SET deleted_at = now() WHERE id = %s", (story_id,))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_tray_for_story_page(profile_id, limit=20):
    """Fetch active story tray for the stories page including own stories."""
    following = _following_ids(profile_id)

    if not following:
        rows = fast_query(
            """SELECT s.id, s.profile_id, s.media_url, s.media_type, s.caption,
                      s.expires_at, s.created_at, s.views_count, s.likes_count,
                      COALESCE(pr.display_name, pr.username) AS creator_name,
                      pr.avatar_url AS creator_avatar
               FROM chain_status_posts s
               JOIN chain_profiles pr ON pr.id = s.profile_id
               WHERE (s.profile_id = %s)
                 AND s.expires_at > now()
                 AND s.deleted_at IS NULL
               ORDER BY s.created_at DESC LIMIT %s""",
            (profile_id, limit), default=[],
        )
    else:
        following.append(profile_id)
        rows = fast_query(
            """SELECT s.id, s.profile_id, s.media_url, s.media_type, s.caption,
                      s.expires_at, s.created_at, s.views_count, s.likes_count,
                      COALESCE(pr.display_name, pr.username) AS creator_name,
                      pr.avatar_url AS creator_avatar
               FROM chain_status_posts s
               JOIN chain_profiles pr ON pr.id = s.profile_id
               WHERE s.profile_id = ANY(%s)
                 AND s.expires_at > now()
                 AND s.deleted_at IS NULL
               ORDER BY s.created_at DESC LIMIT %s""",
            (following, limit), default=[],
        )

    result = []
    for row in rows:
        story = _normalize_story(row)
        story["viewed"] = _has_viewed(story["id"], profile_id)
        result.append(story)
    return result


def _normalize_story(row):
    return {
        "id": str(row["id"]),
        "profile_id": str(row["profile_id"]),
        "media_url": row.get("media_url", ""),
        "media_type": row.get("media_type", "image"),
        "caption": row.get("caption", ""),
        "expires_at": row["expires_at"].isoformat() if row.get("expires_at") else None,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "views_count": row.get("views_count", 0) or 0,
        "likes_count": row.get("likes_count", 0) or 0,
        "creator_name": row.get("creator_name", ""),
        "creator_avatar": row.get("creator_avatar", ""),
        "viewed": False,
    }


def _has_viewed(story_id, profile_id):
    try:
        rows = fast_query(
            "SELECT 1 FROM chain_story_views WHERE story_id = %s AND viewer_id = %s LIMIT 1",
            (story_id, profile_id), default=[],
        )
        return bool(rows)
    except Exception:
        return False


def _following_ids(profile_id):
    if not profile_id:
        return []
    rows = fast_query(
        "SELECT following_profile_id FROM chain_follows WHERE follower_profile_id = %s",
        (profile_id,), default=[],
    )
    return [str(r["following_profile_id"]) for r in rows]
