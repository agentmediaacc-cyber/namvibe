"""
Notification Grouping Service
Groups similar notifications into single feed items.
"""
from datetime import datetime, timezone


TYPES_THAT_NEVER_GROUP = {
    "friend_request",
    "friend_request_accepted",
    "friend_accepted",
    "wallet_transfer",
    "wallet_received",
    "security_alert",
    "system_announcement",
    "call_missed",
    "new_message",
    "message_reaction",
}

TYPES_THAT_CAN_GROUP = {
    "post_like",
    "reel_like",
    "comment_like",
    "follow",
    "story_view",
    "mention",
    "comment",
    "reply",
    "story_reaction",
    "live_started",
    "creator_subscription",
    "follow_accepted",
    "dating_match",
    "verification_approved",
}


def get_group_key(notification):
    """Returns a tuple key for grouping a notification."""
    event_type = notification.get("event_type", "")
    if event_type in TYPES_THAT_NEVER_GROUP:
        return None
    if event_type not in TYPES_THAT_CAN_GROUP:
        return None
    entity_type = notification.get("entity_type", "")
    entity_id = notification.get("entity_id", "")
    action_url = notification.get("action_url", "")
    if entity_type == "friend_request":
        return None
    created_at = notification.get("created_at", "")
    date_bucket = ""
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00")) if isinstance(created_at, str) else created_at
            date_bucket = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            date_bucket = ""
    return (event_type, entity_type, entity_id, action_url, date_bucket)


def group_notifications(items):
    """Groups a list of notification dicts into grouped items + ungrouped items."""
    groups = {}
    ungrouped = []

    for item in items:
        key = get_group_key(item)
        if key is None:
            ungrouped.append(item)
        else:
            if key not in groups:
                groups[key] = []
            groups[key].append(item)

    result = []
    for key, group_items in groups.items():
        if len(group_items) == 1:
            result.append(group_items[0])
        else:
            result.append(_build_grouped_item(group_items))

    result.extend(ungrouped)
    return result


def _build_grouped_item(group_items):
    """Builds a grouped notification item from a list of individual notifications."""
    sorted_items = sorted(group_items, key=lambda x: x.get("created_at", ""), reverse=True)
    first = sorted_items[0]
    actors = []
    seen_actors = set()
    for g in sorted_items:
        aid = g.get("actor_profile_id")
        if aid and aid not in seen_actors:
            seen_actors.add(aid)
            actors.append({
                "id": aid,
                "username": g.get("actor_username", ""),
                "avatar": g.get("actor_avatar", ""),
                "display_name": g.get("actor_display_name", ""),
            })

    is_read = all(g.get("is_read", False) for g in group_items)
    actor_names = [a.get("display_name") or a.get("username") or "Someone" for a in actors]
    actor_avatars = [a.get("avatar", "") for a in actors if a.get("avatar")]

    return {
        "id": first["id"],
        "grouped": True,
        "group_count": len(group_items),
        "actor_count": len(actors),
        "actor_names": actor_names,
        "actor_avatars": actor_avatars,
        "first_actor_avatar": actors[0].get("avatar", "") if actors else "",
        "first_actor_username": actors[0].get("username", "") if actors else "",
        "notification_ids": [g["id"] for g in group_items],
        "latest_created_at": sorted_items[0].get("created_at", ""),
        "is_read": is_read,
        "event_type": first.get("event_type", ""),
        "title": format_grouped_title(first, actor_names),
        "body": format_grouped_body(first, actor_names, len(group_items)),
        "action_url": first.get("action_url", ""),
        "icon": first.get("icon", "fa-bell"),
        "category": first.get("category", "activity"),
    }


def format_grouped_title(first, actor_names):
    """Builds a human-readable title for a grouped notification."""
    event_type = first.get("event_type", "")
    count = len(actor_names)

    preview = {
        "post_like": "liked your post",
        "reel_like": "liked your reel",
        "comment_like": "liked your comment",
        "follow": "followed you",
        "story_view": "viewed your story",
        "mention": "mentioned you",
        "comment": "commented on your post",
        "reply": "replied to your comment",
        "story_reaction": "reacted to your story",
        "live_started": "went live",
        "creator_subscription": "subscribed to you",
        "follow_accepted": "accepted your follow request",
        "dating_match": "matched with you",
        "verification_approved": "got verified",
    }
    action_text = preview.get(event_type, "interacted with your content")

    if count == 1:
        name = actor_names[0]
        return f"{name} {action_text}"
    elif count == 2:
        return f"{actor_names[0]} and {actor_names[1]} {action_text}"
    else:
        others = count - 2
        return f"{actor_names[0]}, {actor_names[1]} and {others} others {action_text}"


def format_grouped_body(first, actor_names, total_count):
    """Builds a detail body for a grouped notification."""
    event_type = first.get("event_type", "")
    body = first.get("body", "")

    if event_type in ("post_like", "reel_like", "comment_like", "follow", "story_view"):
        return f"{total_count} people" if total_count > 1 else body or ""

    if body:
        return body
    return ""
