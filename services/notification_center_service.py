from datetime import datetime, timezone
from services.neon_service import fast_query
from services.notification_engine import (
    create_notification as engine_create,
    list_notifications as engine_list,
    list_notifications_tab,
    unread_count as engine_unread_count,
    mark_read as engine_mark_read,
    mark_all_read as engine_mark_all_read,
    delete_notification as engine_delete,
    delete_selected_notifications,
    mute_notification_type,
    get_notification_preferences,
    update_notification_preferences,
    _NOTIF_TYPE_CATEGORIES,
    _NOTIF_ICONS,
)

_NOTIFICATION_TYPE_CATEGORIES = _NOTIF_TYPE_CATEGORIES
_NOTIFICATION_ICONS = _NOTIF_ICONS


def _category_for(event_type):
    return _NOTIFICATION_TYPE_CATEGORIES.get(event_type or "", "activity")


def _icon_for(event_type):
    return _NOTIFICATION_ICONS.get(event_type or "", "fa-bell")


def _sender_name(row):
    return (
        row.get("actor_display_name")
        or row.get("actor_username")
        or row.get("display_name")
        or row.get("username")
        or "Someone"
    )


def _sender_avatar(row):
    return (
        row.get("actor_avatar")
        or row.get("avatar_url")
        or row.get("image_url")
        or ""
    )


def _sender_initials(name):
    text = (name or "S").strip()
    if not text:
        return "S"
    parts = [p[:1].upper() for p in text.split() if p]
    return "".join(parts[:2]) or text[:1].upper()


def _entity_preview(row):
    entity_type = row.get("entity_type")
    entity_id = row.get("entity_id")
    actor_profile_id = row.get("actor_profile_id")
    if not entity_type or not entity_id:
        return row.get("body") or ""
    try:
        if row.get("event_type") == "comment" and entity_type == "post" and actor_profile_id:
            comment = fast_query(
                """
                SELECT body FROM chain_post_comments
                WHERE post_id = %s AND profile_id = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (entity_id, actor_profile_id),
                default=[],
            )
            if comment:
                return (comment[0].get("body") or "").strip()
        if row.get("event_type") == "comment" and entity_type == "reel" and actor_profile_id:
            comment = fast_query(
                """
                SELECT body FROM chain_reel_comments
                WHERE reel_id = %s AND profile_id = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (entity_id, actor_profile_id),
                default=[],
            )
            if comment:
                return (comment[0].get("body") or "").strip()
        if entity_type == "post":
            post = fast_query(
                "SELECT caption, body FROM chain_posts WHERE id = %s LIMIT 1",
                (entity_id,),
                default=[],
            )
            if post:
                return (post[0].get("caption") or post[0].get("body") or "").strip()
        if entity_type == "reel":
            reel = fast_query(
                "SELECT caption FROM chain_reels WHERE id = %s LIMIT 1",
                (entity_id,),
                default=[],
            )
            if reel:
                return (reel[0].get("caption") or "").strip()
    except Exception:
        return row.get("body") or ""
    return row.get("body") or ""


def _open_url(row):
    event_type = row.get("event_type")
    entity_type = row.get("entity_type")
    entity_id = row.get("entity_id")
    actor_username = row.get("actor_username")
    if event_type == "post_like" and entity_id:
        return f"/post/{entity_id}"
    if event_type == "comment" and entity_type == "post" and entity_id:
        return f"/post/{entity_id}#comments"
    if event_type == "reel_like" and entity_id:
        return f"/reels/{entity_id}"
    if event_type == "comment" and entity_type == "reel" and entity_id:
        return f"/reels/{entity_id}#comments"
    if event_type in {"follow", "new_follower", "follow_accepted"} and actor_username:
        return f"/profile/@{actor_username}"
    if event_type in {"new_message", "message_reaction"}:
        action_url = row.get("action_url") or ""
        return action_url
    if entity_type == "story" and entity_id:
        return f"/status/{entity_id}"
    return row.get("action_url") or ""


def _action_text(row):
    mapping = {
        "post_like": "liked your post",
        "comment": "commented on your post" if row.get("entity_type") == "post" else "commented on your reel",
        "reel_like": "liked your reel",
        "new_follower": "followed you",
        "follow": "followed you",
        "follow_accepted": "accepted your follow request",
        "new_message": "sent you a message",
        "message_reaction": "reacted to your message",
        "story_liked": "liked your story",
        "story_reaction": "reacted to your story",
    }
    return mapping.get(row.get("event_type"), row.get("title") or "sent a notification")


def format_notification(row):
    if not row:
        return None
    d = dict(row)
    event_type = d.get("event_type") or d.get("notification_type") or ""
    sender_name = _sender_name(d)
    preview_text = _entity_preview(d)
    d["category"] = _category_for(event_type)
    d["icon"] = _icon_for(event_type)
    d["sender_display_name"] = sender_name
    d["sender_avatar_url"] = _sender_avatar(d)
    d["sender_initials"] = _sender_initials(sender_name)
    d["action_text"] = _action_text(d)
    d["preview_text"] = preview_text or (d.get("body") or "")
    d["open_url"] = _open_url(d)
    d["open_label"] = "Open"
    d["is_unread"] = not bool(d.get("is_read"))
    if isinstance(d.get("created_at"), datetime):
        d["created_at"] = d["created_at"].isoformat()
    if isinstance(d.get("read_at"), datetime):
        d["read_at"] = d["read_at"].isoformat()
    if isinstance(d.get("deleted_at"), datetime):
        d["deleted_at"] = d["deleted_at"].isoformat()
    return d


def create_notification(
    recipient_profile_id,
    notification_type,
    title,
    body=None,
    actor_profile_id=None,
    target_type=None,
    target_id=None,
    action_url=None,
    image_url=None,
    metadata=None,
):
    from services.notification_engine import create_notification as _engine_create
    return _engine_create(
        recipient_profile_id=recipient_profile_id,
        event_type=notification_type,
        title=title,
        body=body,
        actor_profile_id=actor_profile_id,
        entity_type=target_type,
        entity_id=target_id,
        action_url=action_url,
    )


def list_notifications(profile_id, tab="all", page=1, limit=30):
    if page < 1:
        page = 1
    if limit < 1:
        limit = 10
    limit = min(limit, 50)
    try:
        if tab == "social":
            tab = "activity"
        items, has_more = list_notifications_tab(profile_id, tab=tab, page=page, limit=limit)
        return [format_notification(item) for item in items], has_more
    except Exception:
        return [], False


def unread_count(profile_id):
    try:
        return engine_unread_count(profile_id)
    except Exception:
        return 0


def mark_read(profile_id, notification_id):
    try:
        return engine_mark_read(notification_id, profile_id)
    except Exception:
        return False


def mark_all_read(profile_id):
    try:
        return engine_mark_all_read(profile_id)
    except Exception:
        return False


def delete_notification(profile_id, notification_id):
    try:
        return engine_delete(notification_id, profile_id)
    except Exception:
        return False


def delete_selected(profile_id, notification_ids):
    if not notification_ids:
        return False
    try:
        return delete_selected_notifications(notification_ids, profile_id)
    except Exception:
        return False


def get_preferences(profile_id):
    try:
        return get_notification_preferences(profile_id)
    except Exception:
        return {"profile_id": profile_id, "muted_types": []}


def update_preferences(profile_id, prefs_data):
    try:
        return update_notification_preferences(profile_id, prefs_data)
    except Exception:
        return False


def mute_type(profile_id, notification_type, muted=True):
    try:
        return mute_notification_type(profile_id, notification_type, muted=muted)
    except Exception:
        return False
