from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login as django_login, logout as django_logout
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import LoginForm, SignupForm
from .models import AccountProfile
from messaging.services import messaging_dashboard_context
from posts.supabase_posts import get_posts_by_user


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


def login_view(request):
    if request.user.is_authenticated:
        _set_account_session(request, request.user)
        return redirect("user_dashboard")

    form = LoginForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.cleaned_data["user"]
            django_login(request, user)
            _set_account_session(request, user)
            return redirect(_profile_redirect_url(request))
        messages.error(request, "Check your login details and try again.")

    return render(request, "accounts/login.html", {"form": form, "next": _profile_redirect_url(request)})


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
            django_login(request, user)
            _set_account_session(request, user)
            return redirect("profile_completion")

    return render(request, "accounts/signup.html", {"form": form})


def forgot_password_view(request):
    return render(request, "accounts/forgot_password.html")


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

    posts = []
    try:
        posts = get_posts_by_user(request.session.get("eharo_user_id"))
    except Exception as e:
        print("LOAD POSTS ERROR:", e)

    context = {
        "full_name": request.session.get("eharo_full_name", ""),
        "username": request.session.get("eharo_username", ""),
        "email": request.session.get("eharo_email", ""),
        "user_posts": posts,
        **messaging_dashboard_context(request.user, request.GET.get("conversation")),
    }
    return render(request, "accounts/dashboard.html", context)
