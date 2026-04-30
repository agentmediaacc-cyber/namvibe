from urllib.parse import urlencode
import logging
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth import login as django_login, logout as django_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_POST, require_http_methods

from live.models import LiveSession
from messaging.models import Conversation, Message
from messaging.services import messaging_dashboard_context
from dating.models import DatingCoinBalance, DatingLike, DatingProfileView, Match
from posts.models import Post
from posts.services import base_visible_posts
from posts.supabase_posts import get_posts_by_user
from stories.models import StoryItem
from wallet.services import active_membership_for, ensure_wallet
from communities.models import CommunityMembership

from .forms import LoginForm, ProfileForm, SignupForm
from .models import AccountProfile, Block, Follow, FriendRequest, Profile
from .services import (
    account_rank_for_value,
    ensure_account_role,
    is_valid_uuid,
    is_master_admin,
    load_email_verification_token,
    master_admin_dashboard_url,
    master_admin_email,
    master_admin_supabase_uid,
    next_auth_redirect,
    onboarding_items_for,
    repair_master_admin_user,
    send_verification_email,
)
from .supabase import (
    ensure_supabase_profile,
    find_supabase_profile,
    get_supabase_profile,
    sign_in_supabase_auth,
    supabase_profile_id_for_user,
)

logger = logging.getLogger(__name__)


def _empty_message_threads(unread_total=0):
    return {
        "chat_conversations": [],
        "active_conversation": None,
        "has_selected_conversation": False,
        "active_chat_other": None,
        "active_messages": [],
        "message_form": None,
        "all_chat_users": [],
        "chat_unread_total": unread_total,
        "chat_unread_threads": unread_total,
        "chat_total_messages": 0,
        "chat_media_messages": 0,
    }


def _safe_redirect(request, fallback="user_dashboard"):
    redirect_to = request.POST.get("next") or request.GET.get("next") or reverse(fallback)
    if url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to
    return reverse(fallback)


def _login_url_with_next(route_name):
    return f"{reverse('login')}?{urlencode({'next': reverse(route_name)})}"


def _safe_reverse(name, fallback="user_dashboard", **kwargs):
    try:
        return reverse(name, kwargs=kwargs or None)
    except NoReverseMatch:
        return reverse(fallback)


def _profile_edit_url(tab=""):
    url = reverse("profile_edit")
    if tab:
        return f"{url}?tab={tab}"
    return url


def _friendship_q(left_user, right_user):
    return (
        Q(from_user=left_user, to_user=right_user)
        | Q(from_user=right_user, to_user=left_user)
    )


def _users_are_friends(left_user, right_user):
    if not left_user.is_authenticated:
        return False
    return FriendRequest.objects.filter(
        _friendship_q(left_user, right_user),
        status=FriendRequest.Status.ACCEPTED,
    ).exists()


def _friend_request_between(left_user, right_user):
    if not left_user.is_authenticated:
        return None
    return FriendRequest.objects.filter(_friendship_q(left_user, right_user)).order_by("-updated_at").first()


def _account_path_active(request, route_name):
    match = getattr(request, "resolver_match", None)
    return getattr(match, "url_name", "") == route_name


def _account_rank(profile, wallet, coin_balance):
    balance_candidates = [
        getattr(coin_balance, "balance", 0),
        getattr(wallet, "available_balance", 0),
        getattr(wallet, "pending_balance", 0),
    ]
    numeric_balance = 0
    for value in balance_candidates:
        try:
            numeric_balance = max(numeric_balance, int(float(value or 0)))
        except (TypeError, ValueError):
            continue
    rank = account_rank_for_value(numeric_balance)
    if getattr(profile, "is_verified", False) and rank["label"] == "Namvibe":
        rank = {**rank, "icon": "✓"}
    return rank


def _profile_menu_groups(request):
    settings_url = _safe_reverse("account_settings")
    privacy_url = _safe_reverse("account_privacy")
    security_url = _safe_reverse("account_security")
    profile_username = getattr(getattr(request.user, "profile", None), "username", "") or request.user.username
    groups = [
        {
            "title": "Account",
            "items": [
                {"label": "Overview", "url": _safe_reverse("user_dashboard")},
                {"label": "Edit Profile", "url": settings_url},
                {"label": "Profile Picture", "url": _profile_edit_url("picture")},
                {"label": "Cover Image", "url": _profile_edit_url("cover")},
                {"label": "Settings", "url": settings_url},
                {"label": "Privacy Settings", "url": privacy_url},
                {"label": "Security / PIN Reset", "url": security_url},
            ],
        },
        {
            "title": "Social",
            "items": [
                {"label": "Feed", "url": _safe_reverse("feed")},
                {"label": "Gallery", "url": _safe_reverse("profile_gallery")},
                {"label": "Posts", "url": _safe_reverse("author_posts", username=profile_username)},
                {"label": "Stories", "url": _safe_reverse("stories_home")},
                {"label": "Reels", "url": _safe_reverse("reels_feed")},
                {"label": "Messages", "url": _safe_reverse("messages_home")},
                {"label": "Notifications", "url": _safe_reverse("notifications")},
                {"label": "Followers", "url": _safe_reverse("account_followers")},
                {"label": "Groups / Communities", "url": _safe_reverse("community_list")},
            ],
        },
        {
            "title": "Money / Access",
            "items": [
                {"label": "Wallet", "url": _safe_reverse("wallet_home")},
                {"label": "Coins", "url": _safe_reverse("coins")},
                {"label": "Upgrade Account", "url": _safe_reverse("wallet_membership_plans")},
                {"label": "Subscription", "url": _safe_reverse("wallet_membership")},
            ],
        },
        {
            "title": "Creator / Model",
            "items": [
                {"label": "Become Creator", "url": _safe_reverse("studio")},
                {"label": "Model / Streamer Application", "url": _safe_reverse("account_model_application")},
                {"label": "Verification Status", "url": _safe_reverse("verify_email_notice")},
                {"label": "Live Studio", "url": _safe_reverse("live_start")},
            ],
        },
        {
            "title": "Entertainment",
            "items": [
                {"label": "Dating", "url": _safe_reverse("dating")},
                {"label": "Games", "url": _safe_reverse("games_home")},
                {"label": "Pink Friday", "url": _safe_reverse("pink_friday")},
                {"label": "Live Shows", "url": _safe_reverse("live_shows")},
            ],
        },
        {
            "title": "Help",
            "items": [
                {"label": "Support", "url": _safe_reverse("support_help")},
                {"label": "Logout", "url": _safe_reverse("logout")},
            ],
        },
    ]
    for group in groups:
        for item in group["items"]:
            dashboard_url = _safe_reverse("user_dashboard")
            item["active"] = request.path == item["url"] or (
                item["url"] == dashboard_url and _account_path_active(request, "user_dashboard")
            )
    return groups


