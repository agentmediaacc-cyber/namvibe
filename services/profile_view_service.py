"""View-model helpers for the production NamVibe profile page."""

from datetime import datetime, timezone

from services.profile_completion_service import calculate_profile_completion


def _as_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _present(value):
    return value not in (None, "", [], {})


def _initials(profile):
    name = (profile or {}).get("display_name") or (profile or {}).get("full_name") or (profile or {}).get("username") or "NamVibe"
    parts = [part for part in str(name).replace("@", " ").split() if part]
    if not parts:
        return "NV"
    return "".join(part[0].upper() for part in parts[:2])


def _location(profile):
    profile = profile or {}
    parts = []
    for key in ("town", "city", "region", "country", "current_country", "country_origin"):
        value = profile.get(key)
        if value and str(value).strip() and str(value).strip() not in parts:
            parts.append(str(value).strip())
    return ", ".join(parts) or profile.get("current_location") or profile.get("location") or ""


def _relative_active(profile, presence):
    if presence and presence.get("status") in {"online", "active"}:
        return {"label": "Active now", "online": True}
    raw = (presence or {}).get("last_seen") or (profile or {}).get("last_active") or (profile or {}).get("last_login_at") or (profile or {}).get("updated_at")
    if not raw:
        return {"label": "Active recently", "online": False}
    try:
        if isinstance(raw, str):
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            dt = raw
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        minutes = max(0, int(delta.total_seconds() // 60))
        if minutes < 5:
            return {"label": "Active recently", "online": False}
        if minutes < 60:
            return {"label": f"Active {minutes}m ago", "online": False}
        hours = minutes // 60
        if hours < 24:
            return {"label": f"Active {hours}h ago", "online": False}
    except Exception:
        pass
    return {"label": "Active recently", "online": False}


def _joined(profile):
    raw = (profile or {}).get("created_at")
    if not raw:
        return "Recently joined"
    try:
        if isinstance(raw, str):
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            dt = raw
        return dt.strftime("%b %Y")
    except Exception:
        return "Recently joined"


def _verification(profile, wallet, creator):
    profile = profile or {}
    wallet = wallet or {}
    creator = creator or {}
    creator_state = creator.get("verification_status") or profile.get("creator_verification_status") or ("verified" if profile.get("creator_verified") else "not_started")
    return [
        {"key": "email", "label": "Email Verified", "state": "verified" if profile.get("email_verified") or profile.get("email_confirmed") else "missing"},
        {"key": "phone", "label": "Phone Verified", "state": "verified" if profile.get("phone_verified") or profile.get("phone_confirmed") else "missing"},
        {"key": "identity", "label": "Identity Verified", "state": "verified" if profile.get("identity_verified") or profile.get("is_verified") or profile.get("verified") else "missing"},
        {"key": "creator", "label": "Creator Verification", "state": creator_state if creator_state in {"verified", "pending", "rejected"} else "missing"},
        {"key": "withdrawal", "label": "Withdrawal Ready", "state": "verified" if wallet.get("withdrawal_ready") or wallet.get("payouts_enabled") else "missing"},
    ]


def _tabs(own_profile, is_creator, has_shop):
    tabs = [
        {"key": "posts", "label": "Posts", "icon": "fa-table-cells-large"},
        {"key": "reels", "label": "Reels", "icon": "fa-film"},
        {"key": "media", "label": "Media", "icon": "fa-photo-film"},
        {"key": "gallery", "label": "Gallery", "icon": "fa-photo-film"},
        {"key": "live", "label": "Live", "icon": "fa-tower-broadcast"},
        {"key": "about", "label": "About", "icon": "fa-circle-info"},
    ]
    if own_profile:
        tabs.extend([
            {"key": "saved", "label": "Saved", "icon": "fa-bookmark"},
            {"key": "liked", "label": "Liked", "icon": "fa-heart"},
        ])
    if own_profile or is_creator:
        tabs.append({"key": "dashboard", "label": "Dashboard", "icon": "fa-gauge-high"})
    if has_shop:
        tabs.append({"key": "shop", "label": "Shop", "icon": "fa-bag-shopping"})
    return tabs


def build_profile_view_model(profile, viewer=None, stats=None, content=None, wallet=None, creator=None, marketplace=None, presence=None, action_policy=None):
    profile = profile or {}
    viewer = viewer or {}
    stats = stats or {}
    content = content or {}
    wallet = wallet or {}
    creator = creator or {}
    marketplace = marketplace or {}
    action_policy = action_policy or {}

    own_profile = bool(viewer and profile and viewer.get("id") == profile.get("id"))
    products = marketplace.get("items") or marketplace.get("featured_products") or content.get("marketplace") or []
    has_shop = bool(products or marketplace.get("shop_enabled") or profile.get("shop_enabled") or profile.get("has_shop"))
    is_creator = bool(profile.get("is_creator") or creator.get("studio_enabled") or creator.get("monetization_enabled") or profile.get("profile_type") == "creator")
    posts_count = _as_int(stats.get("posts") or stats.get("posts_count") or profile.get("posts_count"))
    reels_count = _as_int(stats.get("reels") or stats.get("reels_count") or profile.get("reels_count"))
    views_count = _as_int(stats.get("views") or stats.get("views_count") or profile.get("profile_views"))
    stat_items = [
        {"key": "posts", "label": "Posts", "value": posts_count},
        {"key": "reels", "label": "Reels", "value": reels_count},
        {"key": "followers", "label": "Followers", "value": _as_int(stats.get("followers") or profile.get("followers_count"))},
        {"key": "following", "label": "Following", "value": _as_int(stats.get("following") or profile.get("following_count"))},
        {"key": "friends", "label": "Friends", "value": _as_int(stats.get("friends") or profile.get("friends_count"))},
        {"key": "likes", "label": "Likes", "value": _as_int(stats.get("likes") or profile.get("total_likes"))},
        {"key": "views", "label": "Views", "value": views_count},
        {"key": "profile_views", "label": "Profile Views", "value": views_count},
    ]
    highlights = content.get("highlights") or profile.get("highlights") or []
    if own_profile and not highlights:
        highlights = [
            {"label": "Add Highlight", "icon": "fa-plus", "url": "/status/create", "empty": True},
            {"label": "Music", "icon": "fa-music", "url": "/music/", "empty": True},
            {"label": "Events", "icon": "fa-calendar", "url": "/events/", "empty": True},
            {"label": "Live", "icon": "fa-tower-broadcast", "url": "/live/studio", "empty": True},
        ]

    completion_profile = {**profile, "posts_count": posts_count, "reels_count": reels_count, "stories_count": _as_int(stats.get("stories") or len(content.get("stories") or []))}
    return {
        "own_profile": own_profile,
        "display_name": profile.get("display_name") or profile.get("full_name") or profile.get("username") or "NamVibe Member",
        "username": profile.get("username") or "member",
        "initials": _initials(profile),
        "location": _location(profile),
        "joined": _joined(profile),
        "active": _relative_active(profile, presence),
        "avatar_url": profile.get("avatar_url") or profile.get("photo_url") or profile.get("thumbnail_url"),
        "cover_url": profile.get("cover_url") or profile.get("banner_url"),
        "member_badge": "Creator" if is_creator else ("Verified" if profile.get("is_verified") or profile.get("verified") else "Member"),
        "privacy": profile.get("profile_visibility") or profile.get("visibility") or "public",
        "completion": calculate_profile_completion(completion_profile),
        "tabs": _tabs(own_profile, is_creator, has_shop),
        "has_shop": has_shop,
        "products": products,
        "stats": stat_items,
        "all_stats_zero": not any(item["value"] for item in stat_items),
        "verification": _verification(profile, wallet, creator),
        "highlights": highlights,
        "show_owner_dashboard": own_profile,
        "show_dashboard_tab": own_profile or is_creator,
        "withdrawal_ready": bool(wallet.get("withdrawal_ready") or wallet.get("payouts_enabled")),
        "withdrawal_reason": wallet.get("withdrawal_block_reason") or "Verify your identity and payout details first.",
        "can_message": bool(action_policy.get("can_chat") or action_policy.get("can_message")),
        "can_call": bool(action_policy.get("can_call")),
        "can_video_call": bool(action_policy.get("can_video_call") or action_policy.get("can_call")),
    }
