from urllib.parse import urlencode

from django.urls import NoReverseMatch, reverse

from .services import is_master_admin, master_admin_dashboard_url

def _safe_reverse(name, fallback="#"):
    try:
        return reverse(name)
    except NoReverseMatch:
        return fallback


def _current_route(request):
    match = getattr(request, "resolver_match", None)
    return {
        "url_name": getattr(match, "url_name", "") or "",
        "view_name": getattr(match, "view_name", "") or "",
        "namespace": getattr(match, "namespace", "") or "",
        "path": request.path,
    }


def _is_active(route, *names):
    haystack = {route["url_name"], route["view_name"], route["namespace"], route["path"]}
    return any(name in haystack or route["path"].startswith(name) for name in names)


def _drawer_groups(request, smart_profile_url):
    route = _current_route(request)
    items = [
        {
            "title": "Watch",
            "items": [
                {"label": "Home", "url": _safe_reverse("home"), "icon": "home", "active": _is_active(route, "home", "/")},
                {"label": "Feed", "url": _safe_reverse("feed"), "icon": "spark", "active": _is_active(route, "feed", "feed_following", "feed_friends", "feed_trending", "feed_nearby")},
                {"label": "Reels / Videos", "url": _safe_reverse("reels_feed"), "icon": "play", "active": _is_active(route, "reels_feed", "posts_reels_feed")},
                {"label": "Stories", "url": _safe_reverse("story_create"), "icon": "story", "active": _is_active(route, "story_create", "story_detail")},
                {"label": "Discover", "url": _safe_reverse("discover"), "icon": "discover", "active": _is_active(route, "discover", "discover_search", "posts_discover")},
                {"label": "Dating", "url": _safe_reverse("dating"), "icon": "heart", "active": _is_active(route, "dating", "dating_discover", "dating_matches", "dating_likes", "dating_profile_detail", "dating_profile_edit")},
                {"label": "Live", "url": _safe_reverse("live_home"), "icon": "live", "active": _is_active(route, "live_home", "live_room", "live_featured", "live_scheduled")},
                {"label": "Live Studio", "url": _safe_reverse("live_start"), "icon": "broadcast", "active": _is_active(route, "live_start", "legacy_live_studio")},
                {"label": "Communities", "url": _safe_reverse("community_list"), "icon": "community", "active": _is_active(route, "community_list", "community_detail", "community_create")},
                {"label": "Channels", "url": _safe_reverse("channels"), "icon": "channel", "active": _is_active(route, "channels")},
                {"label": "Gaming", "url": _safe_reverse("gaming"), "icon": "gaming", "active": _is_active(route, "gaming")},
            ],
        },
        {
            "title": "Create and Earn",
            "items": [
                {"label": "Wallet", "url": _safe_reverse("wallet_home"), "icon": "wallet", "active": _is_active(route, "wallet_home", "wallet_transactions", "wallet_gifts", "wallet_membership", "wallet_membership_plans", "wallet_creator_earnings")},
                {"label": "Premium", "url": _safe_reverse("wallet_membership_plans"), "icon": "premium", "active": _is_active(route, "wallet_membership", "wallet_membership_plans", "premium_tier")},
                {"label": "Gifting", "url": _safe_reverse("gifting"), "icon": "gift", "active": _is_active(route, "gifting")},
                {"label": "Coins", "url": _safe_reverse("coins"), "icon": "coin", "active": _is_active(route, "coins")},
                {"label": "Photo Selling", "url": _safe_reverse("photo_selling"), "icon": "camera", "active": _is_active(route, "photo_selling")},
                {"label": "Flyer Studio", "url": _safe_reverse("flyer_tools"), "icon": "flyer", "active": _is_active(route, "flyer_tools")},
                {"label": "Image Tools", "url": _safe_reverse("image_tools"), "icon": "image", "active": _is_active(route, "image_tools")},
                {"label": "Studio / Creator Tools", "url": _safe_reverse("studio"), "icon": "studio", "active": _is_active(route, "studio", "studio_create", "posts_studio", "posts_studio_create", "posts_studio_draft")},
                {"label": "Ads / Promotions", "url": _safe_reverse("ads_home"), "icon": "megaphone", "active": _is_active(route, "ads_home", "ads_starter")},
            ],
        },
        {
            "title": "Account",
            "items": [
                {"label": "Support", "url": _safe_reverse("support_help"), "icon": "support", "active": _is_active(route, "support_help", "support_center", "support_control")},
                {"label": "Settings", "url": _safe_reverse("settings"), "icon": "settings", "active": _is_active(route, "settings", "profile_edit")},
                {"label": "Profile / Account", "url": smart_profile_url, "icon": "user", "active": _is_active(route, "user_dashboard", "profile_detail", "profile_edit")},
            ],
        },
    ]
    auth_items = []
    if request.user.is_authenticated:
        if is_master_admin(request.user) or (hasattr(request.user, "account_role") and request.user.account_role.is_admin):
            auth_items.append({"label": "Control", "url": _safe_reverse("support_control"), "icon": "shield", "active": _is_active(route, "support_control")})
        auth_items.append({"label": "Logout", "url": _safe_reverse("logout"), "icon": "logout", "active": False})
    else:
        auth_items.extend(
            [
                {"label": "Login", "url": _safe_reverse("login"), "icon": "login", "active": _is_active(route, "login")},
                {"label": "Signup", "url": _safe_reverse("signup"), "icon": "premium", "active": _is_active(route, "signup")},
            ]
        )
    items.append({"title": "Session", "items": auth_items})
    return items