def _dashboard_route_cards(request, profile, completion, rank, gallery_count, unread_count):
    cards = [
        {"title": "Profile Settings", "emoji": "⚙️", "url": _safe_reverse("account_settings"), "meta": "Profile, privacy, security"},
        {"title": "Gallery / Album", "emoji": "🖼️", "url": _safe_reverse("profile_gallery"), "meta": f"{gallery_count} items" if gallery_count else "Open album"},
        {"title": "Wallet", "emoji": "💳", "url": _safe_reverse("wallet_home"), "meta": "Balance and membership"},
        {"title": "Messages", "emoji": "💬", "url": _safe_reverse("messages_home"), "meta": f"{unread_count} unread" if unread_count else "Open inbox"},
        {"title": "Notifications", "emoji": "🔔", "url": _safe_reverse("notifications"), "meta": "Activity and alerts"},
        {"title": "Dating", "emoji": "💕", "url": _safe_reverse("dating"), "meta": "Discovery and matches"},
        {"title": "Model / Streamer", "emoji": "🎤", "url": _safe_reverse("account_model_application"), "meta": "Apply safely"},
        {"title": "Live", "emoji": "📡", "url": _safe_reverse("live_home"), "meta": "Rooms and go live"},
        {"title": "Games", "emoji": "🎮", "url": _safe_reverse("games_home"), "meta": "Friendly social games"},
        {"title": "Pink Friday", "emoji": "🌸", "url": _safe_reverse("pink_friday"), "meta": "Weekly event"},
        {"title": "Support", "emoji": "🛟", "url": _safe_reverse("support_help"), "meta": "Help and account safety"},
    ]
    return cards


def _member_cards_for(user, profiles, *, include_friendship=True):
    cards = []
    for profile in profiles:
        if include_friendship and user.is_authenticated and profile.user == user:
            continue
        friend_request = _friend_request_between(user, profile.user) if include_friendship and user.is_authenticated else None
        is_friend = bool(friend_request and friend_request.status == FriendRequest.Status.ACCEPTED)
        request_sent = bool(
            friend_request
            and friend_request.status == FriendRequest.Status.PENDING
            and friend_request.from_user_id == user.id
        ) if user.is_authenticated else False
        request_received = bool(
            friend_request
            and friend_request.status == FriendRequest.Status.PENDING
            and friend_request.to_user_id == user.id
        ) if user.is_authenticated else False
        is_following = Follow.objects.filter(follower=user, following=profile.user).exists() if user.is_authenticated else False
        cards.append(
            {
                "profile": profile,
                "display_name": profile.display_name or profile.username or profile.user.username,
                "username": profile.username or profile.user.username,
                "bio": (profile.bio or "").strip(),
                "location": ", ".join([item for item in [profile.town, profile.region, profile.location] if item]) or "Namibia",
                "profile_url": _safe_reverse("profile_detail", username=profile.username or profile.user.username),
                "is_following": is_following,
                "is_friend": is_friend,
                "request_sent": request_sent,
                "request_received": request_received,
                "can_chat": is_friend,
                "follow_url": _safe_reverse("follow_toggle", username=profile.username or profile.user.username),
                "friend_request_url": _safe_reverse("friend_request_send", username=profile.username or profile.user.username),
                "friend_accept_url": _safe_reverse("friend_request_accept", request_id=getattr(friend_request, "id", 0)),
                "chat_url": _safe_reverse("messaging:start_chat", fallback="user_dashboard", user_id=profile.user.id),
            }
        )
    return cards


def _dashboard_next_actions(profile, completion, unread_count):
    next_actions = [
        {
            "title": "Complete profile",
            "copy": completion.get("next_action", {}).get("label") if completion.get("next_action") else "Review your profile details and finish key setup.",
            "url": _safe_reverse("profile_edit"),
            "emoji": "✨",
        },
        {
            "title": "Upload story",
            "copy": "Share a quick photo, clip, or text update.",
            "url": _safe_reverse("story_create"),
            "emoji": "📸",
        },
        {
            "title": "Check messages",
            "copy": f"{unread_count} unread waiting for you." if unread_count else "Open your inbox and start a new chat.",
            "url": _safe_reverse("messages_home"),
            "emoji": "💬",
        },
        {
            "title": "Open wallet",
            "copy": "Review balance, coins, and premium access.",
            "url": _safe_reverse("wallet_home"),
            "emoji": "💳",
        },
        {
            "title": "Go live",
            "copy": "Start a room or schedule your next session.",
            "url": _safe_reverse("live_start"),
            "emoji": "📡",
        },
    ]
    return next_actions


def _set_account_session(request, user):
    profile = getattr(user, "account_profile", None)
    full_name = profile.full_name if profile else user.get_full_name()
    email = profile.email if profile else user.email

    request.session["eharo_user_id"] = str(user.id)
    request.session["eharo_full_name"] = full_name or user.username
    request.session["eharo_username"] = user.username
    request.session["eharo_email"] = email or ""


def _ensure_auth_profile(user):
    Profile.objects.get_or_create(
        user=user,
        defaults={
            "username": user.username,
            "display_name": user.username,
        },
    )


def _ensure_account_profile(user):
    account_profile, _created = AccountProfile.objects.get_or_create(
        user=user,
        defaults={
            "full_name": user.get_full_name() or user.username,
            "email": (user.email or f"{user.username}@local.invalid").lower(),
            "phone_country_code": "+264",
            "cellphone_number": f"+264{user.pk or 0}",
            "residential_address": "",
            "country_of_origin": "Namibia",
            "current_country": "Namibia",
            "profile_completed": False,
            "email_verified": False,
        },
    )
    return account_profile


def _ensure_user_bootstrap(user):
    try:
        _ensure_auth_profile(user)
    except Exception as exc:
        logger.error("Bootstrap: _ensure_auth_profile failed for %s: %s", user.username, exc)

    try:
        account_profile = _ensure_account_profile(user)
    except Exception as exc:
        logger.error("Bootstrap: _ensure_account_profile failed for %s: %s", user.username, exc)
        account_profile = getattr(user, "account_profile", None)

    try:
        DatingCoinBalance.for_user(user)
    except Exception as exc:
        logger.error("Bootstrap: DatingCoinBalance.for_user failed for %s: %s", user.username, exc)

    try:
        ensure_account_role(user)
    except Exception as exc:
        logger.error("Bootstrap: ensure_account_role failed for %s: %s", user.username, exc)

    return account_profile


def _safe_sync_supabase_profile(user):
    try:
        return ensure_supabase_profile(user)
    except Exception as exc:
        logger.exception("Supabase profile sync crashed for user_id=%s with %s", user.pk, exc.__class__.__name__)
        return None


def _safe_send_verification_email(request, user):
    try:
        return send_verification_email(request, user)
    except Exception as exc:
        logger.exception("Verification email flow crashed for user_id=%s with %s", user.pk, exc.__class__.__name__)
        return False, "Your account was created, but verification email could not be sent right now."


def _available_username(seed):
    base = slugify(seed or "namvibe-user").replace("-", "_")[:30] or "namvibe_user"
    username = base
    counter = 2
    while User.objects.filter(username__iexact=username).exists():
        suffix = f"_{counter}"
        username = f"{base[:30 - len(suffix)]}{suffix}"
        counter += 1
    return username


