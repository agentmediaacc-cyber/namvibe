"""View-model helpers for the production NamVibe profile page."""

from datetime import datetime, timezone

from services.profile_completion_service import calculate_profile_completion
from services.avatar_service import avatar_meta
from services.subscription_entitlement_service import get_entitlement


def _as_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _compute_years(created_at):
    if not created_at:
        return 0
    try:
        if isinstance(created_at, str):
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            dt = created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(1, (datetime.now(timezone.utc) - dt).days // 365)
    except Exception:
        return 0


def _member_year(created_at):
    if not created_at:
        return ""
    try:
        if isinstance(created_at, str):
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            dt = created_at
        return str(dt.year)
    except Exception:
        return ""


def _format_list(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return ", ".join(str(x) for x in value if x)
    return str(value)


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
    avatar = avatar_meta(profile)
    entitlement = get_entitlement(profile.get("id"), profile=profile) if profile.get("id") else {"effective_plan": "free", "subscription_status": "free", "is_premium": False}
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
    gallery_preview = content.get("gallery_preview") or content.get("albums_preview") or []
    mutual_friends = content.get("mutual_friends") or {}
    profile_strength_raw = content.get("profile_strength") or {}
    profile_strength = _as_int(profile_strength_raw.get("score") or profile_strength_raw.get("percent") or 0) if isinstance(profile_strength_raw, dict) else _as_int(profile_strength_raw or 0)
    recently_active_friends = content.get("recently_active_friends") or []
    if own_profile and not highlights:
        highlights = [
            {"label": "Add Highlight", "icon": "fa-plus", "url": "/status/create", "empty": True},
            {"label": "Music", "icon": "fa-music", "url": "/music/", "empty": True},
            {"label": "Events", "icon": "fa-calendar", "url": "/events/", "empty": True},
            {"label": "Live", "icon": "fa-tower-broadcast", "url": "/live/studio", "empty": True},
        ]

    completion_profile = {**profile, "posts_count": posts_count, "reels_count": reels_count, "stories_count": _as_int(stats.get("stories") or len(content.get("stories") or []))}
    active = _relative_active(profile, presence)
    return {
        "own_profile": own_profile,
        "display_name": profile.get("display_name") or profile.get("full_name") or profile.get("username") or "NamVibe Member",
        "username": profile.get("username") or "member",
        "initials": _initials(profile),
        "location": _location(profile),
        "joined": _joined(profile),
        "active": active,
        **avatar,
        "avatar_url": avatar["avatar_url"],
        "cover_url": profile.get("cover_url") or profile.get("banner_url"),
        "gallery_preview": gallery_preview,
        "mutual_friends_count": int(mutual_friends.get("count") or 0),
        "mutual_friends_items": mutual_friends.get("items") or [],
        "profile_strength": profile_strength,
        "recently_active_friends": recently_active_friends,
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
        "friendship_status_label": {
            "friend": "Friends",
            "pending_sent": "Request sent",
            "pending_received": "Accept request",
            "follower": "Following",
            "blocked": "Blocked",
        }.get(action_policy.get("relationship"), "Discover"),

        # Flat convenience keys for template compatibility
        "id": profile.get("id"),
        "is_self": own_profile,
        "is_online": bool(active.get("online")),
        "state_label": active.get("label", ""),
        "verified": bool(profile.get("verified") or profile.get("is_verified")),
        "badge_type": "creator" if is_creator else ("blue" if profile.get("is_verified") or profile.get("verified") else ""),
        "badge_label": "Creator" if is_creator else "Verified",
        "bio": profile.get("bio") or "",
        "website": profile.get("website") or "",
        "category": profile.get("category") or profile.get("profile_type") or "",
        "is_friend": action_policy.get("relationship") == "friend",
        "is_following": action_policy.get("relationship") in ("following", "friend"),
        "request_sent": action_policy.get("relationship") == "pending_sent",
        "posts_count": posts_count,
        "reels_count": reels_count,
        "stories_count": _as_int(stats.get("stories") or len(content.get("stories") or [])),
        "followers_count": _as_int(stats.get("followers") or profile.get("followers_count")),
        "following_count": _as_int(stats.get("following") or profile.get("following_count")),
        "friends_count": _as_int(stats.get("friends") or profile.get("friends_count")),
        "likes_count": _as_int(stats.get("likes") or profile.get("total_likes")),
        "views_count": views_count,
        "has_active_stories": bool(content.get("stories") if isinstance(content, dict) else False),
        "mutual_friends": mutual_friends.get("items") or [],
        "report_url": f"/report/profile/{profile.get('id')}" if profile.get("id") else None,

        # ─── Premium profile field passthrough ───
        "pronouns": profile.get("pronouns"),
        "occupation": profile.get("occupation"),
        "company": profile.get("company"),
        "school": profile.get("school"),
        "university": profile.get("university"),
        "premium_tier": entitlement["effective_plan"],
        "subscription_status": entitlement["subscription_status"],
        "is_premium": entitlement["is_premium"],
        "subscription_entitlement": entitlement,
        "verification_type": profile.get("verification_type") or ("gold" if profile.get("verified") and (profile.get("identity_verified") or profile.get("professional_membership")) else ("blue" if profile.get("verified") or profile.get("is_verified") else "none")),
        "is_gold_verified": bool(profile.get("verification_type") == "gold" or (bool(profile.get("verified")) and (bool(profile.get("identity_verified")) or bool(profile.get("professional_membership"))))),
        "gold_badge": bool(profile.get("gold_badge") or (profile.get("verification_type") == "gold")),
        "premium_badge": bool(profile.get("premium_badge")),
        "creator_badge": bool(profile.get("creator_badge")),
        "business_badge": bool(profile.get("business_badge")),
        "government_badge": bool(profile.get("government_badge")),
        "ngo_badge": bool(profile.get("ngo_badge")),
        "student_badge": bool(profile.get("student_badge")),
        "medical_badge": bool(profile.get("medical_badge")),
        "teacher_badge": bool(profile.get("teacher_badge")),
        "profile_score": _as_int(profile.get("profile_score")),
        "profile_level": profile.get("profile_level") or "Bronze",
        "country_flag": profile.get("country_flag"),
        "city_name": profile.get("city_name"),
        "current_activity": profile.get("current_activity"),
        "mood_emoji": profile.get("mood_emoji"),
        "mood_text": profile.get("mood_text"),
        "local_time": profile.get("local_time"),
        "weather_emoji": profile.get("weather_emoji"),
        "weather_temp": profile.get("weather_temp"),
        "quote_of_day": profile.get("quote_of_day"),
        "activity_status": profile.get("activity_status") or "online",
        "total_profile_views": _as_int(profile.get("total_profile_views") or profile.get("profile_views")),
        "total_likes": _as_int(profile.get("total_likes") or stats.get("likes")),
        "total_shares": _as_int(profile.get("total_shares")),
        "total_bookmarks": _as_int(profile.get("total_bookmarks")),
        "total_achievements": _as_int(profile.get("total_achievements")),
        "total_collections": _as_int(profile.get("total_collections")),
        "total_albums": _as_int(profile.get("total_albums")),
        "years_on_namvibe": _compute_years(profile.get("created_at")),
        "trust_score": _as_int(profile.get("trust_score")),
        "community_rating": profile.get("community_rating"),
        "friendliness_score": _as_int(profile.get("friendliness_score")),
        "safety_score": _as_int(profile.get("safety_score")),
        "response_rate": _as_int(profile.get("response_rate")),
        "response_time": profile.get("response_time") or "< 1h",
        "popularity_score": _as_int(profile.get("popularity_score")),
        "activity_level": _as_int(profile.get("activity_level")),
        "identity_verified": bool(profile.get("identity_verified") or profile.get("is_verified")),
        "scam_protection": bool(profile.get("scam_protection") if profile.get("scam_protection") is not None else True),
        "languages_list": _format_list(profile.get("languages") or profile.get("preferred_language")),
        "interests_list": _format_list(profile.get("interests")),
        "skills_list": _format_list(profile.get("skills")),
        "member_since_year": _member_year(profile.get("created_at")),
        "city": (profile.get("city_name") or profile.get("city") or profile.get("town") or ""),
        "total_comments": _as_int(profile.get("total_comments")),
        "total_downloads": _as_int(profile.get("total_downloads")),
        "total_live_hours": _as_int(profile.get("total_live_hours")),
        "total_voice_calls": _as_int(profile.get("total_voice_calls")),
        "total_video_calls": _as_int(profile.get("total_video_calls")),
        "total_messages": _as_int(profile.get("total_messages")),
        "total_visits": _as_int(profile.get("total_visits") or profile.get("profile_views")),
        "total_earnings": profile.get("total_earnings") or 0,
        "total_marketplace_sales": _as_int(profile.get("total_marketplace_sales")),
        "relationship_status": profile.get("relationship_status") or "",
        "email": profile.get("email") or "",
        "phone": profile.get("phone") or "",
        "cover_video_url": profile.get("cover_video_url") or profile.get("profile_video_url") or "",
        "nationality": profile.get("nationality") or "",
        "verified_id": bool(profile.get("verified_id") or profile.get("identity_verified")),
        "driving_licence": bool(profile.get("driving_licence")),
        "student_card": bool(profile.get("student_card")),
        "employee_card": bool(profile.get("employee_card")),
        "health_card": bool(profile.get("health_card")),
        "business_licence": bool(profile.get("business_licence")),
        "professional_membership": bool(profile.get("professional_membership")),
        "volunteer_badge": bool(profile.get("volunteer_badge")),
        "favorite_songs": profile.get("favorite_songs") or [],
        "recently_played": profile.get("recently_played") or [],
        "playlists": profile.get("playlists") or [],
        "favorite_artists": profile.get("favorite_artists") or [],
        "favorite_games_list": profile.get("favorite_games") or [],
        "gaming_level": profile.get("gaming_level") or "",
        "gaming_achievements": profile.get("gaming_achievements") or [],
        "countries_visited": profile.get("countries_visited") or [],
        "cities_visited": profile.get("cities_visited") or [],
        "travel_wishlist": profile.get("travel_wishlist") or [],
        "fitness_steps": _as_int(profile.get("fitness_steps")),
        "fitness_workouts": _as_int(profile.get("fitness_workouts")),
        "fitness_cycling": _as_int(profile.get("fitness_cycling")),
        "fitness_running": _as_int(profile.get("fitness_running")),
        "fitness_calories": _as_int(profile.get("fitness_calories")),
        "fitness_goals": profile.get("fitness_goals") or "",
        "fitness_sleep": profile.get("fitness_sleep") or "",
        "marketplace_items_selling": _as_int(profile.get("marketplace_items_selling")),
        "marketplace_wishlist": _as_int(profile.get("marketplace_wishlist")),
        "marketplace_purchased": _as_int(profile.get("marketplace_purchased")),
        "marketplace_reviews": _as_int(profile.get("marketplace_reviews")),
        "wallet_coins": _as_int(wallet.get("coin_balance") if isinstance(wallet, dict) else 0),
        "wallet_rewards": _as_int(profile.get("wallet_rewards")),
        "wallet_tips": _as_int(profile.get("wallet_tips")),
        "wallet_revenue": _as_int(profile.get("wallet_revenue")),
        "subscriptions_count": _as_int(profile.get("subscriptions_count")),
        "subscribers_count": _as_int(profile.get("subscribers_count")),
        "studio_enabled": bool(creator.get("studio_enabled") if isinstance(creator, dict) else False),
        "business_name": profile.get("business_name") or profile.get("company") or "",
        "business_hours": profile.get("business_opening_hours") or "",
        "business_map": profile.get("business_location_data") or "",
        "business_whatsapp": profile.get("business_contact_phone") or "",
        "business_booking": profile.get("business_booking_url") or "",
        "business_appointments": profile.get("business_appointments_enabled") or False,
        "business_delivery": profile.get("business_delivery_enabled") or False,
        "business_catalogue": profile.get("business_catalogue") or [],
        "ai_profile_summary": profile.get("ai_profile_summary") or "",
        "ai_bio_suggestions": profile.get("ai_bio_suggestions") or [],
        "ai_friend_suggestions": profile.get("ai_friend_suggestions") or [],
        "ai_creator_recommendations": profile.get("ai_creator_recommendations") or [],
        "ai_growth_analysis": profile.get("ai_growth_analysis") or "",
    }
