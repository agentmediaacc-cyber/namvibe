import os
import time

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from services.auth_service import (
    get_current_profile,
    get_current_user,
    get_oauth_url,
    handle_oauth_callback,
    check_account_availability,
    login_chain_user,
    logout_chain_user,
    refresh_chain_session,
    register_chain_user,
    set_current_user_password,
    send_password_reset,
    resend_confirmation_email,
    verify_recovery_token,
    update_password_from_recovery,
)
from services.rate_limit_service import limiter


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _is_production_env():
    if os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    return os.getenv("FLASK_ENV") == "production" or os.getenv("ENV") == "production"


def _register_rate_limit_exempt():
    return not _is_production_env() or os.getenv("CHAIN_FAST_LOCAL") == "1"


def _auth_rate_limit_key():
    return request.headers.get("X-Forwarded-For") or request.remote_addr


def _apply_registration_session(result):
    profile = result.get("profile") or {}
    auth_user_id = result.get("auth_user_id") or profile.get("auth_user_id")
    email = profile.get("email")
    if auth_user_id:
        session["auth_user_id"] = auth_user_id
        session["user_id"] = auth_user_id
    if email:
        session["auth_email"] = email
        session["email"] = email
    if profile.get("id"):
        session["profile_id"] = profile.get("id")
    if profile.get("username"):
        session["username"] = profile.get("username")
    if profile.get("full_name") or profile.get("display_name"):
        session["full_name"] = profile.get("full_name") or profile.get("display_name")
    
    if result.get("dev_fallback") and profile:
        session["dev_profile"] = profile
        session["dev_profile_fallback"] = True

    session["auth_provider"] = "password"
    session["login_at"] = int(time.time())
    session["age_check_required"] = False
    session["age_verified"] = bool(profile.get("date_of_birth"))
    if profile.get("date_of_birth"):
        session["date_of_birth"] = profile.get("date_of_birth")
        session["pending_date_of_birth"] = profile.get("date_of_birth")
    session.modified = True


def _log_registration_route_state(result, redirect_to=None):
    profile = result.get("profile") or {}
    print(
        "[auth.register] result",
        {
            "ok": bool(result.get("ok")),
            "auth_user_id_exists": bool(result.get("auth_user_id")),
            "profile_exists": bool(profile),
            "profile_id_exists": bool(profile.get("id")),
            "session_profile_id_exists": bool(session.get("profile_id")),
            "redirect_to": redirect_to,
        },
    )


def _age_from_date(date_of_birth):
    from datetime import datetime, timezone
    if not date_of_birth:
        return None
    try:
        dob = datetime.fromisoformat(str(date_of_birth)).date()
    except ValueError:
        return None
    today = datetime.now(timezone.utc).date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def _queue_oauth_error():
    session["oauth_error_message"] = "Google sign-in could not complete. Try email registration or check OAuth callback settings."


def _clear_oauth_error_state():
    session.pop("oauth_error_message", None)
    flashes = session.get("_flashes", [])
    if flashes:
        session["_flashes"] = [item for item in flashes if item[0] != "oauth_error"]
        if not session["_flashes"]:
            session.pop("_flashes", None)


def _should_show_oauth_error():
    if request.args.get("oauth_error"):
        return True
    if request.args.get("error"):
        return True
    if request.args.get("error_description"):
        return True
    if request.args.get("oauth") == "failed":
        return True
    return False


def _next_target(default="/profile/"):
    candidate = request.args.get("next") or session.get("auth_next") or default
    if not candidate.startswith("/"):
        return default
    return candidate


def _post_login_redirect(result):
    target = result if isinstance(result, str) and result.startswith("/") else "/profile/"
    if target == "/profile/":
        requested = session.pop("auth_next", None)
        if requested and requested.startswith("/"):
            return requested
    session.pop("auth_next", None)
    return target