def _master_admin_candidate():
    email = master_admin_email()
    uid = master_admin_supabase_uid()
    if uid:
        candidate = User.objects.filter(account_role__supabase_uid=uid).first()
        if candidate:
            return candidate
    if email:
        candidate = User.objects.filter(email__iexact=email).order_by("id").first()
        if candidate:
            return candidate
    return None


def _dashboard_metrics(user):
    wallet = ensure_wallet(user)
    onboarding_items, onboarding_progress = onboarding_items_for(user)
    return {
        "wallet_balance": getattr(wallet, "available_balance", 0),
        "pending_balance": getattr(wallet, "pending_balance", 0),
        "onboarding_items": onboarding_items,
        "onboarding_progress": onboarding_progress,
        "active_membership": active_membership_for(user),
    }


def has_active_subscription(user):
    return active_membership_for(user) is not None


def free_message_quota_remaining(user):
    if has_active_subscription(user):
        return None
    started_threads = (
        Conversation.objects.filter(participants=user, messages__sender=user)
        .distinct()
        .count()
    )
    return max(0, 3 - started_threads)


def can_open_messages(user):
    if has_active_subscription(user):
        return True
    if Conversation.objects.filter(participants=user).exists():
        return True
    return free_message_quota_remaining(user) > 0


def _section_url(section_name):
    return f"{reverse('user_dashboard')}?{urlencode({'section': section_name})}"


def _profile_completion_snapshot(user, profile, account_profile, dating_profile, published_post_count):
    checks = [
        {
            "label": "Add profile picture",
            "done": bool(profile.avatar),
            "url": reverse("profile_edit"),
        },
        {
            "label": "Add cover image",
            "done": bool(profile.cover_image),
            "url": reverse("profile_edit"),
        },
        {
            "label": "Set display name",
            "done": bool((profile.display_name or "").strip()),
            "url": reverse("profile_edit"),
        },
        {
            "label": "Write your bio",
            "done": bool((profile.bio or "").strip()),
            "url": reverse("profile_edit"),
        },
        {
            "label": "Add your region",
            "done": bool((profile.region or "").strip()),
            "url": reverse("profile_edit"),
        },
        {
            "label": "Add your town",
            "done": bool((profile.town or "").strip()),
            "url": reverse("profile_edit"),
        },
        {
            "label": "Add your phone",
            "done": bool(account_profile and account_profile.cellphone_number),
            "url": reverse("profile_edit"),
        },
        {
            "label": "Connect dating",
            "done": bool(dating_profile),
            "url": reverse("dating_profile"),
        },
        {
            "label": "Create your first post",
            "done": published_post_count > 0,
            "url": reverse("studio"),
        },
    ]
    completed = sum(1 for check in checks if check["done"])
    percentage = int((completed / len(checks)) * 100) if checks else 0
    next_action = next((check for check in checks if not check["done"]), None)
    return {
        "percentage": percentage,
        "checks": checks,
        "next_action": next_action,
    }


def _account_level_badge(user, wallet, membership):
    if membership:
        plan_name = membership.plan.name
        is_vip = "vip" in plan_name.lower()
        return {
            "label": "Premium Member" if not is_vip else "VIP Member",
            "tone": "premium",
            "accent": "gold",
            "icon": "👑" if not is_vip else "✨",
        }
    if any(getattr(wallet, field, 0) > 0 for field in ("available_balance", "pending_balance", "lifetime_earned")):
        return {
            "label": "Active Wallet",
            "tone": "wallet",
            "accent": "silver",
            "icon": "◈",
        }
    return {
        "label": "Namvibe User",
        "tone": "member",
        "accent": "green",
        "icon": "●",
    }


def _gallery_items_for(profile, posts, stories):
    items = []
    if profile.avatar:
        items.append({"kind": "Profile Picture", "type": "image", "url": profile.avatar.url, "target": reverse("profile_edit")})
    if profile.cover_image:
        items.append({"kind": "Cover Image", "type": "image", "url": profile.cover_image.url, "target": reverse("profile_edit")})
    for story in stories:
        if story.file:
            items.append(
                {
                    "kind": "Story",
                    "type": "video" if story.media_type == StoryItem.MediaType.VIDEO else "image",
                    "url": story.file.url,
                    "target": reverse("story_detail", kwargs={"id": story.id}),
                    "caption": story.caption or story.text_content[:60],
                }
            )
    for post in posts:
        for media in post.media.all():
            if len(items) >= 16:
                return items
            items.append(
                {
                    "kind": post.get_post_type_display(),
                    "type": "video" if media.media_type == media.MediaType.VIDEO else "image",
                    "url": media.thumbnail.url if media.thumbnail else media.file.url,
                    "target": reverse("post_detail", kwargs={"uuid": post.uuid}),
                    "caption": post.title or post.caption[:60] or post.get_post_type_display(),
                }
            )
    return items


def _dashboard_section_groups():
    return [
        {
            "title": "Account",
            "items": [
                {"key": "overview", "label": "Profile"},
                {"key": "gallery", "label": "Gallery"},
                {"key": "posts", "label": "Posts"},
                {"key": "reels", "label": "Reels"},
                {"key": "stories", "label": "Stories"},
                {"key": "dating", "label": "Dating"},
            ],
        },
        {
            "title": "Platform",
            "items": [
                {"key": "wallet", "label": "Wallet"},
                {"key": "messages", "label": "Messages"},
                {"key": "notifications", "label": "Notifications"},
                {"key": "creator", "label": "Creator"},
                {"key": "live", "label": "Live"},
                {"key": "games", "label": "Games"},
            ],
        },
        {
            "title": "Support",
            "items": [
                {"key": "support", "label": "Support"},
                {"key": "settings", "label": "Settings"},
                {"key": "logout", "label": "Logout", "url": reverse("logout")},
            ],
        },
    ]


def _user_from_supabase_login(identifier, password, auth_payload, profile_payload):
    auth_user = auth_payload.get("user") or {}
    email = (auth_user.get("email") or identifier).lower()
    full_name = (
        (profile_payload or {}).get("full_name")
        or (auth_user.get("user_metadata") or {}).get("full_name")
        or email.split("@")[0]
    )
    username = (
        (profile_payload or {}).get("username")
        or (auth_user.get("user_metadata") or {}).get("username")
        or email.split("@")[0]
    )

    master_uid = auth_user.get("id") or ""
    user = None
    if master_uid:
        user = User.objects.filter(account_role__supabase_uid=master_uid).first()
    if user is None and email:
        if email == master_admin_email():
            user = _master_admin_candidate()
        if user is None:
            user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User.objects.create_user(
            username=_available_username(username),
            email=email,
            password=password,
            first_name=full_name,
        )
    else:
        user.set_password(password)
        if full_name and not user.get_full_name():
            user.first_name = full_name
        user.save()

    _ensure_auth_profile(user)
    profile_username = (profile_payload or {}).get("username") or user.profile.username
    if Profile.objects.filter(username__iexact=profile_username).exclude(user=user).exists():
        profile_username = user.profile.username
    Profile.objects.filter(user=user).update(
        username=profile_username,
        display_name=user.profile.display_name or profile_username,
    )

    phone = (profile_payload or {}).get("phone") or ""
    account_profile, _ = AccountProfile.objects.get_or_create(
        user=user,
        defaults={
            "full_name": full_name,
            "email": email,
            "phone_country_code": "+264",
            "cellphone_number": phone or f"+264{user.id}",
            "residential_address": "",
            "country_of_origin": "Namibia",
            "current_country": "Namibia",
        },
    )
    if full_name and not account_profile.full_name:
        account_profile.full_name = full_name
    if email and not account_profile.email:
        account_profile.email = email
    if phone and not account_profile.cellphone_number:
        account_profile.cellphone_number = phone
    account_profile.save()

    if email == master_admin_email() or master_uid == master_admin_supabase_uid():
        repair_master_admin_user(user, supabase_uid=master_uid, email=email)
    else:
        ensure_account_role(user, supabase_uid=master_uid)
    return user


