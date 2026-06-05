from datetime import datetime, timezone
from html import escape

from services.supabase_safe import safe_count, safe_delete, safe_insert, safe_select, safe_update, table_exists


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _clean_body(value, max_len=1000):
    text = " ".join((value or "").strip().split())
    if not text:
        return ""
    return escape(text[:max_len], quote=False)


def _first(table, filters, columns="*", order_by=None):
    rows = safe_select(table, columns=columns, filters=filters, limit=1, order_by=order_by)
    return rows[0] if rows else None


def _owner_for(entity_type, entity_id):
    table_map = {
        "post": ("chain_posts", ["profile_id"]),
        "reel": ("chain_reels", ["profile_id"]),
        "story": ("chain_status_posts", ["profile_id"]),
        "live_room": ("chain_live_rooms", ["profile_id", "host_profile_id"]),
    }
    table_info = table_map.get(entity_type)
    if not table_info:
        return None
    table, owner_columns = table_info
    row = _first(table, {"id": entity_id}, columns="*", order_by=None) or {}
    for column in owner_columns:
        if row.get(column):
            return row.get(column)
    return None


def _notify(recipient_id, actor_id, event_type, title, body, target_url, entity_type=None, entity_id=None):
    if not recipient_id or recipient_id == actor_id:
        return False
    created = False
    try:
        from services.notification_engine import create_notification as create_engine_notification

        created = bool(
            create_engine_notification(
                recipient_profile_id=recipient_id,
                actor_profile_id=actor_id,
                event_type=event_type,
                title=title,
                body=body,
                entity_type=entity_type,
                entity_id=entity_id,
                action_url=target_url,
            )
        )
    except Exception:
        created = False
    if created:
        return True
    try:
        from services.notification_service import create_notification

        return create_notification(
            profile_id=recipient_id,
            actor_profile_id=actor_id,
            title=title,
            body=body,
            n_type=event_type,
            link_url=target_url,
        )
    except Exception:
        return False


def _set_count(table, entity_id, column, count):
    safe_update(table, {column: count}, eq={"id": entity_id})


def _reaction_config(entity_type):
    return {
        "post": {
            "table": "chain_post_reactions",
            "entity_column": "post_id",
            "target_table": "chain_posts",
            "count_column": "likes_count",
            "target_url": f"/#post-{{id}}",
            "event_type": "post_liked",
            "title": "Post liked",
            "body": "liked your post.",
        },
        "reel": {
            "table": "chain_reel_reactions",
            "entity_column": "reel_id",
            "target_table": "chain_reels",
            "count_column": "likes_count",
            "target_url": "/reels/",
            "event_type": "reel_liked",
            "title": "Reel liked",
            "body": "liked your reel.",
        },
        "story": {
            "table": "chain_story_reactions",
            "entity_column": "story_id",
            "target_table": "chain_status_posts",
            "count_column": "likes_count",
            "target_url": f"/status/{{id}}",
            "event_type": "story_liked",
            "title": "Story liked",
            "body": "liked your story.",
        },
        "live_room": {
            "table": "chain_live_reactions",
            "entity_column": "room_id",
            "target_table": "chain_live_rooms",
            "count_column": "likes_count",
            "target_url": f"/live/room/{{id}}",
            "event_type": "live_liked",
            "title": "Live room liked",
            "body": "liked your live room.",
        },
    }.get(entity_type)


