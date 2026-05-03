import logging

from django.contrib.auth.models import User
from django.db.models import Q
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from accounts.models import Block, Follow, FriendRequest, Profile
from live.services import live_now_for
from messaging.models import Message
from messaging.presence import presence_snapshot
from posts.models import Comment, Like, Post
from posts.services import base_visible_posts, suggested_users_for
from stories.models import StoryItem
from stories.services import story_rail_for
from wallet.services import (
    VIBE_COIN_DISPLAY_RATE,
    active_boosted_post_ids,
    active_membership_for,
    ensure_wallet,
    premium_badge_for,
)

logger = logging.getLogger(__name__)


def _safe_profile_url(user):
    profile = getattr(user, "profile", None)
    if profile and profile.username:
        return reverse("profile_detail", kwargs={"username": profile.username})
    return reverse("user_dashboard")


def _login_dashboard_url():
    return f"{reverse('login')}?next=%2Faccounts%2Fdashboard%2F"


def _safe_reverse(name, fallback=None, **kwargs):
    try:
        return reverse(name, kwargs=kwargs or None)
    except NoReverseMatch:
        return fallback or reverse("home")


def _safe_section(label, default, callback):
    try:
        return callback()
    except Exception as exc:
        logger.warning("Homepage section '%s' failed with %s", label, exc.__class__.__name__)
        return default() if callable(default) else default


def _header_counts(user):
    if not user.is_authenticated:
        return {"messages": 0, "notifications": 0}

    unread_messages = Message.objects.filter(conversation__participants=user, read_at__isnull=True).exclude(sender=user).count()
    pending_friends = FriendRequest.objects.filter(to_user=user, status=FriendRequest.Status.PENDING).count()
    post_activity = Comment.objects.filter(post__author=user).exclude(author=user).count()
    return {
        "messages": unread_messages,
        "notifications": unread_messages + pending_friends + post_activity,
    }


def _wallet_snapshot(user):
    if not user.is_authenticated:
        return None
    wallet = ensure_wallet(user)
    membership = active_membership_for(user)
    return {
        "account": wallet,
        "active_membership": membership,
        "available_balance": getattr(wallet, "available_balance", 0),
        "pending_balance": getattr(wallet, "pending_balance", 0),
    }


def _visible_profile_queryset(user):
    queryset = Profile.objects.select_related("user").filter(is_hidden_by_moderation=False)
    if not user.is_authenticated:
        return queryset

    blocked_pairs = Block.objects.filter(Q(blocker=user) | Q(blocked=user)).values_list("blocker_id", "blocked_id")
    blocked_user_ids = {item for pair in blocked_pairs for item in pair if item and item != user.id}
    return queryset.exclude(user=user).exclude(user_id__in=blocked_user_ids)


def _friend_request_between(user, other_user):
    if not user.is_authenticated:
        return None
    return FriendRequest.objects.filter(
        Q(from_user=user, to_user=other_user) | Q(from_user=other_user, to_user=user)
    ).order_by("-updated_at").first()


def _member_cards(user, profiles, limit=6):
    cards = []
    followed_ids = set()
    if user.is_authenticated:
        followed_ids = set(Follow.objects.filter(follower=user).values_list("following_id", flat=True))

    for profile in profiles[:limit]:
        if user.is_authenticated and profile.user_id == user.id:
            continue

        presence = presence_snapshot(profile.user)
        friend_request = _friend_request_between(user, profile.user) if user.is_authenticated else None
        is_friend = bool(friend_request and friend_request.status == FriendRequest.Status.ACCEPTED)
        request_sent = bool(
            friend_request
            and friend_request.status == FriendRequest.Status.PENDING
            and friend_request.from_user_id == user.id
        )
        request_received = bool(
            friend_request
            and friend_request.status == FriendRequest.Status.PENDING
            and friend_request.to_user_id == user.id
        )
        display_name = profile.display_name or profile.username or profile.user.username
        username = profile.username or profile.user.username

        if is_friend:
            action_label = "Chat"
        elif request_received:
            action_label = "Accept Friend"
        elif request_sent:
            action_label = "Request Sent"
        else:
            action_label = "Add Friend"

        cards.append(
            {
                "profile": profile,
                "display_name": display_name,
                "username": username,
                "bio": (profile.bio or "").strip(),
                "location": ", ".join([item for item in [profile.town, profile.region, profile.location] if item]) or "Namibia",
                "profile_url": _safe_reverse("profile_detail", username=username),
                "presence": presence,
                "is_online": presence.get("is_online", False),
                "is_following": profile.user_id in followed_ids,
                "is_friend": is_friend,
                "request_sent": request_sent,
                "request_received": request_received,
                "friend_request_id": getattr(friend_request, "id", 0),
                "primary_action_label": action_label,
                "follow_url": _safe_reverse("follow_toggle", username=username),
                "friend_request_url": _safe_reverse("friend_request_send", username=username),
                "friend_accept_url": _safe_reverse("friend_request_accept", request_id=getattr(friend_request, "id", 0)),
                "chat_url": _safe_reverse("messaging:start_chat", fallback="member_discovery", user_id=profile.user.id),
                "premium_badge": premium_badge_for(profile.user),
            }
        )
    return cards


