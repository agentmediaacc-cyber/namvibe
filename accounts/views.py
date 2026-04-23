from urllib.parse import urlencode
import logging

from django.contrib import messages
from django.contrib.auth import login as django_login, logout as django_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from live.models import LiveSession
from messaging.services import messaging_dashboard_context
from posts.models import Post
from posts.services import base_visible_posts
from posts.supabase_posts import get_posts_by_user
from wallet.services import active_membership_for, ensure_wallet
from communities.models import CommunityMembership

from .forms import LoginForm, ProfileForm, SignupForm
from .models import AccountProfile, Block, Follow, Profile
from .services import (
    ensure_account_role,
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
        _set_account_session(request, request.user)
        ensure_account_role(request.user)
        if is_master_admin(request.user):
            return redirect(master_admin_dashboard_url())
        return redirect("user_dashboard")

    form = LoginForm(request.POST or None)
    clean_login_error = None

    if request.method == "POST":
        if form.is_valid():
            user = form.cleaned_data["user"]
            _ensure_auth_profile(user)
            ensure_supabase_profile(user)
            ensure_account_role(user)
            django_login(request, user)
            if form.cleaned_data.get("remember_me"):
                request.session.set_expiry(60 * 60 * 24 * 30)
            else:
                request.session.set_expiry(0)
            _set_account_session(request, user)
            if is_master_admin(user):
                repair_master_admin_user(user, supabase_uid=getattr(getattr(user, "account_role", None), "supabase_uid", ""), email=user.email)
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
                ensure_supabase_profile(user)
                django_login(request, user)
                if request.POST.get("remember_me"):
                    request.session.set_expiry(60 * 60 * 24 * 30)
                else:
                    request.session.set_expiry(0)
                _set_account_session(request, user)
                if is_master_admin(user):
                    repair_master_admin_user(user, supabase_uid=auth_payload.get("user", {}).get("id", ""), email=user.email)
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
        _set_account_session(request, request.user)
        ensure_account_role(request.user)
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
        except IntegrityError:
            messages.error(
                request,
                "An account with those details already exists. Check username, email, and cellphone number.",
            )
        else:
            _ensure_auth_profile(user)
            ensure_supabase_profile(user)
            ensure_account_role(user)
            django_login(request, user)
            request.session.set_expiry(60 * 60 * 24 * 14)
            _set_account_session(request, user)
            sent, note = send_verification_email(request, user)
            if note:
                if sent:
                    messages.success(request, note)
                else:
                    messages.info(request, note)
            messages.success(request, "Your account is ready. Finish the quick setup to unlock your best Namvibe experience.")
            return redirect("profile_completion")

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

    ensure_account_role(request.user)
    if is_master_admin(request.user):
        repair_master_admin_user(request.user, supabase_uid=getattr(getattr(request.user, "account_role", None), "supabase_uid", ""), email=request.user.email)
        return redirect(master_admin_dashboard_url())
    _set_account_session(request, request.user)
    account_profile = getattr(request.user, "account_profile", None)
    onboarding_items, onboarding_progress = onboarding_items_for(request.user)
    if request.method == "POST":
        account_profile.profile_completed = True
        account_profile.save(update_fields=["profile_completed", "updated_at"])
        messages.success(request, "Your onboarding shell is ready.")
        return redirect("user_dashboard")

    return render(
        request,
        "accounts/profile_completion.html",
        {
            "profile": account_profile,
            "onboarding_items": onboarding_items,
            "onboarding_progress": onboarding_progress,
            "active_membership": active_membership_for(request.user),
        },
    )


def user_dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect(_login_url_with_next("user_dashboard"))

    _set_account_session(request, request.user)
    _ensure_auth_profile(request.user)
    account_role = ensure_account_role(request.user)
    if is_master_admin(request.user, role=account_role):
        repair_master_admin_user(
            request.user,
            supabase_uid=getattr(account_role, "supabase_uid", ""),
            email=request.user.email,
        )
        return redirect(master_admin_dashboard_url())
    supabase_profile = ensure_supabase_profile(request.user) or get_supabase_profile(request.user)

    posts = []
    try:
        posts = get_posts_by_user(request.session.get("eharo_user_id"))
        if not posts:
            posts = get_posts_by_user(str(supabase_profile_id_for_user(request.user)))
    except Exception as exc:
        logger.warning("LOAD POSTS ERROR: %s", exc)

    profile = request.user.profile
    account_profile = getattr(request.user, "account_profile", None)
    full_name = (
        (supabase_profile or {}).get("full_name")
        or getattr(account_profile, "full_name", "")
        or request.user.get_full_name()
        or request.user.username
    )
    username = (supabase_profile or {}).get("username") or profile.username or request.user.username
    email = (supabase_profile or {}).get("email") or getattr(account_profile, "email", "") or request.user.email
    post_count = max(profile.post_count, len(posts))
    dashboard_metrics = _dashboard_metrics(request.user)

    active_panel = request.GET.get("section") or ("messages" if request.GET.get("conversation") else "overview")
    if active_panel not in {"overview", "profile", "posts", "messages", "wallet", "support"}:
        active_panel = "overview"

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

    context = {
        "full_name": full_name,
        "username": username,
        "email": email,
        "profile": profile,
        "supabase_profile": supabase_profile,
        "account_profile": account_profile,
        "user_posts": posts,
        "post_count": post_count,
        "account_role": account_role,
        "draft_posts": Post.objects.filter(author=request.user, status=Post.Status.DRAFT).prefetch_related("media")[:8],
        "saved_post_count": request.user.post_saves.count(),
        "community_count": CommunityMembership.objects.filter(user=request.user, status=CommunityMembership.Status.ACTIVE).count(),
        "active_panel": active_panel,
        "following_preview": following_preview,
        "follower_preview": follower_preview,
        **dashboard_metrics,
        **messaging_dashboard_context(request.user, request.GET.get("conversation")),
    }
    return render(request, "accounts/dashboard.html", context)


def public_profile_view(request, username):
    profile = get_object_or_404(Profile.objects.select_related("user"), username__iexact=username)
    is_blocked = False
    is_following = False
    if request.user.is_authenticated:
        is_blocked = Block.objects.filter(blocker=profile.user, blocked=request.user).exists()
        is_following = Follow.objects.filter(follower=request.user, following=profile.user).exists()

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

    context = {
        "profile": profile,
        "is_following": is_following,
        "can_edit": request.user.is_authenticated and request.user == profile.user,
        "profile_posts": visible_posts,
        "media_posts": media_posts,
        "reel_posts": [post for post in visible_posts if post.post_type == Post.PostType.REEL],
        "live_posts": live_posts,
        "joined_communities": joined_communities,
        "current_live": current_live,
        "upcoming_live": upcoming_live,
        "active_membership": active_membership_for(profile.user),
        "recent_followers": recent_followers,
        "following_preview": following_preview,
        "related_creators": related_creators,
        "dating_profile_visible": bool(dating_profile and dating_profile.is_visible),
    }
    return render(request, "accounts/profile_detail.html", context)


@login_required(login_url="login")
def edit_profile_view(request):
    profile = request.user.profile
    account_profile = getattr(request.user, "account_profile", None)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        if account_profile:
            account_profile.profile_completed = True
            account_profile.save(update_fields=["profile_completed", "updated_at"])
        messages.success(request, "Profile updated.")
        return redirect("profile_detail", username=profile.username)
    return render(request, "accounts/profile_edit.html", {"form": form, "profile": profile, "account_profile": account_profile})


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
        messages.success(request, f"You are now following @{target_profile.username}.")
    else:
        follow.delete()
        messages.success(request, f"You unfollowed @{target_profile.username}.")
    return redirect("profile_detail", username=target_profile.username)
