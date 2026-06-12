from services.live_service import get_room
from services.profile_service import get_current_profile, get_profile_by_username, normalize_profile
from services.supabase_safe import safe_select
from utils.supabase_client import get_supabase_admin


def _select_rows_for_profile(table, profile_id, limit=40):
    admin = get_supabase_admin()
    candidate_keys = [
        "profile_id",
        "owner_profile_id",
        "user_profile_id",
        "actor_profile_id",
        "viewer_profile_id",
        "user_id",
    ]

    for key in candidate_keys:
        try:
            rows = (
                admin.table(table)
                .select("*")
                .eq(key, profile_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data
                or []
            )
            return rows
        except Exception:
            continue

    return []


def _pick_target(row, keys):
    for key in keys:
        value = row.get(key)
        if value:
            return value
    return None


def _resolve_profile_item(row):
    target_profile_id = _pick_target(
        row,
        ["target_profile_id", "favorited_profile_id", "viewed_profile_id", "target_member_id", "member_id"],
    )
    if not target_profile_id:
        username = row.get("target_username") or row.get("username")
        if username:
            profile = get_profile_by_username(username)
        else:
            profile = None
    else:
        profiles = safe_select("chain_profiles", filters={"id": target_profile_id}, limit=1, order_by=None)
        profile = normalize_profile(profiles[0]) if profiles else None

    if not profile:
        return None

    return {
        "kind": "profile",
        "title": profile.get("full_name") or profile.get("username") or "Saved member",
        "subtitle": f"@{profile.get('username')} • {profile.get('current_location') or 'Location not set'}",
        "href": f"/profile/@{profile.get('username')}",
        "image_url": profile.get("avatar_url"),
        "created_at": row.get("created_at"),
    }


def _resolve_post_item(row):
    target_post_id = _pick_target(row, ["target_post_id", "post_id", "viewed_post_id"])
    if not target_post_id:
        return None

    posts = safe_select("chain_posts", filters={"id": target_post_id}, limit=1, order_by=None)
    if not posts:
        return None

    post = posts[0]
    body = (post.get("body") or post.get("caption") or "Saved post").strip()
    return {
        "kind": "post",
        "title": body[:110] + ("..." if len(body) > 110 else ""),
        "subtitle": "Post from NamVibe feed",
        "href": "/discover/trending",
        "image_url": post.get("media_url"),
        "created_at": row.get("created_at") or post.get("created_at"),
    }


def _resolve_room_item(row):
    target_room_id = _pick_target(row, ["target_room_id", "live_room_id", "room_id", "viewed_room_id"])
    if not target_room_id:
        return None

    room = get_room(target_room_id)
    if not room:
        return None

    return {
        "kind": "live",
        "title": room.get("title") or "Live room",
        "subtitle": f"{room.get('host_name') or 'Host'} • {room.get('access_type', 'public').title()}",
        "href": f"/live/room/{room.get('id')}",
        "image_url": None,
        "created_at": row.get("created_at") or room.get("created_at"),
    }


def _fallback_item(row, label):
    title = row.get("title") or row.get("label") or row.get("name") or label
    subtitle = row.get("description") or row.get("favorite_type") or row.get("view_type") or "Saved from your NamVibe activity."
    href = row.get("target_url") or row.get("href") or "/discover"
    return {
        "kind": "generic",
        "title": title,
        "subtitle": subtitle,
        "href": href,
        "image_url": row.get("image_url") or row.get("avatar_url") or row.get("media_url"),
        "created_at": row.get("created_at"),
    }


def _normalize_items(rows, label):
    items = []
    for row in rows:
        item = (
            _resolve_profile_item(row)
            or _resolve_room_item(row)
            or _resolve_post_item(row)
            or _fallback_item(row, label)
        )
        items.append(item)
    return items


def get_favorites(limit=40):
    current = get_current_profile()
    if not current:
        return [], None

    rows = _select_rows_for_profile("chain_favorites", current["id"], limit=limit)
    return _normalize_items(rows, "Favorite"), current


def get_history(limit=40):
    current = get_current_profile()
    if not current:
        return [], None

    rows = _select_rows_for_profile("chain_recent_views", current["id"], limit=limit)
    return _normalize_items(rows, "Recent view"), current