def _existing_session_redirect():
    user = get_current_user()
    if not user:
        return None
    profile = get_current_profile()
    if not profile:
        return "/profile/onboarding"
    if profile.get("profile_completed"):
        return "/profile/"
    return "/profile/onboarding"


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10/minute", key_func=lambda: request.headers.get("X-Forwarded-For") or request.remote_addr)
def login():
    existing_target = _existing_session_redirect()
    if request.method == "GET" and existing_target:
        return redirect(existing_target)
    error = None
    oauth_error = None
    success_message = None
    
    # Handle success/status messages
    if request.args.get("password_reset") == "1":
        success_message = "Password updated. You can now log in."
    elif request.args.get("registered") == "1":
        success_message = "Account created. Check your email to confirm your account."
    elif request.args.get("oauth_error") == "1":
        oauth_error = "Google sign-in could not complete. Try email registration or check OAuth callback settings."

    if request.method == "POST":
        raw_login_id = (
            request.form.get("login_id")
            or request.form.get("username")
            or request.form.get("email")
            or request.form.get("identifier")
            or request.form.get("login")
            or ""
        )
        raw_password = (
            request.form.get("password")
            or request.form.get("user_password")
            or ""
        )
        ok, result = login_chain_user(raw_login_id, raw_password)
        if ok:
            return redirect(_post_login_redirect(result))
        
        if "invalid" in result.lower() or "not confirmed" in result.lower() or "incorrect" in result.lower():
            error = {
                "message": result,
                "actions": True,
                "email": raw_login_id if "@" in (raw_login_id or "") else None
            }
        else:
            error = result
            
    if request.args.get("next"):
        session["auth_next"] = request.args.get("next")
        
    if request.method == "GET":
        if not oauth_error and _should_show_oauth_error():
            oauth_error = session.pop("oauth_error_message", None) or "Google sign-in could not complete. Try email registration or check OAuth callback settings."
        else:
            _clear_oauth_error_state()
            
    return render_template("auth/login.html", 
                           error=error, 
                           oauth_error=oauth_error, 
                           success_message=success_message,
                           next_path=session.get("auth_next"))


@auth_bp.route("/register", methods=["GET"])
@limiter.exempt
def register():
    existing_target = _existing_session_redirect()
    if existing_target:
        return redirect(existing_target)
    return render_template("auth/register.html", error=None, form=None)


@auth_bp.route("/register", methods=["POST"])
@limiter.limit(
    "5/hour",
    key_func=_auth_rate_limit_key,
    methods=["POST"],
    exempt_when=_register_rate_limit_exempt,
)
def register_post():
    error = None
    password = request.form.get("password") or ""
    confirm_password = request.form.get("confirm_password") or ""
    required_fields = {
        "full_name": "Full name is required.",
        "email": "Email is required.",
        "phone": "Phone number is required.",
        "username": "Username is required.",
        "country_origin": "Country of origin is required.",
        "current_country": "Current country is required.",
        "region": "Region, state, or province is required.",
        "town": "Town or city is required.",
        "password": "Password is required.",
        "confirm_password": "Confirm your password.",
    }
    for field, message in required_fields.items():
        if not (request.form.get(field) or "").strip():
            return render_template("auth/register.html", error=message, form=request.form)
    if password != confirm_password:
        error = "Passwords do not match."
        return render_template("auth/register.html", error=error, form=request.form)
    agreement_fields = (
        "agreement_true_details",
        "agreement_identity_use",
        "agreement_username_privacy",
        "agreement_standards",
        "agreement_no_abuse",
        "terms",
    )
    if not all(request.form.get(field) for field in agreement_fields):
        error = "You must accept all account agreements before creating your CHAIN account."
        return render_template("auth/register.html", error=error, form=request.form)
    result = register_chain_user(
        request.form.get("email"),
        request.form.get("password"),
        request.form.get("username"),
        request.form.get("full_name"),
        extra={
            "phone": request.form.get("phone"),
            "phone_code": request.form.get("phone_code"),
            "date_of_birth": request.form.get("date_of_birth"),
            "residential_address": request.form.get("residential_address"),
            "country_origin": request.form.get("country_origin") or request.form.get("country"),
            "current_country": request.form.get("current_country"),
            "country": request.form.get("current_country") or request.form.get("country") or request.form.get("country_origin"),
            "preferred_language": request.form.get("preferred_language"),
            "current_location": request.form.get("town") or request.form.get("current_location"),
            "town": request.form.get("town"),
            "region": request.form.get("region"),
            "interests": [item.strip() for item in (request.form.get("interests") or "").split(",") if item.strip()],
            "activities": [item.strip() for item in (request.form.get("activities") or "").split(",") if item.strip()],
            "looking_for": request.form.getlist("looking_for") or [item.strip() for item in (request.form.get("looking_for") or "").split(",") if item.strip()],
            "profile_type": request.form.get("profile_type"),
            "creator_mode_enabled": request.form.get("creator_mode_enabled"),
            "seller_mode_enabled": request.form.get("seller_mode_enabled") or request.form.get("business_mode_enabled"),
            "dating_mode_enabled": request.form.get("dating_mode_enabled"),
            "premium_mode_enabled": request.form.get("premium_mode_enabled"),
            "terms_accepted": request.form.get("terms"),
            "human_confirmed": request.form.get("human_confirmed"),
            "agreement_true_details": request.form.get("agreement_true_details"),
            "agreement_identity_use": request.form.get("agreement_identity_use"),
            "agreement_username_privacy": request.form.get("agreement_username_privacy"),
            "agreement_standards": request.form.get("agreement_standards"),
            "agreement_no_abuse": request.form.get("agreement_no_abuse"),
        },
    )
    if result.get("ok"):
        _apply_registration_session(result)
        redirect_to = result.get("redirect_to") or "/profile/"
        _log_registration_route_state(result, redirect_to=redirect_to)
        if result.get("dev_fallback"):
            flash("Email verification is pending. You can continue testing your profile.", "info")
        return redirect(redirect_to)

    if result.get("error") == "EMAIL_EXISTS":
        error = {
            "message": "This email already has a CHAIN account.",
            "email": request.form.get("email"),
            "exists": True
        }
    else:
        error = result.get("error") or "Registration failed. Please try again."
    return render_template("auth/register.html", error=error, form=request.form)