def login_view(request):
    if request.user.is_authenticated:
        try:
            _set_account_session(request, request.user)
            ensure_account_role(request.user)
        except Exception as exc:
            logger.error("Login authenticated: failed setting session/role: %s", exc)
        
        if is_master_admin(request.user):
            return redirect(master_admin_dashboard_url())
        return redirect("user_dashboard")

    form = LoginForm(request.POST or None)
    clean_login_error = None

    if request.method == "POST":
        if form.is_valid():
            user = form.cleaned_data["user"]
            try:
                _ensure_user_bootstrap(user)
                _safe_sync_supabase_profile(user)
            except Exception as exc:
                logger.error("Login POST: bootstrap failed for %s: %s", user.username, exc)

            django_login(request, user)
            if form.cleaned_data.get("remember_me"):
                request.session.set_expiry(60 * 60 * 24 * 30)
            else:
                request.session.set_expiry(0)
            
            try:
                _set_account_session(request, user)
                if is_master_admin(user):
                    repair_master_admin_user(user, supabase_uid=getattr(getattr(user, "account_role", None), "supabase_uid", ""), email=user.email)
            except Exception as exc:
                logger.error("Login POST: session/master-repair failed for %s: %s", user.username, exc)

            account_profile = getattr(user, "account_profile", None)
            if account_profile and not account_profile.email_verified:
                messages.info(request, "Verify your email to unlock trusted account features and admin approvals.")
            return redirect(next_auth_redirect(request, user))

        identifier = request.POST.get("identifier", "").strip().lower()
        password = request.POST.get("password", "")
        if "@" in identifier and password:
            supabase_profile = find_supabase_profile(email=identifier)
            auth_payload, auth_error = sign_in_supabase_auth(identifier, password)
            if auth_payload:
                user = _user_from_supabase_login(identifier, password, auth_payload, supabase_profile)
                try:
                    _ensure_user_bootstrap(user)
                    _safe_sync_supabase_profile(user)
                except Exception as exc:
                    logger.error("Login Supabase: bootstrap failed for %s: %s", user.username, exc)

                django_login(request, user)
                if request.POST.get("remember_me"):
                    request.session.set_expiry(60 * 60 * 24 * 30)
                else:
                    request.session.set_expiry(0)
                
                try:
                    _set_account_session(request, user)
                    if is_master_admin(user):
                        repair_master_admin_user(user, supabase_uid=auth_payload.get("user", {}).get("id", ""), email=user.email)
                except Exception as exc:
                    logger.error("Login Supabase: session/master-repair failed for %s: %s", user.username, exc)

                account_profile = getattr(user, "account_profile", None)
                if account_profile and not account_profile.email_verified:
                    messages.info(request, "Verify your email to unlock trusted account features and admin approvals.")
                return redirect(next_auth_redirect(request, user))
            if supabase_profile and auth_error != "not_configured":
                clean_login_error = "Incorrect password."

    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": _safe_redirect(request), "clean_login_error": clean_login_error},
    )


def logout_view(request):
    django_logout(request)
    request.session.flush()
    return redirect("login")


def signup_view(request):
    if request.user.is_authenticated:
        try:
            _set_account_session(request, request.user)
            ensure_account_role(request.user)
        except Exception as exc:
            logger.error("Signup authenticated: failed setting session/role: %s", exc)
        
        if is_master_admin(request.user):
            return redirect(master_admin_dashboard_url())
        return redirect("user_dashboard")

    form = SignupForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        normalized_phone = form.cleaned_data["normalized_phone"]
        existing_supabase_profile = find_supabase_profile(
            email=form.cleaned_data["email"],
            username=form.cleaned_data["username"],
            phone=normalized_phone,
        )
        if existing_supabase_profile:
            messages.error(request, "An account with those details already exists. Try logging in instead.")
            return render(request, "accounts/signup.html", {"form": form})

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=form.cleaned_data["username"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    first_name=form.cleaned_data["full_name"],
                )
                AccountProfile.objects.create(
                    user=user,
                    full_name=form.cleaned_data["full_name"],
                    email=form.cleaned_data["email"],
                    phone_country_code=form.cleaned_data["country_code"],
                    cellphone_number=normalized_phone,
                    residential_address="",
                    country_of_origin="Namibia",
                    current_country="Namibia",
                    profile_completed=False,
                    email_verified=False,
                )
            
            try:
                _ensure_user_bootstrap(user)
                _safe_sync_supabase_profile(user)
            except Exception as exc:
                logger.error("Signup: bootstrap failed for %s: %s", user.username, exc)

            django_login(request, user)
            request.session.set_expiry(60 * 60 * 24 * 14)

            try:
                _set_account_session(request, user)
            except Exception as exc:
                logger.error("Signup: _set_account_session failed for %s: %s", user.username, exc)

            sent, note = _safe_send_verification_email(request, user)
            if note:
                if sent:
                    messages.success(request, note)
                else:
                    messages.info(request, note)
            messages.success(request, "Your account is ready. Complete the rest from your new Namvibe account hub.")
            return redirect("user_dashboard")

        except IntegrityError:
            messages.error(
                request,
                "An account with those details already exists. Check username, email, and cellphone number.",
            )

    return render(request, "accounts/signup.html", {"form": form})


def forgot_password_view(request):
    form = PasswordResetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            form.save(
                request=request,
                use_https=request.is_secure(),
                from_email=None,
                email_template_name="accounts/password_reset_email.html",
                subject_template_name="accounts/password_reset_subject.txt",
            )
        except Exception as exc:
            logger.warning("Password reset email could not be sent: %s", exc)
        messages.success(request, "If that email belongs to a Namvibe account, a reset link has been sent.")
        return redirect("forgot_password")
    return render(request, "accounts/forgot_password.html", {"form": form})


def verify_email_request_view(request):
    if request.method == "POST":
        identifier = (request.POST.get("email") or "").strip().lower()
        user = User.objects.filter(email__iexact=identifier).first()
        if user and hasattr(user, "account_profile") and not user.account_profile.email_verified:
            sent, note = send_verification_email(request, user)
            if sent:
                messages.success(request, "If this account exists, a fresh verification email has been sent.")
            else:
                messages.info(request, note)
        else:
            messages.success(request, "If this account exists, a fresh verification email has been sent.")
        return redirect("verify_email_request")
    return render(request, "accounts/verify_email_request.html")