def _online_member_cards(user, limit=6, sample_size=60):
    profiles = list(
        _visible_profile_queryset(user)
        .order_by("-is_verified", "-follower_count", "-post_count", "-created_at")[:sample_size]
    )
    online = [profile for profile in profiles if presence_snapshot(profile.user)["is_online"]]
    return _member_cards(user, online, limit=limit)


def _recent_member_cards(user, limit=6, sample_size=80):
    profiles = list(
        _visible_profile_queryset(user)
        .order_by("-is_verified", "-follower_count", "-post_count", "-created_at")[:sample_size]
    )
    ranked = []
    for profile in profiles:
        presence = presence_snapshot(profile.user)
        if presence["is_online"] or presence["label"] == "Active recently":
            ranked.append((presence["is_online"], profile.created_at, profile))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return _member_cards(user, [item[2] for item in ranked], limit=limit)


def _suggested_member_cards(user, limit=6):
    suggested = list(suggested_users_for(user, limit=limit * 2))
    filtered = [profile for profile in suggested if not getattr(profile, "is_hidden_by_moderation", False)]
    if not filtered:
        filtered = list(
            _visible_profile_queryset(user)
            .order_by("-is_verified", "-is_creator", "-follower_count", "-post_count", "-created_at")[:limit]
        )
    return _member_cards(user, filtered, limit=limit)


def _feed_items(posts):
    items = []
    for post in posts:
        items.append(
            {
                "kind": "reel" if post.post_type in {Post.PostType.REEL, Post.PostType.VIDEO} else "post",
                "post": post,
            }
        )
    return items[:20]


def _mobile_action_items(user):
    return [
        {"label": "Home", "icon": "home", "url": reverse("home")},
        {"label": "Reels", "icon": "video", "url": reverse("reels_feed")},
        {"label": "Create", "icon": "plus", "action_launcher": True},
        {"label": "Messages", "icon": "message-circle", "url": reverse("messages_home") if user.is_authenticated else reverse("login")},
        {"label": "Profile", "icon": "user", "url": reverse("user_dashboard") if user.is_authenticated else reverse("login")},
    ]


def _hero_actions(user):
    if user.is_authenticated:
        return [
            {"label": "Create Post", "url": reverse("studio"), "tone": "primary"},
            {"label": "Story", "url": reverse("story_create"), "tone": "secondary"},
            {"label": "Reel", "url": f"{reverse('studio')}?type=reel", "tone": "secondary"},
            {"label": "Live", "url": reverse("live_start"), "tone": "secondary"},
        ]
    return [
        {"label": "Join Namvibe", "url": reverse("signup"), "tone": "primary"},
        {"label": "Login", "url": reverse("login"), "tone": "secondary"},
    ]


def _quick_create_items():
    return [
        {"label": "Post", "url": reverse("studio")},
        {"label": "Story", "url": reverse("story_create")},
        {"label": "Reel", "url": f"{reverse('studio')}?type=reel"},
        {"label": "Live", "url": reverse("live_start")},
    ]