@auth_bp.route("/resend-confirmation", methods=["POST"])
def resend_confirmation():
    email = request.form.get("email")
    if not email:
        return redirect(url_for("auth.login"))
    ok, result = resend_confirmation_email(email)
    return redirect(url_for("auth.login", message=result))


@auth_bp.route("/onboarding/preferences", methods=["GET", "POST"])
def onboarding_preferences():
    if not session.get("auth_user_id"):
        return redirect(url_for("auth.login", next=request.path))
    profile = get_current_profile()
    if request.method == "POST":
        session["onboarding_preferences"] = dict(request.form)
        return redirect(url_for("auth.onboarding_profile"))
    return render_template("profile/onboarding.html", profile=profile, form=profile or {}, progress=(profile or {}).get("profile_completion", 0), setup_mode=True)


@auth_bp.route("/onboarding/profile", methods=["GET", "POST"])
def onboarding_profile():
    if not session.get("auth_user_id"):
        return redirect(url_for("auth.login", next=request.path))
    profile = get_current_profile()
    if request.method == "POST":
        session["onboarding_profile"] = dict(request.form)
        return redirect(url_for("auth.onboarding_tour"))
    return render_template("profile/edit.html", profile=profile or {}, form=profile or {}, setup_mode=True, progress=(profile or {}).get("profile_completion", 0))


@auth_bp.route("/onboarding/tour", methods=["GET", "POST"])
def onboarding_tour():
    if not session.get("auth_user_id"):
        return redirect(url_for("auth.login", next=request.path))
    if request.method == "POST":
        return redirect("/profile/")
    return render_template("auth/profile_error.html", error_detail="Welcome tour is ready. Start exploring CHAIN or skip for now.")


@auth_bp.route("/check-availability")
@limiter.limit(
    "180/minute",
    key_func=_auth_rate_limit_key,
    exempt_when=_register_rate_limit_exempt,
)
def check_availability():
    field = request.args.get("field")
    value = request.args.get("value")
    town = request.args.get("town")
    return jsonify(check_account_availability(field, value, town=town))


@auth_bp.route("/google")
def google_login():
    session["oauth_mode"] = request.args.get("mode", "login")
    session["auth_provider"] = "google"
    session["auth_next"] = _next_target()
    url = get_oauth_url("google")
    if url:
        return redirect(url)
    _queue_oauth_error()
    return redirect(url_for("auth.login", oauth_error=1))


@auth_bp.route("/facebook")
def facebook_login():
    session["oauth_mode"] = request.args.get("mode", "login")
    session["auth_provider"] = "facebook"
    session["auth_next"] = _next_target()
    url = get_oauth_url("facebook")
    if url:
        return redirect(url)
    _queue_oauth_error()
    return redirect(url_for("auth.login", oauth_error=1))