def _bottom_actions(request, smart_profile_url):
    route = _current_route(request)
    page = "default"
    actions = [
        {"label": "Home", "url": _safe_reverse("home"), "icon": "home", "active": _is_active(route, "home")},
        {"label": "Videos", "url": _safe_reverse("reels_feed"), "icon": "play", "active": _is_active(route, "reels_feed")},
        {"label": "Create", "url": _safe_reverse("studio"), "icon": "plus", "active": _is_active(route, "studio")},
        {"label": "Live", "url": _safe_reverse("live_home"), "icon": "live", "active": _is_active(route, "live_home", "live_room")},
        {"label": "Profile", "url": smart_profile_url, "icon": "user", "active": _is_active(route, "user_dashboard", "profile_detail", "profile_edit")},
    ]

    if _is_active(route, "profile_detail", "profile_edit"):
        page = "profile"
        actions = [
            {"label": "Profile", "url": smart_profile_url, "icon": "user", "active": True},
            {"label": "Edit", "url": _safe_reverse("profile_edit"), "icon": "edit", "active": _is_active(route, "profile_edit")},
            {"label": "Posts", "url": request.path + "#posts", "icon": "spark", "active": False},
            {"label": "Activity", "url": _safe_reverse("notifications"), "icon": "bell", "active": False},
            {"label": "Menu", "url": "#", "icon": "menu", "active": False, "drawer_trigger": True},
        ]
    elif _is_active(route, "live_home", "live_room", "live_start", "live_studio", "legacy_live_studio"):
        page = "live"
        actions = [
            {"label": "Explore", "url": _safe_reverse("live_home"), "icon": "discover", "active": _is_active(route, "live_home", "live_room")},
            {"label": "Go Live", "url": _safe_reverse("live_start"), "icon": "broadcast", "active": _is_active(route, "live_start", "live_studio", "legacy_live_studio")},
            {"label": "Chats", "url": _safe_reverse("user_dashboard") + "?section=messages", "icon": "chat", "active": False},
            {"label": "Gifts", "url": _safe_reverse("wallet_gifts"), "icon": "gift", "active": False},
            {"label": "Menu", "url": "#", "icon": "menu", "active": False, "drawer_trigger": True},
        ]
    elif route["namespace"] == "messaging" or _is_active(route, "user_dashboard"):
        page = "messaging"
        actions = [
            {"label": "Chats", "url": _safe_reverse("user_dashboard") + "?section=messages", "icon": "chat", "active": True},
            {"label": "Calls", "url": _safe_reverse("user_dashboard") + "?section=messages", "icon": "phone", "active": False},
            {"label": "Video", "url": _safe_reverse("user_dashboard") + "?section=messages", "icon": "video", "active": False},
            {"label": "Contacts", "url": _safe_reverse("discover"), "icon": "community", "active": False},
            {"label": "Menu", "url": "#", "icon": "menu", "active": False, "drawer_trigger": True},
        ]
    elif _is_active(route, "wallet_home", "wallet_transactions", "wallet_gifts", "wallet_membership", "wallet_membership_plans", "wallet_creator_earnings"):
        page = "wallet"
        actions = [
            {"label": "Wallet", "url": _safe_reverse("wallet_home"), "icon": "wallet", "active": True},
            {"label": "Send", "url": _safe_reverse("wallet_gifts"), "icon": "gift", "active": False},
            {"label": "Buy", "url": _safe_reverse("wallet_membership_plans"), "icon": "premium", "active": False},
            {"label": "History", "url": _safe_reverse("wallet_transactions"), "icon": "history", "active": False},
            {"label": "Menu", "url": "#", "icon": "menu", "active": False, "drawer_trigger": True},
        ]
    elif _is_active(route, "dating", "dating_discover", "dating_matches", "dating_likes", "dating_profile_detail", "dating_profile_edit"):
        page = "dating"
        actions = [
            {"label": "Discover", "url": _safe_reverse("dating_discover"), "icon": "discover", "active": _is_active(route, "dating", "dating_discover")},
            {"label": "Likes", "url": _safe_reverse("dating_likes"), "icon": "heart", "active": _is_active(route, "dating_likes")},
            {"label": "Matches", "url": _safe_reverse("dating_matches"), "icon": "spark", "active": _is_active(route, "dating_matches")},
            {"label": "Profile", "url": _safe_reverse("dating_profile_edit"), "icon": "user", "active": _is_active(route, "dating_profile_edit", "dating_profile_detail")},
            {"label": "Menu", "url": "#", "icon": "menu", "active": False, "drawer_trigger": True},
        ]
    elif _is_active(route, "community_detail", "community_list", "community_create"):
        page = "community"
        actions = [
            {"label": "Feed", "url": _safe_reverse("community_list"), "icon": "spark", "active": _is_active(route, "community_list", "community_detail")},
            {"label": "Members", "url": request.path + "#members", "icon": "community", "active": False},
            {"label": "Media", "url": request.path + "#media", "icon": "image", "active": False},
            {"label": "Events", "url": _safe_reverse("live_home"), "icon": "live", "active": False},
            {"label": "Menu", "url": "#", "icon": "menu", "active": False, "drawer_trigger": True},
        ]
    return page, actions


def profile_navigation(request):
    dashboard_url = reverse("user_dashboard")
    login_url = reverse("login")
    if request.user.is_authenticated:
        smart_profile_url = master_admin_dashboard_url() if is_master_admin(request.user) else dashboard_url
    else:
        smart_profile_url = f"{login_url}?{urlencode({'next': dashboard_url})}"

    current_route = _current_route(request)
    page_kind, bottom_actions = _bottom_actions(request, smart_profile_url)
    return {
        "smart_profile_url": smart_profile_url,
        "profile_dashboard_url": dashboard_url,
        "current_route": current_route,
        "app_drawer_groups": _drawer_groups(request, smart_profile_url),
        "mobile_action_page": page_kind,
        "mobile_action_items": bottom_actions,
    }
