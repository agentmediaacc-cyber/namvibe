from datetime import datetime, timezone
from services.supabase_safe import safe_select
from services.trending_service import get_trending_items
from services.relationship_privacy_service import can_view_posts, can_view_reels, can_view_stories, is_blocked_any


def _profile_for_owner(owner_id):
    rows = safe_select("chain_profiles", columns="*", filters={"id": owner_id}, limit=1)
    return rows[0] if rows else None


def get_personalized_feed(profile_id, limit=30):
    feed = []
    seen_ids = set()

    following = safe_select("chain_follows", filters={"follower_profile_id": profile_id})
    following_ids = [f['following_profile_id'] for f in following]

    if following_ids:
        live_rooms = safe_select("chain_live_rooms", filters={"is_live": True, "host_profile_id": ("in", following_ids)}, limit=5)
        for room in live_rooms:
            if room['id'] not in seen_ids:
                feed.append({"type": "live_room", "data": room, "priority": 100})
                seen_ids.add(room['id'])
        posts = safe_select("chain_posts", filters={"profile_id": ("in", following_ids)}, limit=10, order_by="created_at", desc=True)
        for post in posts:
            if post['id'] not in seen_ids:
                owner = _profile_for_owner(post.get("profile_id"))
                if owner and can_view_posts(profile_id, owner):
                    feed.append({"type": "post", "data": post, "priority": 90})
                    seen_ids.add(post['id'])

    trending_rooms = get_trending_items('live_room', limit=5)
    if trending_rooms:
        room_ids = [t['entity_id'] for t in trending_rooms]
        rooms = safe_select("chain_live_rooms", filters={"id": ("in", room_ids)})
        for room in rooms:
            if room['id'] not in seen_ids and not is_blocked_any(profile_id, room.get("host_profile_id")):
                feed.append({"type": "live_room", "data": room, "priority": 80})
                seen_ids.add(room['id'])

    marketplace = safe_select("chain_marketplace_items", filters={"approval_status": "approved"}, limit=5, order_by="created_at", desc=True)
    for item in marketplace:
        if item['id'] not in seen_ids:
            feed.append({"type": "marketplace_item", "data": item, "priority": 70})
            seen_ids.add(item['id'])

    remaining = limit - len(feed)
    if remaining > 0:
        general_posts = safe_select("chain_posts", limit=remaining, order_by="created_at", desc=True)
        for post in general_posts:
            if post['id'] not in seen_ids:
                owner = _profile_for_owner(post.get("profile_id"))
                if owner and can_view_posts(profile_id, owner):
                    feed.append({"type": "post", "data": post, "priority": 50})
                    seen_ids.add(post['id'])

    feed.sort(key=lambda x: x['priority'], reverse=True)
    return feed[:limit]