@login_required(login_url="login")
def verify_email_notice_view(request):
    ensure_account_role(request.user)
    if is_master_admin(request.user):
        return redirect(master_admin_dashboard_url())
    account_profile = getattr(request.user, "account_profile", None)
    if account_profile and account_profile.email_verified:
        messages.success(request, "Your email is already verified.")
        return redirect("user_dashboard")
    return render(
        request,
        "accounts/verify_email_notice.html",
        {
            "account_profile": account_profile,
        },
    )


@login_required(login_url="login")
@require_POST
def resend_verification_email_view(request):
    sent, note = send_verification_email(request, request.user)
    if sent:
        messages.success(request, note)
    else:
        messages.info(request, note)
    return redirect("verify_email_notice")


def verify_email_confirm_view(request, token):
    try:
        payload = load_email_verification_token(token)
    except Exception:
        return render(request, "accounts/verify_email_result.html", {"verification_ok": False})

    user = get_object_or_404(User, pk=payload.get("user_id"), email__iexact=payload.get("email"))
    account_profile = getattr(user, "account_profile", None)
    if account_profile:
        account_profile.email_verified = True
        account_profile.profile_completed = True
        account_profile.save(update_fields=["email_verified", "profile_completed", "updated_at"])
    return render(request, "accounts/verify_email_result.html", {"verification_ok": True, "verified_user": user})


def profile_completion_view(request):
    if not request.user.is_authenticated:
        return redirect(_login_url_with_next("profile_completion"))
    messages.info(request, "Finish your setup from your account hub.")
    return redirect(f"{reverse('user_dashboard')}?section=overview")


def _account_shell_context(request, profile, account_profile=None, coin_balance=None):
    wallet = ensure_wallet(request.user)
    if coin_balance is None:
        try:
            coin_balance = DatingCoinBalance.for_user(request.user)
        except Exception:
            coin_balance = SimpleNamespace(balance=0)
    published_post_count = Post.objects.filter(author=request.user, status=Post.Status.PUBLISHED).count()
    completion = _profile_completion_snapshot(
        request.user,
        profile,
        account_profile,
        getattr(request.user, "dating_profile", None),
        published_post_count,
    )
    rank = _account_rank(profile, wallet, coin_balance)
    return {
        "profile": profile,
        "account_profile": account_profile,
        "profile_completion": completion,
        "completion": completion,
        "account_rank": rank,
        "profile_menu_groups": _profile_menu_groups(request),
        "account_shell_title": "My Account",
        "account_shell_subtitle": "Profile, settings, and feature routing",
        "wallet_account": wallet,
        "coin_balance": coin_balance,
    }


