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
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import LoginForm, ProfileForm, SignupForm
from .models import AccountProfile, Block, Follow, Profile
from .supabase import (
    ensure_supabase_profile,
    find_supabase_profile,
    get_supabase_profile,
    sign_in_supabase_auth,
    supabase_profile_id_for_user,
)
from messaging.services import messaging_dashboard_context
from posts.models import Post
from posts.services import base_visible_posts
from posts.supabase_posts import get_posts_by_user
from live.models import LiveSession
from wallet.services import active_membership_for

logger = logging.getLogger(__name__)


def _profile_redirect_url(request):
    redirect_to = request.POST.get("next") or request.GET.get("next") or reverse("user_dashboard")
    if url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to
    return reverse("user_dashboard")


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
            "display_name": user.get_full_name() or user.username,
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


def _user_from_supabase_login(identifier, password, auth_payload, profile_payload):
    auth_user = auth_payload.get("user") or {}
    email = (auth_user.get("email") or identifier).lower()
    full_name = (
        (profile_payload or {}).get("full_name")
        or (auth_user.get("user_metadata") or {}).get("full_name")
        or email.split("@")[0]
    )
    username = (profile_payload or {}).get("username") or (auth_user.get("user_metadata") or {}).get("username") or email.split("@")[0]

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
    Profile.objects.filter(user=user).update(username=profile_username, display_name=full_name or user.profile.display_name)

    phone = (profile_payload or {}).get("phone") or ""
    if phone and not hasattr(user, "account_profile"):
        AccountProfile.objects.get_or_create(
            user=user,
            defaults={
                "full_name": full_name,
                "email": email,
                "cellphone_number": phone,
                "residential_address": "",
                "country_of_origin": "",
                "current_country": "",
            },
        )
    return user


def login_view(request):
    if request.user.is_authenticated:
        _set_account_session(request, request.user)
        return redirect("user_dashboard")

    form = LoginForm(request.POST or None)
    clean_login_error = None

    if request.method == "POST":
        if form.is_valid():
            user = form.cleaned_data["user"]
            _ensure_auth_profile(user)
            ensure_supabase_profile(user)
            django_login(request, user)
            _set_account_session(request, user)
            return redirect(_profile_redirect_url(request))
        identifier = request.POST.get("identifier", "").strip().lower()
        password = request.POST.get("password", "")
        if "@" in identifier and password:
            supabase_profile = find_supabase_profile(email=identifier)
            auth_payload, auth_error = sign_in_supabase_auth(identifier, password)
            if auth_payload:
                user = _user_from_supabase_login(identifier, password, auth_payload, supabase_profile)
                ensure_supabase_profile(user)
                django_login(request, user)
                _set_account_session(request, user)
                return redirect(_profile_redirect_url(request))
            if supabase_profile and auth_error != "not_configured":
                clean_login_error = "Incorrect password."

    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": _profile_redirect_url(request), "clean_login_error": clean_login_error},
    )


def logout_view(request):
    django_logout(request)
    request.session.flush()
    return redirect("login")


def signup_view(request):
    if request.user.is_authenticated:
        _set_account_session(request, request.user)
        return redirect("user_dashboard")

    form = SignupForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        existing_supabase_profile = find_supabase_profile(
            email=form.cleaned_data["email"],
            username=form.cleaned_data["username"],
            phone=form.cleaned_data["cellphone_number"],
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
                    cellphone_number=form.cleaned_data["cellphone_number"],
                    residential_address=form.cleaned_data["residential_address"],
                    country_of_origin=form.cleaned_data["country_of_origin"],
                    current_country=form.cleaned_data["current_country"],
                )
        except IntegrityError:
            messages.error(
                request,
                "An account with those details already exists. Check username, email, and cellphone number.",
            )
        else:
            _ensure_auth_profile(user)
            ensure_supabase_profile(user)
            django_login(request, user)
            _set_account_session(request, user)
            return redirect("user_dashboard")

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


def profile_completion_view(request):
    if not request.user.is_authenticated:
        return redirect(_login_url_with_next("profile_completion"))

    _set_account_session(request, request.user)

    profile = None
    if request.user.is_authenticated:
        profile = getattr(request.user, "account_profile", None)

    return render(request, "accounts/profile_completion.html", {"profile": profile})


def user_dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect(_login_url_with_next("user_dashboard"))

    _set_account_session(request, request.user)
    _ensure_auth_profile(request.user)
    supabase_profile = ensure_supabase_profile(request.user) or get_supabase_profile(request.user)

    posts = []
    try:
        posts = get_posts_by_user(request.session.get("eharo_user_id"))
        if not posts:
            posts = get_posts_by_user(str(supabase_profile_id_for_user(request.user)))
    except Exception as e:
        print("LOAD POSTS ERROR:", e)

    profile = request.user.profile
    wallet = getattr(request.user, "wallet", None)
    account_profile = getattr(request.user, "account_profile", None)
    full_name = (
        (supabase_profile or {}).get("full_name")
        or getattr(account_profile, "full_name", "")
        or profile.display_name
        or request.user.get_full_name()
        or request.user.username
    )
    username = (supabase_profile or {}).get("username") or profile.username or request.user.username
    email = (supabase_profile or {}).get("email") or getattr(account_profile, "email", "") or request.user.email
    post_count = max(profile.post_count, len(posts))

    context = {
        "full_name": full_name,
        "username": username,
        "email": email,
        "profile": profile,
        "supabase_profile": supabase_profile,
        "account_profile": account_profile,
        "user_posts": posts,
        "post_count": post_count,
        "wallet_balance": getattr(wallet, "available_balance", 0),
        **messaging_dashboard_context(request.user, request.GET.get("conversation")),
    }
    return render(request, "accounts/dashboard.html", context)


def public_profile_view(request, username):
    profile = get_object_or_404(
        Profile.objects.select_related("user"),
        username__iexact=username,
    )
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

    context = {
        "profile": profile,
        "is_following": is_following,
        "can_edit": request.user.is_authenticated and request.user == profile.user,
        "profile_posts": visible_posts,
        "media_posts": media_posts,
        "live_posts": live_posts,
        "current_live": current_live,
        "upcoming_live": upcoming_live,
        "active_membership": active_membership_for(profile.user),
    }
    return render(request, "accounts/profile_detail.html", context)


@login_required(login_url="login")
def edit_profile_view(request):
    profile = request.user.profile
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("profile_detail", username=profile.username)
    return render(request, "accounts/profile_edit.html", {"form": form, "profile": profile})


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
