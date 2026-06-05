from services.profile_service import (
    get_profile_bundle,
    get_profile_completion,
)
from services.supabase_safe import safe_count, safe_select, table_exists


LEVELS = [
    (1, "New Member"),
    (10, "Influencer"),
    (25, "Creator"),
    (50, "Legend"),
    (100, "Titan"),
]


def _safe_select_if_exists(table_name, **kwargs):
    if not table_exists(table_name):
        return []
    return safe_select(table_name, **kwargs) or []


def _safe_count_if_exists(table_name, filters=None):
    if not table_exists(table_name):
        return 0
    return safe_count(table_name, filters=filters or {}) or 0


def _compute_chain_score(stats, creator, marketplace, reputation, dating):
    return int(
        (stats.get("followers", 0) * 0.3)
        + (stats.get("views", 0) * 0.05)
        + (creator.get("earnings", 0) * 0.1)
        + (marketplace.get("revenue", 0) * 0.1)
        + (reputation.get("trust_score", 0) * 1.5)
        + (dating.get("compatibility_score", 0) * 0.5)
    )


def _level_from_score(score):
    level = 1
    title = "New Member"
    next_target = 10
    for target, name in LEVELS:
        if score >= target:
            level = target
            title = name
        elif score < target:
            next_target = target
            break
    progress = 100 if next_target == level else min(100, int((score / max(next_target, 1)) * 100))
    return {"current": level, "title": title, "score": score, "next_target": next_target, "progress_pct": progress}


def _achievement_cards(profile, stats, marketplace, creator):
    likes = stats.get("likes", 0)
    sales = marketplace.get("items_sold", 0)
    reels = stats.get("reels", 0)
    return [
        {"label": "Top Creator", "earned": creator.get("earnings", 0) >= 1000},
        {"label": "First Reel", "earned": reels >= 1},
        {"label": "First Sale", "earned": sales >= 1},
        {"label": "100 Likes", "earned": likes >= 100},
        {"label": "Verified User", "earned": bool(profile.get("is_verified"))},
        {"label": "Trending Creator", "earned": stats.get("views", 0) >= 500},
    ]


def _completion_payload(profile):
    missing = []
    checks = {
        "banner": bool(profile.get("cover_url")),
        "DOB": bool(profile.get("date_of_birth") or profile.get("age")),
        "skills": bool(profile.get("skills")),
        "portfolio": bool(profile.get("portfolio_url") or profile.get("portfolio_projects")),
        "website": bool(profile.get("website")),
        "bio": bool(profile.get("bio")),
    }
    for label, present in checks.items():
        if not present:
            missing.append(label)
    return {"percentage": get_profile_completion(profile), "missing_fields": missing}