@auth_bp.route("/callback")
@auth_bp.route("/google/callback")
@auth_bp.route("/facebook/callback")
def oauth_callback():
    """
    Unified callback handler for Supabase redirects.
    Handles OAuth codes and recovery tokens.
    """
    # 1. Check for recovery/password reset
    if request.args.get("type") == "recovery" or (request.args.get("code") and not session.get("auth_provider")):
        # If we have a code but no provider, it's likely a recovery flow
        # Redirect to reset-password with the query params
        return redirect(url_for("auth.reset_password", **request.args))

    # 2. Check for OAuth errors
    if request.args.get("error") or request.args.get("error_description"):
        session["oauth_error_message"] = request.args.get("error_description") or "Auth failed."
        return redirect(url_for("auth.login", oauth_error=1))

    # 3. Handle Provider Callbacks
    provider = session.get("auth_provider")
    if not provider and "/google/" in request.path:
        provider = "google"
    elif not provider and "/facebook/" in request.path:
        provider = "facebook"
    
    if not provider:
        # If no provider in session or path, check if it's a generic callback
        # that might have tokens in hash (handled by JS on the target page)
        return redirect(url_for("auth.reset_password"))

    mode = session.pop("oauth_mode", "login")
    if not request.args.get("code"):
        print(f"[auth.oauth_callback] {provider} callback missing code: {dict(request.args)}")
        session["oauth_error_message"] = "Google sign-in could not complete. Try email registration or check OAuth callback settings."
        return redirect(url_for("auth.login", oauth_error=1))
    
    ok, result = handle_oauth_callback(provider, request.args, mode=mode)
    if ok:
        session["auth_provider"] = provider
        return redirect(_post_login_redirect(result))
    
    if result == "OAUTH_SIGNUP_REQUIRED":
        return redirect(url_for("auth.register", oauth_signup_required=1))
        
    session["oauth_error_message"] = result
    return redirect(url_for("auth.login", oauth_error=1))


@auth_bp.route("/oauth-diagnostics")
def oauth_diagnostics():
    """
    Diagnostic page for OAuth configuration.
    """
    base = request.host_url.rstrip("/")
    supabase_url = "https://kcxphxihykonzuagtgke.supabase.co"
    
    data = {
        "site_url": base,
        "redirect_urls": [
            f"{base}/auth/callback",
            f"{base}/auth/google/callback",
            f"{base}/auth/facebook/callback",
            "http://127.0.0.1:5000/auth/callback",
            "http://localhost:5000/auth/callback"
        ],
        "google_redirect": f"{supabase_url}/auth/v1/callback",
        "facebook_redirect": f"{supabase_url}/auth/v1/callback"
    }
    return render_template("auth/oauth_diagnostics.html", **data)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    error = None
    success = None
    if request.method == "POST":
        ok, result = send_password_reset(request.form.get("email", ""))
        if ok:
            success = result
        else:
            error = result
    return render_template("auth/forgot_password.html", error=error, success=success)


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    error = None
    success = None

    # Check for recovery params arriving from callback (GET)
    if request.method == "GET" and (request.args.get("code") or request.args.get("token_hash")):
        ok, result = verify_recovery_token(request.args)
        if not ok:
            error = result
        else:
            # Token verified, recovery session established
            pass

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # 1. Capture tokens from the form (submitted via JS from URL hash if it was a hash callback)
        access_token = request.form.get("access_token")
        refresh_token = request.form.get("refresh_token")

        if access_token:
            # Establish session from tokens before updating
            from services.session_service import store_auth_session
            from services.auth_service import get_supabase, sync_oauth_profile
            try:
                client = get_supabase()
                client.auth.set_session(access_token, refresh_token or "")
                user_res = client.auth.get_user(access_token)
                user = getattr(user_res, "user", None)
                if user:
                    profile = sync_oauth_profile(user, "recovery")
                    store_auth_session(None, user, profile, provider="recovery")
                    # Manually ensure tokens are in session
                    session["access_token"] = access_token
                    session["refresh_token"] = refresh_token
            except Exception as e:
                print(f"[auth.reset_password] session setup from tokens failed: {e}")

        # 2. Validate password
        if len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm_password:
            error = "Passwords do not match."
        else:
            # 3. Update password in Supabase and local DB
            ok, result = update_password_from_recovery(password)
            if ok:
                # Successfully reset. Log them out of the recovery session so they can re-login properly.
                from services.auth_service import logout_chain_user
                logout_chain_user()
                return redirect(url_for("auth.login", password_reset_success=1))
            else:
                error = result

    return render_template("auth/reset_password.html", error=error, success=success)

@auth_bp.route("/logout")
def logout():
    logout_chain_user()
    return redirect("/")


@auth_bp.route("/me")
def me():
    user = get_current_user()
    profile = get_current_profile()
    if not user:
        refresh_chain_session()
        user = get_current_user()
        profile = get_current_profile()
    if not user:
        return {"error": "Unauthorized"}, 401
    return {
        "auth_user_id": getattr(user, "id", None),
        "email": getattr(user, "email", None),
        "username": (profile or {}).get("username"),
        "profile_id": (profile or {}).get("id"),
    }
