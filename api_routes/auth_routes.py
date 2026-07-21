import os
import re
import time

from flask import Blueprint, abort, current_app, flash, jsonify, make_response, redirect, render_template, request, session, url_for

from engines.performance_engine import clean_email, normalize_username
from services.auth_service import (
    get_current_profile,
    get_current_user,
    get_supabase_auth_configuration_status,
    get_oauth_url,
    handle_oauth_callback,
    check_account_availability,
    login_chain_user,
    logout_chain_user,
    refresh_chain_session,
    register_chain_user,
    normalize_phone,
    set_current_user_password,
    send_password_reset,
    resend_confirmation_email,
    username_suggestions,
    verify_recovery_token,
    update_password_from_recovery,
)
from services.logging_service import log_warning
from services.rate_limit_service import limiter
from services.session_service import establish_login_session


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _is_production_env():
    if os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    return os.getenv("FLASK_ENV") == "production" or os.getenv("ENV") == "production"


def _register_rate_limit_exempt():
    return not _is_production_env() or os.getenv("CHAIN_FAST_LOCAL") == "1"


def _auth_rate_limit_key():
    return request.headers.get("X-Forwarded-For") or request.remote_addr


def _email_valid(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", (email or "").strip()))


def _availability(field, value, town=None):
    try:
        result = check_account_availability(field, value, town=town)
        result["ok"] = True
        return result
    except Exception as error:
        print(f"[auth.availability] {field} check failed: {error}")
        return {
            "ok": False,
            "available": False,
            "field": field,
            "message": "Availability check is temporarily unavailable. Please try again.",
            "suggestions": [],
        }


def _fast_api_availability(field, value, town=None):
    raw_value = (value or "").strip()
    if not raw_value:
        return {
            "ok": True,
            "available": False,
            "field": field,
            "message": "Enter a value first.",
            "suggestions": [],
        }
    if field == "email":
        normalized = clean_email(raw_value)
        if not _email_valid(normalized):
            return {
                "ok": True,
                "available": False,
                "field": field,
                "message": "Enter a valid email address.",
                "suggestions": [],
            }
    elif field == "username":
        normalized = normalize_username(raw_value)
        if not re.fullmatch(r"[a-z0-9_]{3,30}", normalized or ""):
            return {
                "ok": True,
                "available": False,
                "field": field,
                "message": "Use 3 to 30 lowercase letters, numbers or underscores only.",
                "suggestions": username_suggestions(normalized or raw_value or "namvibe", town=town),
            }
    elif field == "phone":
        if not normalize_phone(raw_value):
            return {
                "ok": True,
                "available": False,
                "field": field,
                "message": "Enter a phone number.",
                "suggestions": [],
            }
    else:
        return {
            "ok": True,
            "available": False,
            "field": field,
            "message": "Unsupported field.",
            "suggestions": [],
        }

    return {
        "ok": True,
        "available": True,
        "field": field,
        "message": "Looks good. We will verify this during signup.",
        "suggestions": [],
    }


def _apply_registration_session(result):
    profile = result.get("profile") or {}
    auth_user_id = result.get("auth_user_id") or profile.get("auth_user_id")
    email = profile.get("email")
    session.clear()
    session.permanent = True
    session["logged_in"] = True
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
    session["logged_in"] = True
    session["profile_completed"] = bool(profile.get("profile_completed"))
    session["remember_me"] = True
    session["login_at"] = int(time.time())
    if result.get("access_token"):
        session["access_token"] = result.get("access_token")
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


def _registration_session_keys_present():
    return {
        "profile_id": bool(session.get("profile_id")),
        "auth_user_id": bool(session.get("auth_user_id")),
        "user_id": bool(session.get("user_id")),
        "email": bool(session.get("email") or session.get("auth_email")),
        "logged_in": bool(session.get("logged_in")),
    }


def _debug_session_payload():
    return {
        "ok": True,
        "logged_in": bool(session.get("profile_id") and (session.get("auth_user_id") or session.get("user_id"))),
        "profile_id": session.get("profile_id"),
        "auth_user_id": session.get("auth_user_id"),
        "user_id": session.get("user_id"),
        "email": session.get("email"),
        "session_keys": sorted(list(session.keys())),
        "cookie_name": current_app.config.get("SESSION_COOKIE_NAME", "session"),
        "host": request.host,
        "user_agent": request.headers.get("User-Agent", ""),
    }


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


def _provider_template_flags():
    status = get_supabase_auth_configuration_status()
    return {
        "google_oauth_enabled": bool(status.get("google_provider_expected")),
        "facebook_oauth_enabled": bool(status.get("facebook_provider_expected")),
    }


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


def _no_cache_headers(template_output):
    if isinstance(template_output, str):
        response = make_response(template_output)
    else:
        response = template_output
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _existing_session_redirect():
    if not (session.get("auth_user_id") or session.get("user_id")):
        return None
    if not session.get("access_token") and not session.get("profile_id"):
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
    existing_target = _existing_session_redirect() if request.method == "GET" else None
    if request.method == "GET" and existing_target:
        return redirect(existing_target)
    error = None
    oauth_error = None
    success_message = None
    
    # Handle success/status messages
    if request.args.get("password_reset") == "1":
        success_message = "Password updated. You can now log in."
    elif request.args.get("registered") == "1":
        success_message = "Account created. Check your email or log in now."
    elif request.args.get("oauth_error") == "1":
        oauth_error = "We could not complete social login. Try email registration or check OAuth callback settings."

    if request.method == "POST":
        form_next = request.form.get("next") or ""
        if form_next.startswith("/"):
            session["auth_next"] = form_next
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
        remember_me = request.form.get("remember_me") in {"1", "true", "on", "yes"}
        ok, result = login_chain_user({
            "login_id": raw_login_id,
            "password": raw_password,
            "remember_me": remember_me,
        })
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
            oauth_error = session.pop("oauth_error_message", None) or "We could not complete social login. Try email registration or check OAuth callback settings."
        else:
            _clear_oauth_error_state()
            
    return _no_cache_headers(render_template(
        "auth/login.html",
        error=error,
        oauth_error=oauth_error,
        success_message=success_message,
        next_path=session.get("auth_next"),
        **_provider_template_flags(),
    ))


@auth_bp.route("/register", methods=["GET"])
@limiter.exempt
def register():
    existing_target = _existing_session_redirect()
    if existing_target:
        return redirect(existing_target)
    return _no_cache_headers(render_template("auth/register.html", error=None, form=None, **_provider_template_flags()))


@auth_bp.route("/register", methods=["POST"])
@limiter.limit(
    "5/hour",
    key_func=_auth_rate_limit_key,
    methods=["POST"],
    exempt_when=_register_rate_limit_exempt,
)
def register_post():
    error = None
    try:
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        raw_email = request.form.get("email")
        email = clean_email(raw_email)
        username = (request.form.get("username") or request.form.get("display_name") or request.form.get("full_name") or "").strip()
        full_name = (request.form.get("full_name") or request.form.get("display_name") or request.form.get("name") or username or "").strip()
        phone = (request.form.get("phone") or "").strip()
        country_origin = (request.form.get("country_origin") or "").strip()
        date_of_birth = (request.form.get("date_of_birth") or "").strip()
        gender = (request.form.get("gender") or "").strip()
        csrf_valid = bool(request.environ.get("namvibe_csrf_valid", True))
        apk_token = (request.form.get("apk_csrf_token") or request.headers.get("X-NamVibe-Apk-CSRF") or "").strip()
        if not apk_token or not csrf_valid:
            return _no_cache_headers(render_template("auth/register.html", error="Your session expired. Please refresh and try again.", form=request.form, **_provider_template_flags()))
        log_warning(
            "auth_register_apk_route_input",
            user_agent=request.headers.get("User-Agent", ""),
            host=request.host,
            form_email_received=str(raw_email or "").strip(),
            normalized_email=email,
            csrf_valid=csrf_valid,
            auth_provider_used="pending",
        )
        if not (username or "").strip():
            return _no_cache_headers(render_template("auth/register.html", error="Enter a name or username.", form=request.form, **_provider_template_flags()))
        if not _email_valid(email):
            return _no_cache_headers(render_template("auth/register.html", error="Enter a valid email address.", form=request.form, **_provider_template_flags()))
        if not password:
            return _no_cache_headers(render_template("auth/register.html", error="Password is required.", form=request.form, **_provider_template_flags()))
        if len(password) < 8:
            return _no_cache_headers(render_template("auth/register.html", error="Password must be at least 8 characters.", form=request.form, **_provider_template_flags()))
        if password != confirm_password:
            error = "Passwords do not match."
            return _no_cache_headers(render_template("auth/register.html", error=error, form=request.form, **_provider_template_flags()))
        if not request.form.get("terms"):
            return _no_cache_headers(render_template("auth/register.html", error="You must accept the terms before creating your account.", form=request.form, **_provider_template_flags()))

        result = register_chain_user(
            email,
            password,
            username,
            full_name,
            extra={
                "phone": phone,
                "phone_code": (request.form.get("phone_code") or "").strip(),
                "gender": gender,
                "date_of_birth": date_of_birth,
                "country_origin": country_origin,
                "current_country": country_origin,
                "country": country_origin,
                "profile_type": request.form.get("profile_type") or "member",
                "signup_method": "email",
                "terms_accepted": True,
                "profile_completed": False,
                "csrf_valid": csrf_valid,
            },
        )
        if not isinstance(result, dict):
            result = {"ok": False, "error": "Registration failed. Please try again."}
        log_warning(
            "auth_register_apk_route_result",
            user_agent=request.headers.get("User-Agent", ""),
            host=request.host,
            form_email_received=str(raw_email or "").strip(),
            normalized_email=email,
            csrf_valid=csrf_valid,
            auth_provider_used=result.get("auth_provider") or ("local_fallback" if result.get("dev_fallback") else "supabase"),
            ok=bool(result.get("ok")),
            error=result.get("error"),
        )
        if result.get("ok"):
            if result.get("requires_confirmation"):
                return _no_cache_headers(render_template("auth/check_email.html", email=email))

            auth_session = result.get("session")
            user = result.get("user")
            profile = result.get("profile") or {}
            if auth_session and user:
                establish_login_session(auth_session, user, profile=profile, provider="password", remember=True)
            else:
                _apply_registration_session(result)
            redirect_to = "/profile/" if profile.get("profile_completed") else "/profile/onboarding"
            _log_registration_route_state(result, redirect_to=redirect_to)
            flash("Account created successfully.", "success")
            response = redirect(redirect_to)
            current_app.session_interface.save_session(current_app, session, response)
            log_warning(
                "auth_register_session_redirect",
                route=request.path,
                user_agent=request.headers.get("User-Agent", ""),
                result_ok=True,
                redirect_to=redirect_to,
                session_keys_present=_registration_session_keys_present(),
                set_cookie_exists=bool(response.headers.get("Set-Cookie")),
                profile_id_in_session=bool(session.get("profile_id")),
            )
            return response

        if result.get("error") == "EMAIL_EXISTS":
            error = {
                "message": "This email already has a NamVibe account.",
                "email": request.form.get("email"),
                "exists": True,
            }
        else:
            error = result.get("error") or "Registration failed. Please try again."
        return _no_cache_headers(render_template("auth/register.html", error=error, form=request.form, **_provider_template_flags()))
    except Exception as _route_err:
        log_warning("auth_register_route_unexpected_error", error=str(_route_err)[:240])
        return _no_cache_headers(
            render_template("auth/register.html", error="Registration is temporarily unavailable. Please try again later.", form=request.form, **_provider_template_flags())
        )


@auth_bp.get("/api/prewarm-register")
@limiter.exempt
def api_prewarm_register():
    try:
        from services.neon_service import prime_neon_runtime
        prime_neon_runtime()
        return jsonify({"ok": True, "pool_ready": True}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200


@auth_bp.route("/debug-input")
def debug_input():
    if _is_production_env():
        abort(404)
    return render_template("auth/debug_input.html", form=request.args)


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
    return render_template("auth/profile_error.html", error_detail="Welcome tour is ready. Start exploring NamVibe or skip for now.")


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
    return jsonify(_availability(field, value, town=town))


@auth_bp.get("/api/check-email")
@limiter.limit("180/minute", key_func=_auth_rate_limit_key, exempt_when=_register_rate_limit_exempt)
def api_check_email():
    result = _fast_api_availability("email", request.args.get("email"))
    return jsonify({
        "ok": bool(result.get("ok")),
        "available": bool(result.get("available")),
        "message": result.get("message") or "",
    })


@auth_bp.get("/api/check-username")
@limiter.limit("180/minute", key_func=_auth_rate_limit_key, exempt_when=_register_rate_limit_exempt)
def api_check_username():
    result = _fast_api_availability("username", request.args.get("username"), town=request.args.get("town"))
    return jsonify({
        "ok": bool(result.get("ok")),
        "available": bool(result.get("available")),
        "message": result.get("message") or "",
        "suggestions": result.get("suggestions") or [],
    })


@auth_bp.get("/api/check-phone")
@limiter.limit("180/minute", key_func=_auth_rate_limit_key, exempt_when=_register_rate_limit_exempt)
def api_check_phone():
    result = _fast_api_availability("phone", request.args.get("phone"))
    return jsonify({
        "ok": bool(result.get("ok")),
        "available": bool(result.get("available")),
        "message": result.get("message") or "",
    })


@auth_bp.get("/debug-csrf")
def debug_csrf():
    if _is_production_env():
        abort(404)
    cookie_name = current_app.config.get("SESSION_COOKIE_NAME", "session")
    return jsonify({
        "has_session_cookie": cookie_name in request.cookies,
        "secure_cookie": current_app.config.get("SESSION_COOKIE_SECURE"),
        "samesite": current_app.config.get("SESSION_COOKIE_SAMESITE"),
        "csrf_enabled": bool(current_app.config.get("WTF_CSRF_ENABLED", True)),
    })


@auth_bp.get("/debug-session")
def debug_session():
    if _is_production_env():
        abort(404)
    return jsonify(_debug_session_payload())


@auth_bp.route("/google")
def google_login():
    if not _provider_template_flags().get("google_oauth_enabled"):
        session["oauth_error_message"] = "Google sign-in is temporarily unavailable."
        return redirect(url_for("auth.login", oauth_error=1))
    state = os.urandom(16).hex()
    session["oauth_mode"] = request.args.get("mode", "login")
    session["auth_provider"] = "google"
    session["oauth_state"] = state
    session["auth_next"] = _next_target()
    url = get_oauth_url("google", state=state)
    if url:
        return redirect(url)
    _queue_oauth_error()
    return redirect(url_for("auth.login", oauth_error=1))


@auth_bp.route("/facebook")
def facebook_login():
    if not _provider_template_flags().get("facebook_oauth_enabled"):
        session["oauth_error_message"] = "Facebook sign-in is temporarily unavailable."
        return redirect(url_for("auth.login", oauth_error=1))
    state = os.urandom(16).hex()
    session["oauth_mode"] = request.args.get("mode", "login")
    session["auth_provider"] = "facebook"
    session["oauth_state"] = state
    session["auth_next"] = _next_target()
    url = get_oauth_url("facebook", state=state)
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
    if request.args.get("type") == "recovery" or request.args.get("token_hash"):
        return redirect(url_for("auth.reset_password", **request.args))

    if request.args.get("error") or request.args.get("error_description"):
        session["oauth_error_message"] = request.args.get("error_description") or "Auth failed."
        return redirect(url_for("auth.login", oauth_error=1))

    provider = session.get("auth_provider")
    if not provider and "/google/" in request.path:
        provider = "google"
    elif not provider and "/facebook/" in request.path:
        provider = "facebook"

    if not provider:
        session["oauth_error_message"] = "Could not determine the sign-in provider. Please try again."
        return redirect(url_for("auth.login", oauth_error=1))

    mode = session.pop("oauth_mode", "login")
    expected_state = session.pop("oauth_state", None)
    if not request.args.get("code"):
        session["oauth_error_message"] = "Social sign-in could not complete. Please try again."
        return redirect(url_for("auth.login", oauth_error=1))

    ok, result = handle_oauth_callback(provider, request.args, mode=mode, expected_state=expected_state)
    if ok:
        session["auth_provider"] = provider
        return redirect(_post_login_redirect(result))

    session["oauth_error_message"] = result
    return redirect(url_for("auth.login", oauth_error=1))


@auth_bp.route("/oauth-diagnostics")
def oauth_diagnostics():
    """
    Diagnostic page for OAuth configuration.
    """
    status = get_supabase_auth_configuration_status()
    site_url = status.get("site_url")
    data = {
        **status,
        "redirect_urls": [f"{site_url}{path}" for path in status.get("allowed_callback_routes", [])],
        "google_redirect": f"{os.getenv('SUPABASE_URL', '').rstrip('/')}/auth/v1/callback" if os.getenv("SUPABASE_URL") else "",
        "facebook_redirect": f"{os.getenv('SUPABASE_URL', '').rstrip('/')}/auth/v1/callback" if os.getenv("SUPABASE_URL") else "",
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
                return redirect(url_for("auth.login", password_reset=1))
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