def build_profile_dashboard(profile=None, viewer=None, bundle=None):
    profile = profile or {}
    bundle = bundle or (get_profile_bundle(profile_id=profile.get("id"), viewer=viewer) if profile.get("id") else None) or {}
    profile = bundle.get("profile") or profile or {}
    viewer = viewer or profile
    stats = bundle.get("stats") or {}
    content = bundle.get("content") or {"posts": [], "reels": [], "rooms": [], "stories": [], "marketplace": [], "albums": []}
    wallet = bundle.get("wallet") or {"coin_balance": 0, "gift_earnings": 0, "pending_withdrawal": 0}
    creator_tools = bundle.get("creator_tools") or {"studio_enabled": False, "featured_links": []}
    activity = bundle.get("activity") or {"gifts": [], "favorites": [], "recent_views": []}
    actions = bundle.get("actions") or []
    presence = bundle.get("presence") or {"status": "offline", "last_seen": None}

    profile_id = profile.get("id")
    settings = {
        "settings": (_safe_select_if_exists("chain_user_settings", filters={"profile_id": profile_id}, limit=1, order_by=None) or [{}])[0] if profile_id else {},
        "security": (_safe_select_if_exists("chain_account_security", filters={"profile_id": profile_id}, limit=1, order_by=None) or [{}])[0] if profile_id else {},
    }

    marketplace_items = _safe_select_if_exists("chain_marketplace_items", filters={"profile_id": profile_id}, limit=6) if profile_id else []
    items_sold = sum(int(item.get("sales_count") or 0) for item in marketplace_items)
    marketplace_revenue = sum(int(item.get("total_earned_coins") or 0) for item in marketplace_items)
    marketplace_rating = 0

    live_gifts = _safe_count_if_exists("chain_live_gifts", filters={"host_profile_id": profile_id}) if profile_id else 0
    subscriptions = _safe_count_if_exists("chain_subscriptions", filters={"creator_profile_id": profile_id}) if profile_id else 0
    live_viewers = _safe_count_if_exists("chain_live_viewers", filters={"profile_id": profile_id}) if profile_id else 0
    business_metrics = (_safe_select_if_exists("chain_business_metrics", limit=1, order_by="metric_date", desc=True) or [{}])[0]

    dating_rows = (_safe_select_if_exists("chain_dating_profiles", filters={"profile_id": profile_id}, limit=1) or [{}]) if profile_id else [{}]
    dating_row = dating_rows[0] if dating_rows else {}

    trust_score = int(profile.get("trust_score") or 0)
    reports_count = _safe_count_if_exists("chain_profile_reports", filters={"target_profile_id": profile_id}) if profile_id else 0
    reputation = {
        "trust_score": trust_score,
        "verification_state": "Verified" if profile.get("is_verified") else "Standard",
        "reports_count": reports_count,
        "transaction_reliability": 100 if marketplace_revenue == 0 else max(0, 100 - reports_count * 5),
    }

    creator = {
        "earnings": wallet.get("gift_earnings", 0) + marketplace_revenue,
        "subscribers": subscriptions,
        "views": stats.get("views", 0),
        "live_viewers": live_viewers,
        "gifts_received": live_gifts,
        "ad_revenue": int(business_metrics.get("revenue_total") or 0),
        "team": {"editors": 0, "moderators": 0, "managers": 0, "cohosts": _safe_count_if_exists("chain_live_cohost_requests", filters={"room_id": profile_id}) if profile_id and table_exists("chain_live_cohost_requests") else 0},
    }

    marketplace = {
        "items": marketplace_items,
        "items_sold": items_sold,
        "rating": marketplace_rating,
        "orders": items_sold,
        "revenue": marketplace_revenue,
        "featured_products": [item for item in marketplace_items if item.get("is_featured")][:3],
        "storefront_url": "/marketplace/",
    }

    dating = {
        "enabled": bool(profile.get("dating_mode_enabled") or dating_row.get("is_enabled")),
        "relationship_status": profile.get("relationship_status") or "Private",
        "interests": profile.get("interests") or [],
        "looking_for": profile.get("looking_for") or [],
        "compatibility_score": int(dating_row.get("compatibility_score") or 0),
        "trust_score": trust_score,
        "ai_match_suggestions": [],
    }

    portfolio = {
        "projects": _safe_select_if_exists("chain_portfolio_projects", filters={"profile_id": profile_id}, limit=6) if profile_id else [],
        "businesses": _safe_select_if_exists("chain_business_profiles", filters={"profile_id": profile_id}, limit=3) if profile_id else [],
        "websites": [profile.get("website")] if profile.get("website") else [],
        "cv": profile.get("portfolio_url"),
        "certificates": _safe_select_if_exists("chain_certificates", filters={"profile_id": profile_id}, limit=6) if profile_id else [],
        "skills": profile.get("skills") or [],
    }

    public_stats = {
        "posts": stats.get("posts", 0),
        "followers": stats.get("followers", 0),
        "reels": stats.get("reels", 0),
        "likes": stats.get("likes", 0),
        "products_sold": items_sold,
    }

    live = {
        "rooms": content.get("rooms", []),
        "go_live_url": "/live/studio",
        "invite_guest": True,
        "live_gifts": live_gifts,
        "live_polls": True,
        "live_shopping": True,
        "ai_moderation": True,
        "hd_streaming": True,
        "voice_rooms": ["Business", "Education", "Music", "Politics", "Sports"],
    }

    calls = {
        "audio_call_url": "/calls/recent",
        "group_audio": True,
        "noise_cancellation": True,
        "echo_cancellation": True,
        "video_call_url": "/calls/recent",
        "screen_share": True,
        "watch_together": True,
        "background_blur": True,
        "group_video": True,
        "voice_notes": True,
        "transcription": True,
        "translation": True,
        "summary": True,
        "ai_subtitles": True,
        "ai_notes": True,
    }

    ai = {
        "assistant_enabled": True,
        "ask_ai_url": "/profile/creator/ai-assist",
        "bio_writer": True,
        "caption_writer": True,
        "dating_compatibility": True,
        "message_assistant": True,
        "schedule_assistant": True,
    }

    completion = _completion_payload(profile)
    score = _compute_chain_score(stats, creator, marketplace, reputation, dating)
    level = _level_from_score(score)
    achievements = _achievement_cards(profile, stats, marketplace, creator)
    permissions = {
        "can_contact_email": bool(profile.get("email")) and settings["settings"].get("allow_messages", True),
        "can_call": settings["settings"].get("allow_video_calls", True),
        "can_message": settings["settings"].get("allow_messages", True),
        "can_share_location": False,
    }

    theme_choice = profile.get("profile_theme") or "Dark Premium"

    dashboard_profile = {
        **profile,
        "chain_score": profile.get("chain_score") or score,
        "rank": profile.get("rank") or level["title"],
        "profile_theme": theme_choice,
    }

    return {
        "profile": dashboard_profile,
        "viewer": viewer,
        "stats": stats,
        "wallet": wallet,
        "creator": creator,
        "marketplace": marketplace,
        "dating": dating,
        "achievements": achievements,
        "calls": calls,
        "live": live,
        "ai": ai,
        "portfolio": portfolio,
        "reputation": reputation,
        "completion": completion,
        "content": content,
        "permissions": permissions,
        "presence": presence,
        "actions": actions,
        "activity": activity,
        "public_stats": public_stats,
        "level": level,
        "story_highlights": ["Travel", "Business", "Family", "Education", "Projects"],
        "pinned": {
            "posts": content.get("posts", [])[:3],
            "reels": content.get("reels", [])[:3],
            "products": marketplace_items[:3],
        },
        "contact": {
            "call": permissions["can_call"],
            "whatsapp": bool(profile.get("phone")),
            "email": permissions["can_contact_email"],
            "message": permissions["can_message"],
        },
        "theme_options": ["Namibia Gold", "Ocean Blue", "Emerald Green", "Royal Purple", "Dark Premium"],
        "super_tabs": [
            "Social Feed", "Reels", "Stories", "Live Streams", "Audio Calls", "Video Calls",
            "Wallet", "Marketplace", "Dating", "Business Page", "Portfolio", "Courses",
            "AI Assistant", "Storefront", "Achievements", "Verification", "About",
        ],
    }