def user_dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect(_login_url_with_next("user_dashboard"))

    _set_account_session(request, request.user)
    _ensure_user_bootstrap(request.user)
    account_role = ensure_account_role(request.user)
    if is_master_admin(request.user, role=account_role):
        repair_master_admin_user(
            request.user,
            supabase_uid=getattr(account_role, "supabase_uid", ""),
            email=request.user.email,
        )
        return redirect(master_admin_dashboard_url())
    supabase_profile = _safe_sync_supabase_profile(request.user) or get_supabase_profile(request.user)

    profile = request.user.profile
    account_profile = getattr(request.user, "account_profile", None)
    local_posts_qs = (
        Post.objects.filter(author=request.user)
        .select_related("author", "author__profile", "community")
        .prefetch_related("media", "poll__options")
        .order_by("-published_at", "-created_at")
    )
    local_posts = list(local_posts_qs[:12])
    legacy_posts = []
    if not local_posts:
        try:
            session_user_id = request.session.get("eharo_user_id")
            legacy_post_user_id = str(supabase_profile_id_for_user(request.user))
            if is_valid_uuid(session_user_id):
                legacy_posts = get_posts_by_user(session_user_id)
            if not legacy_posts and is_valid_uuid(legacy_post_user_id):
                legacy_posts = get_posts_by_user(legacy_post_user_id)
        except Exception as exc:
            logger.warning("LOAD POSTS ERROR: %s", exc)
    full_name = (
        (supabase_profile or {}).get("full_name")
        or getattr(account_profile, "full_name", "")
        or request.user.get_full_name()
        or request.user.username
    )
    username = (supabase_profile or {}).get("username") or profile.username or request.user.username
    email = (supabase_profile or {}).get("email") or getattr(account_profile, "email", "") or request.user.email
    published_post_count = local_posts_qs.filter(status=Post.Status.PUBLISHED).count()
    post_count = max(profile.post_count, published_post_count, len(local_posts), len(legacy_posts))
    try:
        dashboard_metrics = _dashboard_metrics(request.user)
    except Exception as exc:
        logger.warning("Dashboard metrics fallback for user %s: %s", request.user.pk, exc)
        dashboard_metrics = {
            "wallet_balance": 0,
            "pending_balance": 0,
            "onboarding_items": [],
            "onboarding_progress": 0,
            "active_membership": None,
        }
    requested_section = request.GET.get("section")
    try:
        coin_balance = DatingCoinBalance.for_user(request.user)
    except Exception as exc:
        logger.warning("Dating coin balance fallback for user %s: %s", request.user.pk, exc)
        coin_balance = SimpleNamespace(balance=0)
    dating_profile = getattr(request.user, "dating_profile", None)
    dating_views_count = (
        DatingProfileView.objects.filter(viewed_profile=dating_profile).values("viewer_id").distinct().count()
        if dating_profile
        else 0
    )
    profile_views_count = (
        Post.objects.filter(author=request.user, status=Post.Status.PUBLISHED).aggregate(total=Sum("view_count")).get("total")
        or 0
    )
    notifications_preview = []
    conversation_id = request.GET.get("conversation")
    is_message_panel_requested = requested_section == "messages" or bool(conversation_id)
    if is_message_panel_requested:
        try:
            unread_threads = messaging_dashboard_context(request.user, conversation_id)
        except Exception as exc:
            logger.warning("Messaging dashboard fallback for user %s: %s", request.user.pk, exc)
            unread_total = Message.objects.filter(
                conversation__participants=request.user,
                read_at__isnull=True,
            ).exclude(sender=request.user).count()
            unread_threads = _empty_message_threads(unread_total=unread_total)
    else:
        unread_total = Message.objects.filter(
            conversation__participants=request.user,
            read_at__isnull=True,
        ).exclude(sender=request.user).count()
        unread_threads = _empty_message_threads(unread_total=unread_total)
    if unread_threads["chat_unread_total"]:
        notifications_preview.append({
            "title": "Unread messages",
            "copy": f"{unread_threads['chat_unread_total']} new messages across your chat threads.",
            "url": f"{reverse('user_dashboard')}?section=messages",
        })
    pending_follows = Follow.objects.filter(following=request.user).select_related("follower__profile").order_by("-created_at")[:3]
    for edge in pending_follows:
        notifications_preview.append({
            "title": f"@{edge.follower.profile.username} followed you",
            "copy": "Open your profile to follow back or start a chat.",
            "url": reverse("profile_detail", kwargs={"username": edge.follower.profile.username}),
        })
    recent_dating_likes = DatingLike.objects.filter(to_user=request.user).select_related("from_user__profile").order_by("-created_at")[:2]
    for like in recent_dating_likes:
        notifications_preview.append({
            "title": f"Dating like from @{like.from_user.profile.username}",
            "copy": "A new dating interaction is waiting in your likes view.",
            "url": reverse("dating_likes"),
        })
    activity_items = []
    recent_posts = list(local_posts_qs[:3])
    for post in recent_posts:
        activity_items.append({
            "title": post.title or post.caption[:72] or post.get_post_type_display(),
            "meta": f"{post.get_post_type_display()} · {post.published_at or post.created_at}",
            "url": reverse("post_detail", kwargs={"uuid": post.uuid}),
        })
    active_matches = Match.objects.filter(
        Q(user_one=request.user) | Q(user_two=request.user),
        is_active=True,
    ).count()
    if not activity_items and active_matches:
        activity_items.append({
            "title": "Dating activity",
            "meta": f"{active_matches} active matches available now.",
            "url": reverse("dating_matches"),
        })
    if not activity_items:
        activity_items.append({
            "title": "Start your first activity",
            "meta": "Create a post, update your profile, or open dating discovery.",
            "url": reverse("studio"),
        })

    following_preview = list(
        Follow.objects.filter(follower=request.user)
        .select_related("following__profile")
        .order_by("-created_at")[:6]
    )
    follower_preview = list(
        Follow.objects.filter(following=request.user)
        .select_related("follower__profile")
        .order_by("-created_at")[:6]
    )
    user_stories = list(
        StoryItem.objects.filter(author=request.user)
        .order_by("-created_at")[:8]
    )
    live_sessions = list(
        LiveSession.objects.filter(host=request.user)
        .order_by("-starts_at", "-created_at")[:8]
    )
    reel_posts = [post for post in local_posts if post.post_type == Post.PostType.REEL]
    story_posts = [post for post in local_posts if post.post_type == Post.PostType.STORY]
    media_posts = [post for post in local_posts if post.post_type in {Post.PostType.PHOTO, Post.PostType.VIDEO, Post.PostType.REEL}]
    completion = _profile_completion_snapshot(request.user, profile, account_profile, dating_profile, published_post_count)
    wallet = ensure_wallet(request.user)
    rank = _account_rank(profile, wallet, coin_balance)
    badge = _account_level_badge(request.user, wallet, dashboard_metrics["active_membership"])
    gallery_items = _gallery_items_for(profile, local_posts, user_stories)
    active_panel = requested_section or ("messages" if conversation_id else "overview")
    if active_panel not in {"overview", "gallery", "posts", "messages"}:
        active_panel = "overview"
    recent_message_partners = []
    for item in unread_threads.get("chat_conversations", [])[:5]:
        if item.get("other") is not None:
            recent_message_partners.append(item)
    message_quota_remaining = free_message_quota_remaining(request.user)
    dashboard_cards = _dashboard_route_cards(
        request,
        profile,
        completion,
        rank,
        len(gallery_items),
        unread_threads.get("chat_unread_total", 0),
    )
    next_actions = _dashboard_next_actions(profile, completion, unread_threads.get("chat_unread_total", 0))

    context = {
        "full_name": full_name,
        "username": username,
        "email": email,
        "profile": profile,
        "supabase_profile": supabase_profile,
        "account_profile": account_profile,
        "user_posts": local_posts,
        "legacy_user_posts": legacy_posts,
        "post_count": post_count,
        "account_role": account_role,
        "draft_posts": Post.objects.filter(author=request.user, status=Post.Status.DRAFT).prefetch_related("media")[:8],
        "saved_post_count": request.user.post_saves.count(),
        "community_count": CommunityMembership.objects.filter(user=request.user, status=CommunityMembership.Status.ACTIVE).count(),
        "active_panel": active_panel,
        "following_preview": following_preview,
        "follower_preview": follower_preview,
        "coin_balance": coin_balance,
        "dating_profile": dating_profile,
        "dating_views_count": dating_views_count,
        "profile_views_count": profile_views_count,
        "notifications_preview": notifications_preview[:5],
        "activity_items": activity_items,
        "active_match_count": active_matches,
        "completion": completion,
        "profile_completion": completion,
        "account_badge": badge,
        "account_rank": rank,
        "gallery_items": gallery_items,
        "gallery_preview_items": gallery_items[:4],
        "story_items": user_stories,
        "reel_posts": reel_posts,
        "story_posts": story_posts,
        "media_posts": media_posts,
        "live_sessions": live_sessions,
        "support_center_url": reverse("support_help"),
        "settings_url": reverse("profile_edit"),
        "profile_gallery_url": reverse("profile_gallery"),
        "account_section_groups": _dashboard_section_groups(),
        "profile_menu_groups": _profile_menu_groups(request),
        "dashboard_cards": dashboard_cards,
        "next_action_cards": next_actions,
        "recent_message_partners": recent_message_partners,
        "messages_preview": recent_message_partners[:2],
        "has_active_subscription": has_active_subscription(request.user),
        "free_message_quota_remaining": message_quota_remaining,
        "can_open_messages": can_open_messages(request.user),
        "audio_call_url": reverse("messaging:call_gate", kwargs={"user_id": request.user.id, "mode": "voice"}),
        "video_call_url": reverse("messaging:call_gate", kwargs={"user_id": request.user.id, "mode": "video"}),
        "account_shell_title": "My Account",
        "account_shell_subtitle": "Clean profile index and smart routing",
        **dashboard_metrics,
        **unread_threads,
    }
    return render(request, "accounts/dashboard.html", context)


