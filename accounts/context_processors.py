from urllib.parse import urlencode

from django.urls import NoReverseMatch, reverse

from .services import is_master_admin, master_admin_dashboard_url

def _safe_reverse(name, fallback="home"):
    try:
        return reverse(name)
    except NoReverseMatch:
        return reverse(fallback)


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
    items = [{
        "title": "Navigation",
        "items": [
            {"label": "Home", "url": _safe_reverse("home"), "icon": "home", "active": _is_active(route, "home", "/")},
            {"label": "Feed", "url": _safe_reverse("feed"), "icon": "spark", "active": _is_active(route, "feed", "feed_following", "feed_friends", "feed_trending", "feed_nearby", "reels_feed")},
            {"label": "Dating", "url": _safe_reverse("dating"), "icon": "heart", "active": _is_active(route, "dating", "dating_discover", "dating_matches", "dating_likes", "dating_profile_detail", "dating_profile_edit")},
            {"label": "Live", "url": _safe_reverse("live_home"), "icon": "live", "active": _is_active(route, "live_home", "live_room", "live_featured", "live_scheduled", "live_shows")},
            {"label": "Games", "url": _safe_reverse("games_home"), "icon": "gaming", "active": _is_active(route, "games_home", "gaming")},
            {"label": "Pink Friday", "url": _safe_reverse("pink_friday"), "icon": "premium", "active": _is_active(route, "pink_friday")},
        ],
    }]
    if request.user.is_authenticated:
        items[0]["items"].extend([
            {"label": "Wallet", "url": _safe_reverse("wallet_home"), "icon": "wallet", "active": _is_active(route, "wallet_home", "wallet_transactions", "wallet_gifts", "wallet_membership", "wallet_membership_plans", "wallet_creator_earnings")},
            {"label": "Profile", "url": smart_profile_url, "icon": "user", "active": _is_active(route, "user_dashboard", "profile_detail", "profile_edit")},
        ])
    auth_items = []
    if request.user.is_authenticated:
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
    actions = [
        {"label": "Home", "url": _safe_reverse("home"), "icon": "home", "active": _is_active(route, "home")},
        {"label": "Explore", "url": _safe_reverse("discover"), "icon": "discover", "active": _is_active(route, "discover", "discover_search", "reels_feed")},
        {"label": "Create", "url": _safe_reverse("studio"), "icon": "plus", "active": _is_active(route, "studio")},
        {"label": "Dating", "url": _safe_reverse("dating"), "icon": "heart", "active": _is_active(route, "dating", "dating_discover", "dating_matches", "dating_likes", "dating_profile_detail", "dating_profile_edit")},
        {"label": "Profile", "url": smart_profile_url, "icon": "user", "active": _is_active(route, "user_dashboard", "profile_detail", "profile_edit")},
    ]
    return "default", actions


def _nav_counters(request):
    if not request.user.is_authenticated:
        return {
            "nav_notification_count": 0,
            "nav_message_count": 0,
            "nav_notifications_url": _safe_reverse("notifications"),
            "nav_messages_url": _safe_reverse("messages_home"),
        }
    try:
        from accounts.models import Notification
        from messaging.models import Message

        unread_notifications = Notification.objects.filter(recipient=request.user, is_read=False).count()
        unread_messages = (
            Message.objects.filter(conversation__participants=request.user, read_at__isnull=True)
            .exclude(sender=request.user)
            .count()
        )
    except Exception:
        unread_notifications = 0
        unread_messages = 0
    return {
        "nav_notification_count": unread_notifications,
        "nav_message_count": unread_messages,
        "nav_notifications_url": _safe_reverse("notifications"),
        "nav_messages_url": _safe_reverse("messages_home"),
    }


def profile_navigation(request):
    dashboard_url = reverse("user_dashboard")
    login_url = reverse("login")
    if request.user.is_authenticated:
        smart_profile_url = master_admin_dashboard_url() if is_master_admin(request.user) else dashboard_url
    else:
        smart_profile_url = f"{login_url}?{urlencode({'next': dashboard_url})}"

    current_route = _current_route(request)
    page_kind, bottom_actions = _bottom_actions(request, smart_profile_url)
    primary_nav_links = [
        {"label": "Home", "url": _safe_reverse("home"), "active": _is_active(current_route, "home", "/")},
        {"label": "Feed", "url": _safe_reverse("feed"), "active": _is_active(current_route, "feed", "feed_following", "feed_friends", "feed_trending", "feed_nearby")},
        {"label": "Dating", "url": _safe_reverse("dating"), "active": _is_active(current_route, "dating", "dating_discover", "dating_matches", "dating_likes", "dating_profile_detail", "dating_profile_edit")},
        {"label": "Live", "url": _safe_reverse("live_home"), "active": _is_active(current_route, "live_home", "live_room", "live_featured", "live_scheduled")},
        {"label": "Games", "url": _safe_reverse("games_home"), "active": _is_active(current_route, "games_home", "gaming")},
        {"label": "Pink Friday", "url": _safe_reverse("pink_friday"), "active": _is_active(current_route, "pink_friday")},
    ]
    if request.user.is_authenticated:
        primary_nav_links.extend([
            {"label": "Wallet", "url": _safe_reverse("wallet_home"), "active": _is_active(current_route, "wallet_home", "wallet_transactions", "wallet_gifts", "wallet_membership", "wallet_membership_plans", "wallet_creator_earnings")},
            {"label": "Profile", "url": smart_profile_url, "active": _is_active(current_route, "user_dashboard", "profile_detail", "profile_edit")},
        ])
    return {
        "smart_profile_url": smart_profile_url,
        "profile_dashboard_url": dashboard_url,
        "current_route": current_route,
        "primary_nav_links": primary_nav_links,
        "app_drawer_groups": _drawer_groups(request, smart_profile_url),
        "mobile_action_page": page_kind,
        "mobile_action_items": bottom_actions,
        **_nav_counters(request),
    }
