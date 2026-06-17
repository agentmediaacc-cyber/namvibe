from flask import has_request_context, session


def _safe_int(value, default=0):
    try:
        return int(value or default)
    except Exception:
        return default


def _profile_value(profile, key, default=None):
    if not profile:
        return default
    if isinstance(profile, dict):
        return profile.get(key, default)
    return getattr(profile, key, default)


def _first_profile_value(profile, *keys, default=None):
    for key in keys:
        value = _profile_value(profile, key)
        if value not in (None, ""):
            return value
    return default


def build_public_stats(profile=None):
    posts = _safe_int(_first_profile_value(profile, "posts_count", "posts", default=0))
    reels = _safe_int(_first_profile_value(profile, "reels_count", "reels", default=0))
    followers = _safe_int(_first_profile_value(profile, "followers_count", "followers", default=0))
    following = _safe_int(_first_profile_value(profile, "following_count", "following", default=0))
    likes = _safe_int(_first_profile_value(profile, "likes_count", "total_likes", "likes", default=0))
    views = _safe_int(_first_profile_value(profile, "views_count", "profile_views", "views", default=0))
    return {
        "posts_count": posts,
        "reels_count": reels,
        "followers_count": followers,
        "following_count": following,
        "likes_count": likes,
        "views_count": views,
        "posts": posts,
        "reels": reels,
        "followers": followers,
        "following": following,
        "likes": likes,
        "views": views,
    }


def build_profile_nav(profile=None, active_tab="profile"):
    session_username = session.get("username") if has_request_context() else ""
    username = _profile_value(profile, "username") or session_username or ""
    base_profile = f"/profile/{username}" if username else "/profile/"
    items = [
        ("profile", "Profile", base_profile),
        ("posts", "Posts", f"{base_profile}?tab=posts"),
        ("reels", "Reels", f"{base_profile}?tab=reels"),
        ("stories", "Stories", f"{base_profile}?tab=stories"),
        ("settings", "Settings", "/profile/settings"),
    ]
    return [
        {"key": key, "label": label, "url": url, "href": url, "active": active_tab == key}
        for key, label, url in items
    ]


def build_profile_template_context(profile=None, active_tab="profile", extra=None):
    safe_profile = profile or {}
    stats = build_public_stats(profile)
    context = {
        "profile": safe_profile,
        "current_profile": safe_profile,
        "hero_profile": safe_profile,
        "viewer_profile": safe_profile,
        "viewer": safe_profile,
        "current": safe_profile,
        "public_stats": stats,
        "stats": stats,
        "profile_nav": build_profile_nav(profile, active_tab=active_tab),
        "active_tab": active_tab,
        "content": {"stories": [], "posts": [], "reels": [], "rooms": []},
        "wallet": {},
        "creator": {},
        "marketplace": {},
        "dating": {},
        "completion": {"percentage": 0, "missing_fields": []},
        "level": {"title": "New Member", "score": 0, "progress_pct": 0},
        "pinned": {"posts": [], "reels": [], "products": []},
        "presence": {"status": "offline", "last_seen": None},
        "is_following": False,
        "is_page_liked": False,
        "profile_fallback": False,
        "actions": [],
    }
    if extra:
        context.update(extra)
    return context