def public_profile_view(request, username):
    profile = get_object_or_404(Profile.objects.select_related("user"), username__iexact=username)
    is_blocked = False
    is_following = False
    friend_request = None
    is_friend = False
    request_sent = False
    request_received = False
    if request.user.is_authenticated:
        is_blocked = Block.objects.filter(blocker=profile.user, blocked=request.user).exists()
        is_following = Follow.objects.filter(follower=request.user, following=profile.user).exists()
        if request.user != profile.user:
            friend_request = _friend_request_between(request.user, profile.user)
            is_friend = bool(friend_request and friend_request.status == FriendRequest.Status.ACCEPTED)
            request_sent = bool(friend_request and friend_request.status == FriendRequest.Status.PENDING and friend_request.from_user_id == request.user.id)
            request_received = bool(friend_request and friend_request.status == FriendRequest.Status.PENDING and friend_request.to_user_id == request.user.id)

    if is_blocked:
        return render(request, "accounts/profile_unavailable.html", status=403)

    visible_posts = (
        base_visible_posts(request.user)
        .filter(author=profile.user)
        .prefetch_related("media", "poll__options")
        .order_by("-published_at", "-created_at")[:24]
    )
    media_posts = [post for post in visible_posts if post.post_type in {Post.PostType.PHOTO, Post.PostType.VIDEO, Post.PostType.REEL}]
    live_posts = [post for post in visible_posts if post.post_type == Post.PostType.LIVE]
    current_live = LiveSession.objects.filter(host=profile.user, status=LiveSession.Status.LIVE).order_by("-starts_at").first()
    upcoming_live = LiveSession.objects.filter(host=profile.user, status=LiveSession.Status.SCHEDULED).order_by("starts_at").first()
    joined_communities = list(
        CommunityMembership.objects.filter(user=profile.user, status=CommunityMembership.Status.ACTIVE)
        .select_related("community")
        .order_by("-created_at")[:6]
    )
    recent_followers = list(
        Follow.objects.filter(following=profile.user)
        .select_related("follower__profile")
        .order_by("-created_at")[:6]
    )
    following_preview = list(
        Follow.objects.filter(follower=profile.user)
        .select_related("following__profile")
        .order_by("-created_at")[:6]
    )
    related_creators = list(
        Profile.objects.exclude(pk=profile.pk)
        .filter(is_creator=True)
        .select_related("user")
        .order_by("-follower_count", "-post_count")[:6]
    )
    dating_profile = getattr(profile.user, "dating_profile", None)
    wallet = getattr(
        profile.user,
        "wallet",
        SimpleNamespace(available_balance=0, pending_balance=0, lifetime_earned=0),
    )
    dating_coin_balance = getattr(profile.user, "dating_coins", SimpleNamespace(balance=0))
    public_post_count = Post.objects.filter(author=profile.user, status=Post.Status.PUBLISHED).count()
    profile_views_count = (
        Post.objects.filter(author=profile.user, status=Post.Status.PUBLISHED).aggregate(total=Sum("view_count")).get("total")
        or 0
    )
    dating_views_count = dating_profile.views.count() if dating_profile else 0
    photo_posts = [post for post in visible_posts if post.post_type == Post.PostType.PHOTO]
    show_wallet_summary = any(
        getattr(wallet, field, 0) > 0
        for field in ("available_balance", "pending_balance", "lifetime_earned")
    )
    action_urls = {
        "edit_profile": _safe_reverse("profile_edit"),
        "upload_avatar": _safe_reverse("profile_edit"),
        "upload_cover": _safe_reverse("profile_edit"),
        "account_hub": _safe_reverse("user_dashboard"),
        "create_post": _safe_reverse("studio"),
        "go_live": _safe_reverse("live_start"),
        "dating_profile": _safe_reverse("dating_profile_edit") if request.user == profile.user else _safe_reverse("dating_profile_detail", username=profile.username),
        "pink_friday": _safe_reverse("pink_friday"),
        "live_shows": _safe_reverse("live_shows"),
        "wallet": _safe_reverse("wallet_home"),
        "messages": (
            _safe_reverse("user_dashboard")
            if request.user == profile.user
            else (_safe_reverse("messaging:start_chat", fallback="user_dashboard", user_id=profile.user.id) if is_friend else "")
        ),
        "games": _safe_reverse("games_home"),
        "about": _safe_reverse("profile_detail", username=profile.username),
        "friend_request": _safe_reverse("friend_request_send", username=profile.username),
        "friend_accept": _safe_reverse("friend_request_accept", request_id=getattr(friend_request, "id", 0)),
    }
    safe_username = profile.username or getattr(profile.user, "username", "") or "namvibe"
    safe_display_name = profile.display_name or safe_username or "Namvibe member"

    context = {
        "profile": profile,
        "safe_username": safe_username,
        "safe_display_name": safe_display_name,
        "is_following": is_following,
        "is_friend": is_friend,
        "request_sent": request_sent,
        "request_received": request_received,
        "can_edit": request.user.is_authenticated and request.user == profile.user,
        "profile_posts": visible_posts,
        "media_posts": media_posts,
        "photo_posts": photo_posts,
        "reel_posts": [post for post in visible_posts if post.post_type == Post.PostType.REEL],
        "live_posts": live_posts,
        "joined_communities": joined_communities,
        "current_live": current_live,
        "upcoming_live": upcoming_live,
        "active_membership": active_membership_for(profile.user),
        "public_post_count": public_post_count,
        "recent_followers": recent_followers,
        "following_preview": following_preview,
        "related_creators": related_creators,
        "dating_profile_visible": bool(dating_profile and dating_profile.is_visible),
        "dating_profile": dating_profile,
        "dating_views_count": dating_views_count,
        "wallet_summary": wallet,
        "show_wallet_summary": show_wallet_summary,
        "dating_coin_balance": dating_coin_balance,
        "profile_views_count": profile_views_count,
        "action_urls": action_urls,
        "joined_date": profile.user.date_joined,
}
    return render(request, "accounts/profile_detail.html", context)


def member_discovery_view(request):
    profiles = list(
        Profile.objects.select_related("user")
        .order_by("-is_verified", "-follower_count", "-post_count", "-created_at")[:30]
    )
    context = {
        "member_cards": _member_cards_for(request.user, profiles),
    }
    return render(request, "accounts/member_discovery.html", context)


@login_required(login_url="login")
def friends_list_view(request):
    accepted = FriendRequest.objects.filter(
        Q(from_user=request.user) | Q(to_user=request.user),
        status=FriendRequest.Status.ACCEPTED,
    ).select_related("from_user__profile", "to_user__profile").order_by("-updated_at")
    incoming = FriendRequest.objects.filter(
        to_user=request.user,
        status=FriendRequest.Status.PENDING,
    ).select_related("from_user__profile").order_by("-created_at")
    outgoing = FriendRequest.objects.filter(
        from_user=request.user,
        status=FriendRequest.Status.PENDING,
    ).select_related("to_user__profile").order_by("-created_at")
    friends = []
    for item in accepted:
        other_user = item.to_user if item.from_user_id == request.user.id else item.from_user
        friends.append(other_user.profile)
    context = {
        "friend_profiles": friends,
        "incoming_requests": incoming,
        "outgoing_requests": outgoing,
    }
    return render(request, "accounts/friends_list.html", context)


@login_required(login_url="login")
@require_http_methods(["POST"])
def send_friend_request_view(request, username):
    target_profile = get_object_or_404(Profile.objects.select_related("user"), username__iexact=username)
    target_user = target_profile.user
    if target_user == request.user:
        messages.error(request, "You cannot send a friend request to yourself.")
        return redirect("profile_detail", username=target_profile.username)
    if _users_are_friends(request.user, target_user):
        messages.info(request, "You are already friends.")
        return redirect("profile_detail", username=target_profile.username)
    friend_request = _friend_request_between(request.user, target_user)
    if friend_request and friend_request.status == FriendRequest.Status.PENDING:
        messages.info(request, "Friend request already pending.")
        return redirect("profile_detail", username=target_profile.username)
    if friend_request and friend_request.status in {FriendRequest.Status.DECLINED, FriendRequest.Status.CANCELED}:
        friend_request.status = FriendRequest.Status.PENDING
        friend_request.from_user = request.user
        friend_request.to_user = target_user
        friend_request.save(update_fields=["from_user", "to_user", "status", "updated_at"])
    else:
        FriendRequest.objects.create(from_user=request.user, to_user=target_user)
    messages.success(request, f"Friend request sent to @{target_profile.username}.")
    return redirect("profile_detail", username=target_profile.username)