def toggle_like(profile_id, entity_type, entity_id):
    config = _reaction_config(entity_type)
    if not profile_id or not entity_id or not config:
        return {"success": False, "error": "Invalid like target."}
    if not table_exists(config["table"]):
        return {"success": False, "error": f"{config['table']} is not available."}

    filters = {
        "profile_id": profile_id,
        config["entity_column"]: entity_id,
        "reaction_type": "like",
    }
    existing = _first(config["table"], filters, columns="id", order_by=None)
    liked = not bool(existing)
    if existing:
        safe_delete(config["table"], eq={"id": existing["id"]})
    else:
        inserted = safe_insert(
            config["table"],
            {
                **filters,
                "created_at": _utcnow_iso(),
            },
        )
        if inserted is None:
            return {"success": False, "error": "Could not save like."}

    count = safe_count(config["table"], filters={config["entity_column"]: entity_id, "reaction_type": "like"})
    _set_count(config["target_table"], entity_id, config["count_column"], count)

    if liked:
        target_url = config["target_url"].format(id=entity_id)
        _notify(
            _owner_for(entity_type, entity_id),
            profile_id,
            config["event_type"],
            config["title"],
            config["body"],
            target_url,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    return {"success": True, "liked": liked, "count": count}


def is_liked(profile_id, entity_type, entity_id):
    config = _reaction_config(entity_type)
    if not profile_id or not entity_id or not config:
        return False
    return bool(
        _first(
            config["table"],
            {"profile_id": profile_id, config["entity_column"]: entity_id, "reaction_type": "like"},
            columns="id",
            order_by=None,
        )
    )


def _comment_config(entity_type):
    return {
        "post": {
            "table": "chain_post_comments",
            "entity_column": "post_id",
            "target_table": "chain_posts",
            "count_column": "comments_count",
            "target_url": f"/#post-{{id}}",
            "event_type": "post_commented",
            "title": "New comment",
            "body": "commented on your post.",
        },
        "reel": {
            "table": "chain_reel_comments",
            "entity_column": "reel_id",
            "target_table": "chain_reels",
            "count_column": "comments_count",
            "target_url": "/reels/",
            "event_type": "reel_commented",
            "title": "New reel comment",
            "body": "commented on your reel.",
        },
        "live_room": {
            "table": "chain_live_comments",
            "entity_column": "room_id",
            "target_table": "chain_live_rooms",
            "count_column": "comments_count",
            "target_url": f"/live/room/{{id}}",
            "event_type": "live_commented",
            "title": "New live comment",
            "body": "commented in your live room.",
        },
    }.get(entity_type)


def add_comment(profile_id, entity_type, entity_id, body):
    config = _comment_config(entity_type)
    clean = _clean_body(body)
    if not profile_id or not entity_id or not config:
        return {"success": False, "error": "Invalid comment target."}
    if not clean:
        return {"success": False, "error": "Comment cannot be empty."}
    if not table_exists(config["table"]):
        return {"success": False, "error": f"{config['table']} is not available."}

    inserted = safe_insert(
        config["table"],
        {
            "profile_id": profile_id,
            config["entity_column"]: entity_id,
            "body": clean,
            "created_at": _utcnow_iso(),
        },
    )
    if not inserted:
        return {"success": False, "error": "Could not save comment."}

    count = safe_count(config["table"], filters={config["entity_column"]: entity_id})
    _set_count(config["target_table"], entity_id, config["count_column"], count)
    _notify(
        _owner_for(entity_type, entity_id),
        profile_id,
        config["event_type"],
        config["title"],
        config["body"],
        config["target_url"].format(id=entity_id),
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return {"success": True, "comment": inserted[0], "count": count}


def list_comments(entity_type, entity_id, limit=5):
    config = _comment_config(entity_type)
    if not config or not entity_id:
        return []
    comments = safe_select(
        config["table"],
        filters={config["entity_column"]: entity_id},
        limit=limit,
        order_by="created_at",
        desc=True,
    )
    return list(reversed(comments))


def delete_comment(profile_id, entity_type, comment_id):
    config = _comment_config(entity_type)
    if not profile_id or not comment_id or not config:
        return {"success": False, "error": "Invalid comment."}
    existing = _first(config["table"], {"id": comment_id}, columns="id,profile_id," + config["entity_column"], order_by=None)
    if not existing:
        return {"success": False, "error": "Comment not found."}
    if existing.get("profile_id") != profile_id:
        return {"success": False, "error": "You can only delete your own comment."}
    safe_delete(config["table"], eq={"id": comment_id, "profile_id": profile_id})
    entity_id = existing.get(config["entity_column"])
    count = safe_count(config["table"], filters={config["entity_column"]: entity_id})
    _set_count(config["target_table"], entity_id, config["count_column"], count)
    return {"success": True, "count": count}


def follow_profile(follower_id, following_id):
    if not follower_id or not following_id:
        return {"success": False, "error": "Invalid profile."}
    if follower_id == following_id:
        return {"success": False, "error": "You cannot follow yourself."}
    if not table_exists("chain_follows"):
        return {"success": False, "error": "Follow table is not available."}

    existing = _first(
        "chain_follows",
        {"follower_profile_id": follower_id, "following_profile_id": following_id},
        columns="id",
        order_by=None,
    )
    if existing:
        safe_delete("chain_follows", eq={"id": existing["id"]})
        following = False
    else:
        inserted = safe_insert(
            "chain_follows",
            {
                "follower_profile_id": follower_id,
                "following_profile_id": following_id,
                "created_at": _utcnow_iso(),
            },
        )
        if inserted is None:
            return {"success": False, "error": "Could not update follow state."}
        following = True
        _notify(
            following_id,
            follower_id,
            "new_follower",
            "New follower",
            "started following you.",
            f"/profile/{follower_id}",
            entity_type="profile",
            entity_id=following_id,
        )

    followers = safe_count("chain_follows", filters={"following_profile_id": following_id})
    following_count = safe_count("chain_follows", filters={"follower_profile_id": follower_id})
    safe_update("chain_profiles", {"followers_count": followers}, eq={"id": following_id})
    safe_update("chain_profiles", {"following_count": following_count}, eq={"id": follower_id})
    return {"success": True, "following": following, "followers_count": followers, "following_count": following_count}


def unfollow_profile(follower_id, following_id):
    if not follower_id or not following_id:
        return {"success": False, "error": "Invalid profile."}
    safe_delete("chain_follows", eq={"follower_profile_id": follower_id, "following_profile_id": following_id})
    followers = safe_count("chain_follows", filters={"following_profile_id": following_id})
    following_count = safe_count("chain_follows", filters={"follower_profile_id": follower_id})
    safe_update("chain_profiles", {"followers_count": followers}, eq={"id": following_id})
    safe_update("chain_profiles", {"following_count": following_count}, eq={"id": follower_id})
    return {"success": True, "following": False, "followers_count": followers, "following_count": following_count}


def is_following(follower_id, following_id):
    return bool(
        follower_id
        and following_id
        and _first(
            "chain_follows",
            {"follower_profile_id": follower_id, "following_profile_id": following_id},
            columns="id",
            order_by=None,
        )
    )


def toggle_save(profile_id, item_type, item_id):
    if item_type not in {"post", "reel"} or not profile_id or not item_id:
        return {"success": False, "error": "Invalid saved item."}
    if not table_exists("chain_saved_items"):
        return {"success": False, "error": "Saved items table is not available."}
    filters = {"profile_id": profile_id, "item_type": item_type, "item_id": item_id}
    existing = _first("chain_saved_items", filters, columns="id", order_by=None)
    saved = not bool(existing)
    if existing:
        safe_delete("chain_saved_items", eq={"id": existing["id"]})
    else:
        inserted = safe_insert("chain_saved_items", {**filters, "created_at": _utcnow_iso()})
        if inserted is None:
            return {"success": False, "error": "Could not save item."}
    count = safe_count("chain_saved_items", filters={"item_type": item_type, "item_id": item_id})
    return {"success": True, "saved": saved, "count": count}


def get_saved_items(profile_id, limit=20):
    if not profile_id:
        return []
    return safe_select("chain_saved_items", filters={"profile_id": profile_id}, limit=limit)


def save_item(profile_id, item_type, item_id):
    return toggle_save(profile_id, item_type, item_id)


def react_to_post(profile_id, post_id, reaction_type="like"):
    if reaction_type != "like":
        reaction_type = "like"
    return toggle_like(profile_id, "post", post_id)


def react_to_live(room_id, profile_id, reaction_type="like"):
    if reaction_type != "like":
        reaction_type = "like"
    return toggle_like(profile_id, "live_room", room_id)


def comment_on_post(profile_id, post_id, body):
    result = add_comment(profile_id, "post", post_id, body)
    return result.get("comment") if result.get("success") else None


def comment_on_live(room_id, profile_id, body):
    return add_comment(profile_id, "live_room", room_id, body)