def homepage_context(request, page=1, fragment=False):
    user = request.user
    page = max(1, min(int(page or 1), 50))
    limit = 20
    offset = (page - 1) * limit

    visible_posts = (
        base_visible_posts(user)
        .published()
        .select_related("author", "author__profile")
        .prefetch_related("media", "comments__author__profile")
        .order_by("-published_at", "-created_at")
    )
    primary_posts = list(visible_posts[offset : offset + limit])

    boosted_post_ids = set(active_boosted_post_ids([post.id for post in primary_posts]))
    liked_ids = set()
    if user.is_authenticated and primary_posts:
        liked_ids = set(Like.objects.filter(user=user, post__in=primary_posts).values_list("post_id", flat=True))

    for post in primary_posts:
        post.is_boosted = post.id in boosted_post_ids
        post.is_liked = post.id in liked_ids
        post.author_premium_badge = premium_badge_for(post.author)

    if fragment:
        return {
            "mixed_feed": _feed_items(primary_posts),
            "feed_fragment_empty": not primary_posts,
        }

    story_rail = _safe_section("story_rail", [], lambda: story_rail_for(user, limit=12))
    live_preview = _safe_section("live_preview", [], lambda: list(live_now_for(user)[:4]))
    online_members = _safe_section("online_members", [], lambda: _online_member_cards(user, limit=6))
    suggested_members = _safe_section("suggested_members", [], lambda: _suggested_member_cards(user, limit=6))
    recent_members = _safe_section("recent_members", [], lambda: _recent_member_cards(user, limit=6))
    wallet_snapshot = _safe_section("wallet_snapshot", None, lambda: _wallet_snapshot(user))
    header_counts = _safe_section("header_counts", {"messages": 0, "notifications": 0}, lambda: _header_counts(user))

    current_profile = getattr(user, "profile", None) if user.is_authenticated else None
    reel_preview = [post for post in primary_posts if post.post_type in {Post.PostType.REEL, Post.PostType.VIDEO}][:6]
    public_story_count = StoryItem.objects.active().count()
    hero_metrics = [
        {"label": "Stories", "value": public_story_count},
        {"label": "Reels", "value": visible_posts.filter(post_type__in=[Post.PostType.REEL, Post.PostType.VIDEO]).count()},
        {"label": "Posts", "value": visible_posts.count()},
        {"label": "Members", "value": User.objects.count()},
    ]

    return {
        "mobile_action_items": _mobile_action_items(user),
        "story_rail": story_rail,
        "mixed_feed": _feed_items(primary_posts),
        "feed_fragment_empty": not primary_posts,
        "reel_preview": reel_preview,
        "live_preview": live_preview,
        "online_members": online_members,
        "suggested_members": suggested_members,
        "recent_members": recent_members,
        "wallet_snapshot": wallet_snapshot,
        "hero_metrics": hero_metrics,
        "hero_actions": _hero_actions(user),
        "quick_create_items": _quick_create_items(),
        "current_profile": current_profile,
        "nav_notification_count": header_counts["notifications"],
        "nav_message_count": header_counts["messages"],
        "nav_messages_url": reverse("messages_home"),
        "nav_wallet_url": reverse("wallet_home"),
        "nav_profile_url": _safe_profile_url(user) if user.is_authenticated else _login_dashboard_url(),
        "nav_profile_label": (current_profile.display_name or current_profile.username) if current_profile else "Guest",
        "nav_search_placeholder": "Search people, posts, stories, and live rooms",
        "join_url": reverse("signup"),
        "login_url": reverse("login"),
        "messages_url": reverse("messages_home") if user.is_authenticated else reverse("login"),
        "members_url": reverse("member_discovery"),
        "wallet_url": reverse("wallet_home"),
        "profile_url": _safe_profile_url(user) if user.is_authenticated else _login_dashboard_url(),
        "reels_url": reverse("reels_feed"),
        "live_url": reverse("live_home"),
        "coin_display_rate": VIBE_COIN_DISPLAY_RATE,
        "now": timezone.now(),
    }


def fallback_homepage_context(request, error_message=""):
    user = request.user
    current_profile = getattr(user, "profile", None) if user.is_authenticated else None
    return {
        "mobile_action_items": _mobile_action_items(user),
        "story_rail": [],
        "mixed_feed": [],
        "feed_fragment_empty": True,
        "reel_preview": [],
        "live_preview": [],
        "online_members": [],
        "suggested_members": [],
        "recent_members": [],
        "wallet_snapshot": None,
        "hero_metrics": [],
        "hero_actions": _hero_actions(user),
        "quick_create_items": _quick_create_items(),
        "current_profile": current_profile,
        "nav_notification_count": 0,
        "nav_message_count": 0,
        "nav_messages_url": reverse("messages_home") if user.is_authenticated else reverse("login"),
        "nav_wallet_url": reverse("wallet_home"),
        "nav_profile_url": _safe_profile_url(user) if user.is_authenticated else _login_dashboard_url(),
        "nav_profile_label": (current_profile.display_name or current_profile.username) if current_profile else "Guest",
        "nav_search_placeholder": "Search people, posts, stories, and live rooms",
        "join_url": reverse("signup"),
        "login_url": reverse("login"),
        "messages_url": reverse("messages_home") if user.is_authenticated else reverse("login"),
        "members_url": reverse("member_discovery"),
        "wallet_url": reverse("wallet_home"),
        "profile_url": _safe_profile_url(user) if user.is_authenticated else _login_dashboard_url(),
        "reels_url": reverse("reels_feed"),
        "live_url": reverse("live_home"),
        "coin_display_rate": VIBE_COIN_DISPLAY_RATE,
        "now": timezone.now(),
        "homepage_error": error_message,
    }