@login_required(login_url="login")
@require_http_methods(["POST"])
def accept_friend_request_view(request, request_id):
    friend_request = get_object_or_404(
        FriendRequest.objects.select_related("from_user__profile", "to_user__profile"),
        pk=request_id,
        to_user=request.user,
        status=FriendRequest.Status.PENDING,
    )
    friend_request.status = FriendRequest.Status.ACCEPTED
    friend_request.save(update_fields=["status", "updated_at"])
    messages.success(request, f"You are now friends with @{friend_request.from_user.profile.username}.")
    return redirect("friends_list")


@login_required(login_url="login")
def account_gallery_view(request):
    profile = request.user.profile
    account_profile = getattr(request.user, "account_profile", None)
    user_posts = list(
        Post.objects.filter(author=request.user)
        .prefetch_related("media")
        .order_by("-published_at", "-created_at")[:20]
    )
    user_stories = list(StoryItem.objects.filter(author=request.user).order_by("-created_at")[:12])
    gallery_items = _gallery_items_for(profile, user_posts, user_stories)
    context = {
        **_account_shell_context(request, profile, account_profile),
        "gallery_items": gallery_items,
        "account_shell_title": "Gallery / Album",
        "account_shell_subtitle": "Photos, videos, reels, and stories",
    }
    return render(request, "accounts/profile_gallery.html", context)


@login_required(login_url="login")
def account_followers_view(request):
    profile = request.user.profile
    account_profile = getattr(request.user, "account_profile", None)
    followers = list(
        Follow.objects.filter(following=request.user)
        .select_related("follower__profile")
        .order_by("-created_at")[:24]
    )
    following = list(
        Follow.objects.filter(follower=request.user)
        .select_related("following__profile")
        .order_by("-created_at")[:24]
    )
    context = {
        **_account_shell_context(request, profile, account_profile),
        "followers": followers,
        "following": following,
        "account_shell_title": "Followers",
        "account_shell_subtitle": "People connected to your profile",
    }
    return render(request, "accounts/account_followers.html", context)


@login_required(login_url="login")
def account_privacy_view(request):
    profile = request.user.profile
    account_profile = getattr(request.user, "account_profile", None)
    context = {
        **_account_shell_context(request, profile, account_profile),
        "account_shell_title": "Privacy Settings",
        "account_shell_subtitle": "Current visibility and safe placeholders",
        "privacy_rows": [
            {
                "label": "Who can view profile",
                "value": "Approved followers only" if profile.is_private else "Public profile",
                "note": "Controlled by your profile privacy mode.",
            },
            {
                "label": "Who can message me",
                "value": "Members and matches",
                "note": "Granular message privacy can be added later without changing your routing.",
            },
            {
                "label": "Who can see my posts",
                "value": "Per-post audience controls",
                "note": "Photo, reel, story, and post privacy stay on each post flow.",
            },
        ],
    }
    return render(request, "accounts/account_privacy.html", context)


@login_required(login_url="login")
def account_security_view(request):
    profile = request.user.profile
    account_profile = getattr(request.user, "account_profile", None)
    context = {
        **_account_shell_context(request, profile, account_profile),
        "account_shell_title": "Security / PIN Reset",
        "account_shell_subtitle": "Safe placeholders only",
    }
    return render(request, "accounts/account_security.html", context)


@login_required(login_url="login")
def account_model_application_view(request):
    profile = request.user.profile
    account_profile = getattr(request.user, "account_profile", None)
    context = {
        **_account_shell_context(request, profile, account_profile),
        "account_shell_title": "Model / Streamer Application",
        "account_shell_subtitle": "Private foundation for future approval flows",
        "application_status": "Not started",
        "service_options": [
            "Live streaming",
            "Online friend chat",
            "Music / live rooms",
            "Game battles",
            "Pink Friday appearances",
            "Tour guide / walk with me service",
        ],
        "verification_requirements": [
            "Certified ID copy",
            "Live camera ID capture placeholder",
            "Admin approval before public listing",
            "Private review and status updates",
        ],
    }
    return render(request, "accounts/account_model_application.html", context)


@login_required(login_url="login")
def edit_profile_view(request):
    profile = request.user.profile
    account_profile = getattr(request.user, "account_profile", None)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
    requested_tab = request.GET.get("tab", "").strip().lower()
    if request.method == "POST" and form.is_valid():
        form.save()
        if account_profile:
            requested_country = (request.POST.get("current_country") or "").strip()
            if requested_country:
                account_profile.current_country = requested_country
            account_profile.profile_completed = True
            account_profile.save(update_fields=["current_country", "profile_completed", "updated_at"])
        messages.success(request, "Profile updated.")
        return redirect("user_dashboard")
    context = {
        **_account_shell_context(request, profile, account_profile),
        "form": form,
        "profile": profile,
        "account_profile": account_profile,
        "requested_tab": requested_tab,
        "current_country": getattr(account_profile, "current_country", "Namibia"),
        "account_shell_title": "Profile Settings",
        "account_shell_subtitle": "Identity, privacy, and image updates",
    }
    return render(request, "accounts/profile_edit.html", context)


@login_required(login_url="login")
@require_POST
def follow_toggle_view(request, username):
    target_profile = get_object_or_404(Profile.objects.select_related("user"), username__iexact=username)
    target_user = target_profile.user
    if target_user == request.user:
        messages.error(request, "You cannot follow yourself.")
        return redirect("profile_detail", username=target_profile.username)

    if Block.objects.filter(blocker__in=[request.user, target_user], blocked__in=[request.user, target_user]).exists():
        messages.error(request, "This profile is not available.")
        return redirect("profile_detail", username=target_profile.username)

    follow, created = Follow.objects.get_or_create(follower=request.user, following=target_user)
    if created:
        from .models import Notification, notify
        notify(
            recipient=target_user,
            notification_type=Notification.Type.FOLLOW,
            sender=request.user,
            message=f"@{request.user.username} started following you.",
            target_url=reverse("profile_detail", kwargs={"username": request.user.username}),
        )
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"status": "followed", "follower_count": target_profile.user.follower_edges.count()})
        messages.success(request, f"You are now following @{target_profile.username}.")
    else:
        follow.delete()
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"status": "unfollowed", "follower_count": target_profile.user.follower_edges.count()})
        messages.success(request, f"You unfollowed @{target_profile.username}.")
    return redirect("profile_detail", username=target_profile.username)


def profile_shortcut_view(request):
    return redirect("user_dashboard")

def account_profile_detail(request, username):
    return public_profile_view(request, username)

def follow_toggle(request, username):
    return follow_toggle_view(request, username)
