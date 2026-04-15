from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import SignupForm
from posts.supabase_posts import get_posts_by_user
from .supabase_auth import (
    signup_user,
    login_user,
    get_profile_by_user_id,
    username_exists,
    email_exists,
    phone_exists,
)

def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")

        if not email or not password:
            messages.error(request, "Enter your email and password.")
            return render(request, "accounts/login.html", {"entered_email": email})

        auth_resp = login_user(email=email, password=password)

        if not auth_resp.ok:
            print("LOGIN ERROR:", auth_resp.status_code, auth_resp.text)
            messages.error(request, "Invalid login details or account not confirmed.")
            return render(request, "accounts/login.html", {"entered_email": email})

        auth_data = auth_resp.json()
        user = auth_data.get("user") or {}
        user_id = user.get("id")

        if not user_id:
            messages.error(request, "Login failed. No user id returned.")
            return render(request, "accounts/login.html", {"entered_email": email})

        profile_resp = get_profile_by_user_id(user_id)
        full_name = user.get("user_metadata", {}).get("full_name", "")
        username = user.get("user_metadata", {}).get("username", "")

        if profile_resp.ok:
            rows = profile_resp.json()
            if rows:
                row = rows[0]
                full_name = row.get("full_name") or full_name
                username = row.get("username") or username
                email = row.get("email") or email

        request.session["eharo_user_id"] = user_id
        request.session["eharo_full_name"] = full_name or "Eharo User"
        request.session["eharo_username"] = username or "user"
        request.session["eharo_email"] = email
        request.session["eharo_access_token"] = auth_data.get("access_token", "")
        request.session["eharo_refresh_token"] = auth_data.get("refresh_token", "")

        return redirect("user_dashboard")

    return render(request, "accounts/login.html")

def logout_view(request):
    request.session.flush()
    return redirect("login")

def signup_view(request):
    form = SignupForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        full_name = form.cleaned_data["full_name"].strip()
        username = form.cleaned_data["username"].strip().lower()
        email = form.cleaned_data["email"].strip().lower()
        phone = form.cleaned_data["phone"].strip()
        password = form.cleaned_data["password"]

        has_error = False

        if username_exists(username):
            form.add_error("username", "Username already used.")
            has_error = True

        if email_exists(email):
            form.add_error("email", "Email already used.")
            has_error = True

        if phone_exists(phone):
            form.add_error("phone", "Phone number already used.")
            has_error = True

        if not has_error:
            auth_resp = signup_user(
                email=email,
                password=password,
                full_name=full_name,
                username=username,
                phone=phone,
            )

            if not auth_resp.ok:
                print("AUTH SIGNUP ERROR:", auth_resp.status_code, auth_resp.text)
                messages.error(request, f"Signup failed: {auth_resp.text}")
            else:
                auth_data = auth_resp.json()
                user_data = auth_data.get("user") or {}
                user_id = user_data.get("id")

                if not user_id:
                    messages.error(request, "User created but user id was not returned.")
                else:
                    request.session["eharo_user_id"] = user_id
                    request.session["eharo_full_name"] = full_name
                    request.session["eharo_username"] = username
                    request.session["eharo_email"] = email
                    return redirect("user_dashboard")

    return render(request, "accounts/signup.html", {"form": form})

def forgot_password_view(request):
    return render(request, "accounts/forgot_password.html")

def user_dashboard_view(request):
    if not request.session.get("eharo_user_id"):
        return redirect("login")

    posts = []
    try:
        resp = get_posts_by_user(request.session.get("eharo_user_id"))
        if resp.ok:
            posts = resp.json()
    except Exception as e:
        print("LOAD POSTS ERROR:", e)

    context = {
        "full_name": request.session.get("eharo_full_name", ""),
        "username": request.session.get("eharo_username", ""),
        "email": request.session.get("eharo_email", ""),
        "user_posts": posts,
    }
    return render(request, "accounts/dashboard.html", context)
