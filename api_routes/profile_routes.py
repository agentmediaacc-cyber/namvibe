import os
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for, jsonify
from werkzeug.utils import secure_filename

from services.auth_service import refresh_chain_session, set_current_user_password
from services.auth_service import best_effort_age_dob_update
from services.activity_engine import emit_activity
from services.session_service import (
    is_logged_in,
    get_current_auth_user,
    refresh_supabase_session_if_needed,
    clear_auth_session,
    K_USER_ID, K_PROFILE_WARNING, K_AGE_CHECK_REQUIRED, K_PENDING_DATE_OF_BIRTH
)
from services.notification_service import get_my_notifications
from services.profile_service import (
    _age_from_dob,
    accept_friend_request,
    block_profile,
    bootstrap_profile_for_current_user,
    cancel_friend_request,
    create_or_update_profile,
    decline_friend_request,
    delete_post,
    delete_reel,
    favorite_profile,
    follow_profile,
    get_current_profile,
    get_followers_page,
    get_following_page,
    get_following_types,
    get_friend_requests,
    get_friend_status,
    get_friends,
    get_profile_bundle,
    get_profile_by_id,
    get_profile_by_username,
    get_profile_content,
    get_profile_posts,
    get_profile_privacy,
    get_profile_reels,
    get_profile_settings,
    get_profile_stats,
    get_reel_analytics,
    get_sent_friend_requests,
    invalidate_profile_cache,
    is_adult_profile,
    is_profile_complete,
    like_profile,
    mute_profile,
    normalize_dob,
    record_profile_view,
    remove_follower,
    remove_friend,
    report_profile,
    send_friend_request,
    toggle_post_comments,
    toggle_post_pin,
    toggle_post_sharing,
    toggle_reel_comments,
    toggle_reel_pin,
    toggle_reel_sharing,
    unmute_profile,
    update_post_visibility,
    update_profile,
    update_profile_privacy,
    update_profile_setup,
    update_reel_visibility,
    upload_profile_avatar,
    upload_profile_cover,
    verify_profile_age,
)
from services.profile_dashboard_service import build_profile_dashboard
from services.profile_view_service import build_profile_view_model
from services.storage_service import upload_avatar, upload_cover, upload_verification_file
from services.neon_service import fast_query
from services.logging_service import log_error, log_warning, log_info
from services.friend_service import list_friends, list_friend_requests, are_friends, get_mutual_friends, suggest_friends
from services.creator_service import get_creator_dashboard_data, get_creator_analytics
from services.wallet_service import get_or_create_wallet
from services.profile_service import get_wallet_snapshot
from services.security_service import get_device_sessions, get_security_events, get_privacy_settings
from services.trust_score_service import get_trust_summary
from services.ai.interaction_service import track_interaction_safe

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

UPLOAD_MAP = {
    "avatar": "static/uploads/profile/avatars",
    "cover": "static/uploads/profile/covers",
    "verification": "static/uploads/profile/verifications",
}


def _is_production_env():
    if os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    return os.getenv("FLASK_ENV") == "production" or os.getenv("ENV") == "production"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        has_local_session = bool(session.get("profile_id") and (session.get("auth_user_id") or session.get("user_id")))
        if not is_logged_in():
            if session.get("refresh_token"):
                refresh_supabase_session_if_needed()
        if not is_logged_in() and not has_local_session:
            if request.path.startswith('/api/') or request.path.startswith('/reels/api/') or request.path.startswith('/posts/api/') or request.path.startswith('/status/api/'):
                return jsonify({"error": "Unauthorized", "message": "Authentication required"}), 401
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)

    return decorated_function


def save_upload(file, folder):
    if not file or not file.filename:
        return None
    os.makedirs(folder, exist_ok=True)
    filename = secure_filename(file.filename)
    filename = f"{int(time.time())}_{filename}"
    path = os.path.join(folder, filename)
    file.save(path)
    return "/" + path


def _profile_form_defaults():
    return {
        "email": session.get("email"),
        "full_name": session.get("full_name", ""),
        "username": session.get("email", "").split("@")[0] if session.get("email") else "",
        "premium_tier": "free",
        "profile_type": "member",
    }


def _redirect_back(username=None):
    return redirect(request.referrer or (url_for("profile.public_profile", username=username) if username else url_for("profile.my_profile")))


def _session_profile_stub():
    email = session.get("auth_email") or ""
    username = session.get("username") or (email.split("@")[0] if "@" in email else "")
    full_name = session.get("full_name") or ""
    return _with_profile_defaults({
        "id": session.get("profile_id"),
        "auth_user_id": session.get("auth_user_id"),
        "email": email,
        "username": username,
        "full_name": full_name,
        "display_name": full_name,
        "avatar_url": None,
        "date_of_birth": session.get(K_PENDING_DATE_OF_BIRTH),
        "profile_completed": False,
        "profile_type": "member",
    })


def _safe_number(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _with_profile_defaults(profile):
    profile = dict(profile or {})
    username = profile.get("username") or "user"
    display_name = profile.get("display_name") or profile.get("full_name") or username.replace("_", " ").title()
    created_at = profile.get("created_at") or datetime.now(timezone.utc).isoformat()
    profile.setdefault("id", profile.get("auth_user_id") or session.get("profile_id") or session.get("auth_user_id") or "local-profile")
    profile.setdefault("auth_user_id", profile.get("id"))
    profile["username"] = username
    profile["display_name"] = display_name
    profile["full_name"] = profile.get("full_name") or display_name
    profile["bio"] = profile.get("bio") or ""
    profile["avatar_url"] = profile.get("avatar_url") or profile.get("profile_photo")
    profile["cover_url"] = profile.get("cover_url")
    profile["location"] = profile.get("location") or profile.get("current_location") or profile.get("town") or profile.get("region") or profile.get("country_origin") or ""
    profile["current_location"] = profile.get("current_location") or profile["location"]
    profile["website"] = profile.get("website") or profile.get("portfolio_url") or ""
    profile["is_verified"] = bool(profile.get("is_verified") or profile.get("verified") or profile.get("email_verified"))
    profile["verified"] = bool(profile.get("verified") or profile["is_verified"])
    profile["email_verified"] = bool(profile.get("email_verified") or profile["is_verified"])
    profile["rank"] = profile.get("rank") or "New Member"
    profile["created_at"] = created_at
    profile["last_login_at"] = profile.get("last_login_at") or profile.get("last_active") or profile.get("updated_at") or created_at
    profile["followers_count"] = _safe_number(profile.get("followers_count"))
    profile["following_count"] = _safe_number(profile.get("following_count"))
    profile["posts_count"] = _safe_number(profile.get("posts_count"))
    profile["reels_count"] = _safe_number(profile.get("reels_count"))
    profile["total_likes"] = _safe_number(profile.get("total_likes"))
    profile["profile_views"] = _safe_number(profile.get("profile_views"))
    profile["wallet_balance"] = float(profile.get("wallet_balance") or 0)
    profile["chain_score"] = _safe_number(profile.get("chain_score"))
    profile["trust_score"] = _safe_number(profile.get("trust_score"))
    profile["dating_mode_enabled"] = bool(profile.get("dating_mode_enabled"))
    profile["skills"] = profile.get("skills") or []
    return profile


def _profile_fallback_context():
    from services.profile_completion_service import calculate_profile_completion
    from services.social_action_policy import get_action_policy
    viewer = _session_profile_stub()
    action_policy = get_action_policy(viewer.get("id"), viewer)
    context = {
        "unread_count": 0,
        "viewer": viewer,
        "profile": viewer,
        "setup_warning": True,
        "profile_fallback": True,
        "current_year": datetime.now(timezone.utc).year,
        "stats": {},
        "content": {"posts": [], "reels": [], "rooms": [], "stories": []},
        "activity": [],
        "wallet": {},
        "creator_tools": {},
        "actions": [],
        "presence": {"status": "offline"},
        "is_following": False,
        "is_page_liked": False,
        "public_stats": {"posts": 0, "followers": 0, "reels": 0, "likes": 0},
        "action_policy": action_policy,
        "completion": calculate_profile_completion(viewer),
        "level": {"title": "New Member", "score": 0, "next_target": 10, "progress_pct": 0},
        "permissions": {"can_message": False, "can_call": False, "can_contact_email": bool(viewer.get("email") if viewer else False)},
        "contact": {"message": False, "call": False, "email": bool(viewer.get("email") if viewer else False), "whatsapp": False},
        "creator": {},
        "marketplace": {"items": [], "featured_products": []},
        "dating": {},
        "portfolio": {"skills": []},
        "ai": {},
        "live": {"go_live_url": "/live/studio"},
        "calls": {},
        "reputation": {},
        "achievements": [],
        "theme_options": ["Namibia Gold", "Ocean Blue", "Emerald Green", "Royal Purple", "Dark Premium"],
        "pinned": {"posts": [], "reels": [], "products": []},
    }
    context["profile_view"] = build_profile_view_model(
        viewer,
        viewer=viewer,
        stats=context["stats"],
        content=context["content"],
        wallet=context["wallet"],
        creator=context["creator"],
        marketplace=context["marketplace"],
        presence=context["presence"],
        action_policy=context["action_policy"],
    )
    context["pv"] = context["profile_view"]
    return context


def _current_profile_or_session_fallback():
    viewer = get_current_profile()
    if viewer:
        return viewer
    has_session_identity = bool(session.get("profile_id") and (session.get("auth_user_id") or session.get("user_id")))
    fast_local = os.getenv("CHAIN_FAST_LOCAL", "").lower() in ("1", "true", "yes", "on") or os.getenv("FLASK_TESTING") == "1"
    if not has_session_identity or not fast_local:
        return None
    username = session.get("username") or "user"
    full_name = session.get("full_name") or username.replace("_", " ").title()
    return {
        "id": session.get("profile_id"),
        "auth_user_id": session.get("auth_user_id") or session.get("user_id"),
        "username": username,
        "display_name": full_name,
        "full_name": full_name,
        "email": session.get("auth_email") or session.get("email"),
        "avatar_url": session.get("avatar_url"),
        "profile_completed": bool(session.get("profile_completed")),
        "profile_fallback": True,
    }


def _apply_profile_session(profile, fallback_email=None):
    if not profile:
        return
    profile_id = profile.get("id")
    auth_user_id = profile.get("auth_user_id") or session.get("auth_user_id") or session.get("user_id")
    email = profile.get("email") or fallback_email or session.get("auth_email") or session.get("email")
    if profile_id:
        session["profile_id"] = profile_id
    if auth_user_id:
        session["user_id"] = auth_user_id
        session["auth_user_id"] = auth_user_id
    if email:
        session["email"] = email
    if profile.get("username"):
        session["username"] = profile.get("username")
    session.modified = True


def _render_profile_index(profile, viewer=None, status_code=200, unread_count=0, setup_warning=False, bundle=None, action_policy=None):
    try:
        bundle = bundle or get_profile_bundle(profile_id=profile["id"], viewer=viewer)
    except Exception as error:
        log_warning("profile_bundle_route_failed", profile_id=profile.get("id"), error=str(error))
        bundle = None
    if not bundle:
        log_warning("profile_bundle_missing", profile_id=profile.get("id"), username=profile.get("username"))
        fallback = _profile_fallback_context()
        fallback["profile"] = _with_profile_defaults(profile)
        fallback["viewer"] = _with_profile_defaults(viewer or profile)
        fallback["action_policy"] = action_policy
        if not fallback.get("action_policy"):
            from services.social_action_policy import get_action_policy
            viewer_id = fallback["viewer"].get("id") if fallback.get("viewer") else None
            fallback["action_policy"] = get_action_policy(viewer_id, fallback["profile"])
        from services.profile_completion_service import calculate_profile_completion
        fallback["completion"] = calculate_profile_completion(fallback["profile"])
        try:
            from services.profile_service import get_profile_content, get_profile_stats
            viewer_id = fallback["viewer"].get("id") if fallback.get("viewer") else None
            fallback["content"] = get_profile_content(viewer_id, profile.get("id"), "posts")
            fallback["stats"] = get_profile_stats(profile.get("id"))
        except Exception:
            pass
        fallback["profile_view"] = build_profile_view_model(
            fallback["profile"],
            viewer=fallback["viewer"],
            stats=fallback.get("stats"),
            content=fallback.get("content"),
            wallet=fallback.get("wallet"),
            creator=fallback.get("creator"),
            marketplace=fallback.get("marketplace"),
            presence=fallback.get("presence"),
            action_policy=fallback.get("action_policy"),
        )
        fallback["pv"] = fallback["profile_view"]
        # Premium profile data
        try:
            pid = profile.get("id")
            if pid:
                from services.profile_premium_service import (
                    get_achievements, get_badges, get_collections, get_timeline,
                    get_education, get_work_experience, get_skills,
                    get_visitors, get_activity_log, get_favorites_by_type,
                )
                fallback["achievements"] = get_achievements(pid) or []
                fallback["badges"] = get_badges(pid) or []
                fallback["collections"] = get_collections(pid) or []
                fallback["timeline"] = get_timeline(pid) or []
                fallback["education"] = get_education(pid) or []
                fallback["works"] = get_work_experience(pid) or []
                fallback["skills"] = get_skills(pid) or []
                fallback["visitors"] = get_visitors(pid) or []
                fallback["activity"] = get_activity_log(pid) or []
                fallback["favorites_music"] = get_favorites_by_type(pid, "music") or []
                fallback["favorites_games"] = get_favorites_by_type(pid, "game") or []
        except Exception:
            pass
        return render_template("profile/index.html", **fallback), status_code
    try:
        dashboard = build_profile_dashboard(profile=profile, viewer=viewer, bundle=bundle)
    except Exception as error:
        log_warning("profile_dashboard_build_failed", profile_id=profile.get("id"), error=str(error))
        dashboard = {}
    render_bundle = dict(bundle)
    render_profile = _with_profile_defaults(dashboard.get("profile") or render_bundle.pop("profile", profile))
    render_bundle.pop("profile", None)
    context = {
        "unread_count": unread_count,
        "viewer": viewer,
        "profile": render_profile,
        "setup_warning": setup_warning,
        "action_policy": action_policy,
    }
    context.update(render_bundle)
    context.update(dashboard)
    context["profile"] = render_profile
    context["viewer"] = _with_profile_defaults(viewer) if viewer else None
    profile_content = dict(context.get("content") or {})
    profile_content["mutual_friends"] = context.get("mutual_friends") or render_bundle.get("mutual_friends") or {"count": 0, "items": []}
    profile_content["profile_strength"] = context.get("profile_strength") or render_bundle.get("profile_strength") or {"score": 0, "level": "Fresh", "checks": []}
    # Query real content if bundle left it empty
    profile_id = render_profile.get("id")
    if profile_content.get("posts") in (None, []) and profile_id:
        try:
            from services.profile_service import get_profile_content
            viewer_id = viewer.get("id") if viewer else None
            real = get_profile_content(viewer_id, profile_id, "posts") or {}
            posts = real.get("posts") or real.get("items") or []
            reels = real.get("reels") or []
            profile_content["posts"] = posts
            profile_content["reels"] = reels
        except Exception:
            pass
    context["content"] = profile_content
    if not context.get("action_policy"):
        from services.social_action_policy import get_action_policy
        viewer_id = viewer.get("id") if viewer else None
        context["action_policy"] = get_action_policy(viewer_id, render_profile)
    context["profile_view"] = build_profile_view_model(
        context["profile"],
        viewer=context.get("viewer"),
        stats=context.get("stats"),
        content=context.get("content"),
        wallet=context.get("wallet"),
        creator=context.get("creator") or context.get("creator_tools"),
        marketplace=context.get("marketplace"),
        presence=context.get("presence"),
        action_policy=context.get("action_policy"),
    )
    context["pv"] = context["profile_view"]
    # Determine subscriber status for locked content display
    try:
        viewer_id = viewer.get("id") if viewer else None
        profile_id = render_profile.get("id")
        if viewer_id and profile_id and str(viewer_id) != str(profile_id):
            sub_check = fast_query(
                "SELECT status FROM chain_creator_subscriptions WHERE subscriber_id = %s AND creator_id = %s AND status = 'active' LIMIT 1",
                (viewer_id, profile_id), default=[]
            )
            context["subscriber_status"] = sub_check[0].get("status", "inactive") if sub_check else "inactive"
        else:
            context["subscriber_status"] = "active" if (viewer_id and profile_id and str(viewer_id) == str(profile_id)) else "inactive"
    except Exception:
        context["subscriber_status"] = "inactive"
    # Premium profile data (education, work, skills, visitors, etc.)
    try:
        profile_id = render_profile.get("id")
        if profile_id:
            from services.profile_premium_service import (
                get_achievements, get_badges, get_collections, get_timeline,
                get_education, get_work_experience, get_skills,
                get_visitors, get_activity_log, get_favorites_by_type,
            )
            context["achievements"] = get_achievements(profile_id) or []
            context["badges"] = get_badges(profile_id) or []
            context["collections"] = get_collections(profile_id) or []
            context["timeline"] = get_timeline(profile_id) or []
            context["education"] = get_education(profile_id) or []
            context["works"] = get_work_experience(profile_id) or []
            context["skills"] = get_skills(profile_id) or []
            context["visitors"] = get_visitors(profile_id) or []
            context["activity"] = get_activity_log(profile_id) or []
            context["favorites_music"] = get_favorites_by_type(profile_id, "music") or []
            context["favorites_games"] = get_favorites_by_type(profile_id, "game") or []
    except Exception as exc:
        log_warning("premium_profile_data_error", profile_id=profile.get("id"), error=str(exc))
    return render_template("profile/index.html", **context), status_code


def _resolve_profile_route(username=None, user_id=None):
    start = time.perf_counter()
    fast_profile_shell = (
        request.args.get("shell") == "1"
        or
        os.getenv("CHAIN_FORCE_FAST_HOME", "").lower() in ("1", "true", "yes", "on")
        or os.getenv("CHAIN_FAST_LOCAL", "").lower() in ("1", "true", "yes", "on")
        or os.getenv("CHAIN_TUNNEL_TESTING", "").lower() in ("1", "true", "yes", "on")
    )
    viewer = None if fast_profile_shell else (get_current_profile() if is_logged_in() else None)
    profile = None
    if username:
        cleaned_username = username[1:] if username.startswith("@") else username
        profile = get_profile_by_username(cleaned_username)
    elif user_id:
        profile = get_profile_by_id(user_id)

    if not profile:
        log_warning("public_profile_missing", username=username, user_id=user_id)
        log_info("profile_page_total", duration_ms=round((time.perf_counter() - start) * 1000, 2), profile_found=False)
        return render_template("profile/not_found.html", username=username or user_id or ''), 404

    if fast_profile_shell:
        shell_profile = {
            "id": profile.get("id"),
            "username": profile.get("username"),
            "display_name": profile.get("display_name") or profile.get("full_name") or profile.get("username"),
            "avatar_url": profile.get("avatar_url"),
            "bio": profile.get("bio") or "",
            "verified": bool(profile.get("verified") or profile.get("is_verified")),
            "is_verified": bool(profile.get("verified") or profile.get("is_verified")),
            "full_name": profile.get("display_name") or profile.get("full_name") or profile.get("username"),
        }
        log_info("profile_page_total", duration_ms=round((time.perf_counter() - start) * 1000, 2), profile_id=profile.get("id"), privacy="public", shell=True)
        return render_template("profile/public.html", profile=shell_profile, viewer=None, content={"posts": [], "reels": [], "rooms": []}), 200

    if viewer and viewer.get("id") != profile.get("id"):
        record_profile_view(profile.get("id"), viewer.get("id"))
        emit_activity(viewer.get("id"), "profile_viewed", target_type="profile", target_id=profile.get("id"), recipient_profile_id=profile.get("id"))
        track_interaction_safe(viewer.get("id"), "profile", profile.get("id"), "open", source_surface="profile")

    from services.social_action_policy import get_action_policy, can_view_profile
    viewer_id = viewer.get("id") if viewer else None
    action_policy = get_action_policy(viewer_id, profile)
    view_result = can_view_profile(viewer_id, profile)
    profile["action_policy"] = action_policy

    if not view_result.get("can_view_full_profile"):
        context = {
            "profile": profile,
            "viewer": viewer,
            "action_policy": action_policy,
            "privacy_message": "This profile is private.",
            "current_year": profile.get("created_at", datetime.now(timezone.utc)).year
            if isinstance(profile.get("created_at"), datetime)
            else datetime.now(timezone.utc).year,
        }
        log_info("profile_page_total", duration_ms=round((time.perf_counter() - start) * 1000, 2), profile_id=profile.get("id"), privacy="private")
        return render_template("profile/private_profile.html", **context), 200

    response = _render_profile_index(profile, viewer=viewer, action_policy=action_policy)
    log_info("profile_page_total", duration_ms=round((time.perf_counter() - start) * 1000, 2), profile_id=profile.get("id"), privacy="public")
    return response




@profile_bp.route("/")
@login_required
def my_profile():
    start = time.perf_counter()
    try:
        if not _is_production_env() and (session.get("profile_id") or session.get("auth_user_id")):
            session["age_verified"] = True
            session["age_check_required"] = False
            session.modified = True

        # Trust session age check if explicitly False
        if session.get(K_AGE_CHECK_REQUIRED) is True:
            return redirect(url_for("profile.age_check"))

        viewer = get_current_profile()
        if not viewer:
            if session.get("profile_id"):
                try:
                    viewer = get_profile_by_id(session.get("profile_id"))
                    if viewer:
                        _apply_profile_session(viewer)
                except Exception as error:
                    log_warning("profile_session_id_lookup_failed", profile_id=session.get("profile_id"), error=str(error))
            if not viewer and session.get("profile_id"):
                viewer = _session_profile_stub()
                context = _profile_fallback_context()
                context["profile"] = viewer
                context["viewer"] = viewer
                from services.social_action_policy import get_action_policy
                context["action_policy"] = get_action_policy(viewer.get("id"), viewer)
                try:
                    context["content"] = get_profile_content(viewer.get("id"))
                    context["stats"] = get_profile_stats(viewer.get("id"))
                except Exception:
                    pass
                return render_template("profile/index.html", **context)
            session[K_PROFILE_WARNING] = True
            log_warning(
                "profile_missing_for_session",
                auth_user_id=session.get("auth_user_id") or session.get("user_id"),
                profile_id=session.get("profile_id"),
                email=session.get("auth_email") or session.get("email"),
            )
            return redirect(url_for("profile.create_profile"))

        if viewer.get("profile_fallback"):
            context = _profile_fallback_context()
            context["profile"] = viewer
            context["viewer"] = viewer
            from services.social_action_policy import get_action_policy
            context["action_policy"] = get_action_policy(viewer.get("id"), viewer)
            try:
                context["content"] = get_profile_content(viewer.get("id"))
                context["stats"] = get_profile_stats(viewer.get("id"))
            except Exception:
                pass
            return render_template("profile/index.html", **context)

        session.pop(K_PROFILE_WARNING, None)

        ok, result = verify_profile_age(viewer)
        if not ok:
            # Final fallback: if session says we already passed, trust it
            if session.get(K_AGE_CHECK_REQUIRED) is False:
                ok = True
                result = None

            if not ok:
                if result == "REDIRECT_AGE_CHECK":
                    session[K_AGE_CHECK_REQUIRED] = True
                    return redirect(url_for("profile.age_check"))
                log_warning("profile_age_verification_failed", profile_id=viewer.get("id"), detail=result)
                return render_template("auth/profile_error.html", error_detail=result), 200

        incomplete_profile = not is_profile_complete(viewer)

        try:
            bundle = get_profile_bundle(profile_id=viewer["id"], viewer=viewer)
        except Exception as error:
            log_warning("profile_bundle_current_failed", profile_id=viewer.get("id"), error=str(error))
            bundle = None
        if not bundle:
            session[K_PROFILE_WARNING] = True
            log_warning("profile_bundle_missing_for_current_user", profile_id=viewer.get("id"))
            context = _profile_fallback_context()
            context["profile"] = viewer
            context["viewer"] = viewer
            from services.social_action_policy import get_action_policy
            context["action_policy"] = get_action_policy(viewer.get("id"), viewer)
            try:
                context["content"] = get_profile_content(viewer.get("id"))
                context["stats"] = get_profile_stats(viewer.get("id"))
            except Exception:
                pass
            context["profile_view"] = build_profile_view_model(
                context["profile"],
                viewer=context.get("viewer"),
                stats=context.get("stats"),
                content=context.get("content"),
                wallet=context.get("wallet"),
                creator=context.get("creator") or context.get("creator_tools"),
                marketplace=context.get("marketplace"),
                presence=context.get("presence"),
                action_policy=context.get("action_policy"),
            )
            context["pv"] = context["profile_view"]
            return render_template("profile/index.html", **context)

        try:
            _, _, unread_count = get_my_notifications()
        except Exception as error:
            log_warning("profile_notifications_failed", profile_id=viewer.get("id"), error=str(error))
            unread_count = 0
        setup_warning = session.get(K_PROFILE_WARNING)
        return _render_profile_index(
            viewer,
            viewer=viewer,
            unread_count=unread_count,
            setup_warning=setup_warning or incomplete_profile,
            bundle=bundle,
        )
    except Exception as error:
        log_error("profile_route_failed", route="/profile/", error=str(error))
        return render_template("auth/profile_error.html", error_detail="Profile could not be loaded right now."), 500
    finally:
        log_info("profile_page_total", duration_ms=round((time.perf_counter() - start) * 1000, 2), route="/profile/")


@profile_bp.route("/age-check", methods=["GET", "POST"])
@login_required
def age_check():
    viewer = _session_profile_stub()

    error = None
    if request.method == "POST":
        raw_dob = request.form.get("date_of_birth")
        dob = normalize_dob(raw_dob)
        age = _age_from_dob(dob)

        if age is None:
            error = "Please enter a valid date of birth (DD/MM/YYYY or YYYY-MM-DD)."
        elif age < 18:
            # Explicitly block if underage
            return render_template("auth/profile_error.html", error_detail="NamVibe is only available to users 18 and older."), 200
        else:
            session["age_verified"] = True
            session[K_PENDING_DATE_OF_BIRTH] = dob
            session["date_of_birth"] = dob
            session[K_AGE_CHECK_REQUIRED] = False
            session["age_check_required"] = False

            # Ensure session active
            if viewer.get("id"):
                session["profile_id"] = viewer.get("id")
            if viewer.get("auth_user_id"):
                session["auth_user_id"] = viewer.get("auth_user_id")
                session["user_id"] = viewer.get("auth_user_id")

            saved = best_effort_age_dob_update(viewer.get("id"), viewer.get("auth_user_id"), dob)
            if saved:
                session.pop(K_PROFILE_WARNING, None)
                flash("Age verified. Welcome back!", "success")
            else:
                session[K_PROFILE_WARNING] = True
                flash("Age verified. Profile setup is finishing.", "warning")

            session.modified = True
            return redirect(url_for("profile.my_profile"))
    return render_template("profile/age_check.html", error=error, viewer=viewer, current_year=datetime.now(timezone.utc).year)


@profile_bp.route("/retry-bootstrap", methods=["GET", "POST"])
@login_required
def retry_bootstrap():
    ok, result = bootstrap_profile_for_current_user()
    if ok:
        session.pop(K_PROFILE_WARNING, None)
        flash("Profile sync successful.", "success")
        return redirect(url_for("profile.my_profile"))

    return render_template("auth/profile_error.html", error_detail=f"Profile sync failed: {result}")


@profile_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_profile():
    return redirect(url_for("profile.onboarding"))


@profile_bp.route("/setup", methods=["GET", "POST"])
@login_required
def setup_profile():
    return redirect(url_for("profile.onboarding"))


@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    viewer = _current_profile_or_session_fallback()
    if not viewer:
        ok, result = bootstrap_profile_for_current_user()
        viewer = result if ok and isinstance(result, dict) else _current_profile_or_session_fallback()
        if not viewer:
            return redirect(url_for("profile.onboarding"))

    ok, result = verify_profile_age(viewer)
    if not ok:
        if result == "REDIRECT_AGE_CHECK":
            session[K_AGE_CHECK_REQUIRED] = False
            result = None
            ok = True
    if not ok:
        return render_template("auth/profile_error.html", error_detail=result), 200

    setup_mode = request.args.get("setup") == "1"

    if request.method == "POST":
        data = dict(request.form)

        # Map allow_dating checkbox to dating_mode_enabled
        if "allow_dating" in data:
            data["dating_mode_enabled"] = True
        elif "dating_mode_enabled" not in data:
            data["dating_mode_enabled"] = False

        # Avatar Upload
        avatar_file = request.files.get("avatar")
        if avatar_file and avatar_file.filename:
            res, err = upload_avatar(viewer["id"], avatar_file)
            if res:
                data["avatar_url"] = res["public_url"]
                data["avatar_upload_id"] = res["upload_id"]
            else:
                flash(f"Avatar upload failed: {err}", "error")

        # Cover Upload
        cover_file = request.files.get("cover")
        if cover_file and cover_file.filename:
            res, err = upload_cover(viewer["id"], cover_file)
            if res:
                data["cover_url"] = res["public_url"]
                data["cover_upload_id"] = res["upload_id"]
            else:
                flash(f"Cover upload failed: {err}", "error")

        try:
            if setup_mode:
                setup_result = update_profile_setup(viewer["id"], data)
                ok = isinstance(setup_result, dict) and setup_result.get("id")
                result = setup_result
            else:
                updated = update_profile(viewer.get("id") or viewer.get("auth_user_id"), data)
                ok = bool(updated and updated.get("id"))
                result = updated
        except Exception as e:
            ok = False
            result = str(e)
        if ok:
            return redirect(url_for("profile.my_profile"))
        return render_template("profile/edit.html", error=result or "Update failed", profile=viewer, form=request.form)

    progress = viewer.get("profile_completion", 0)
    return render_template("profile/edit.html", profile=viewer, form=viewer, setup_mode=setup_mode, progress=progress)


@profile_bp.route("/@<username>")
@profile_bp.route("/id/<user_id>")
def view_profile(username=None, user_id=None):
    try:
        return _resolve_profile_route(username=username, user_id=user_id)
    except Exception as error:
        log_error("view_profile_failed", username=username, user_id=user_id, error=str(error))
        return render_template("profile/not_found.html", username=username or user_id or ''), 404


@profile_bp.route("", methods=["GET"])
def my_profile_no_slash():
    return my_profile()


@profile_bp.route("/friends")
@login_required
def friends():
    viewer = _current_profile_or_session_fallback()
    if not viewer:
        return redirect(url_for("auth.login", next=request.path))
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 20) or 20), 1), 50)
    try:
        friends_page = get_friends(viewer["id"], page=page, per_page=per_page) or {}
        inbound_page = get_friend_requests(viewer["id"], page=1, per_page=10) or {}
        outbound_page = get_sent_friend_requests(viewer["id"], page=1, per_page=10) or {}
    except Exception as error:
        log_warning("profile_friends_page_failed", profile_id=viewer.get("id"), error=str(error))
        friends_page = {}
        inbound_page = {}
        outbound_page = {}
    return render_template(
        "profile/friends.html",
        profile=viewer,
        viewer=viewer,
        friends=friends_page.get("friends", []),
        total=friends_page.get("total", 0),
        next_cursor=friends_page.get("next_cursor"),
        pending_requests=inbound_page.get("requests", []),
        outbound_requests=outbound_page.get("requests", []),
    )


@profile_bp.route("/followers")
@login_required
def followers():
    viewer = _current_profile_or_session_fallback()
    if not viewer:
        return redirect(url_for("auth.login", next=request.path))
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 20) or 20), 1), 50)
    try:
        followers_page = get_followers_page(viewer["id"], page=page, per_page=per_page) or {}
    except Exception as error:
        log_warning("profile_followers_page_failed", profile_id=viewer.get("id"), error=str(error))
        followers_page = {}
    return render_template(
        "profile/followers.html",
        profile=viewer,
        viewer=viewer,
        followers=followers_page.get("followers", []),
        total=followers_page.get("total", 0),
        next_cursor=followers_page.get("next_cursor"),
    )


@profile_bp.route("/following")
@login_required
def following():
    viewer = _current_profile_or_session_fallback()
    if not viewer:
        return redirect(url_for("auth.login", next=request.path))
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 20) or 20), 1), 50)
    follow_type = (request.args.get("type") or "all").strip().lower()
    try:
        following_page = get_following_page(viewer["id"], page=page, per_page=per_page) or {}
        type_counts = get_following_types(viewer["id"]) or {}
    except Exception as error:
        log_warning("profile_following_page_failed", profile_id=viewer.get("id"), error=str(error))
        following_page = {}
        type_counts = {}
    following_items = list(following_page.get("following", []))
    if follow_type != "all":
        following_items = [item for item in following_items if (item.get("profile_type") or "users").lower() == follow_type.rstrip("s")]
    return render_template(
        "profile/following.html",
        profile=viewer,
        viewer=viewer,
        following=following_items,
        total=following_page.get("total", len(following_items)),
        next_cursor=following_page.get("next_cursor"),
        following_types=type_counts,
    )


@profile_bp.route("/friend-requests")
@login_required
def friend_requests():
    viewer = _current_profile_or_session_fallback()
    if not viewer:
        return redirect(url_for("auth.login", next=request.path))
    try:
        inbound_page = get_friend_requests(viewer["id"], page=1, per_page=50) or {}
        outbound_page = get_sent_friend_requests(viewer["id"], page=1, per_page=50) or {}
    except Exception as error:
        log_warning("profile_friend_requests_page_failed", profile_id=viewer.get("id"), error=str(error))
        inbound_page = {}
        outbound_page = {}
    return render_template(
        "profile/friend_requests.html",
        profile=viewer,
        viewer=viewer,
        received=inbound_page.get("requests", []),
        sent=outbound_page.get("requests", []),
    )


@profile_bp.route("/sent-requests")
@login_required
def sent_requests():
    viewer = _current_profile_or_session_fallback()
    if not viewer:
        return redirect(url_for("auth.login", next=request.path))
    try:
        outbound_page = get_sent_friend_requests(viewer["id"], page=1, per_page=50) or {}
    except Exception as error:
        log_warning("profile_sent_requests_page_failed", profile_id=viewer.get("id"), error=str(error))
        outbound_page = {}
    return render_template(
        "profile/sent_requests.html",
        profile=viewer,
        viewer=viewer,
        sent=outbound_page.get("requests", []),
    )


@profile_bp.route("/<username>")
def public_profile(username):
    if username.startswith("@"):
        return redirect(url_for("profile.view_profile", username=username[1:]), 301)
    try:
        return _resolve_profile_route(username=username)
    except Exception as error:
        log_error("public_profile_failed", username=username, error=str(error))
        return render_template("profile/not_found.html", username=username or ''), 404


@profile_bp.route("/api/summary")
@login_required
def api_profile_summary():
    """Lightweight profile summary endpoint for lazy loading."""
    try:
        viewer = get_current_profile()
        if not viewer:
            return jsonify({"error": "Unauthorized"}), 401
        profile = get_profile_by_id(viewer["id"])
        if not profile:
            return jsonify({"error": "Profile not found"}), 404
        return jsonify({
            "id": profile.get("id"),
            "username": profile.get("username"),
            "display_name": profile.get("display_name"),
            "avatar_url": profile.get("avatar_url"),
            "bio": profile.get("bio"),
            "location": profile.get("location"),
            "is_verified": bool(profile.get("is_verified")),
            "is_online": bool(profile.get("is_online")),
            "followers_count": profile.get("followers_count", 0),
            "following_count": profile.get("following_count", 0),
            "posts_count": profile.get("posts_count", 0),
        }), 200
    except Exception as e:
        log_error("api_profile_summary_failed", error=str(e))
        return jsonify({"error": "Summary unavailable"}), 500


@profile_bp.route("/api/activity")
@login_required
def api_profile_activity():
    """Lightweight profile activity endpoint for lazy loading."""
    try:
        viewer = get_current_profile()
        if not viewer:
            return jsonify({"error": "Unauthorized"}), 401
        from services.profile_service import get_profile_activity
        activity = get_profile_activity(viewer["id"]) or {}
        return jsonify({
            "posts": activity.get("posts", []),
            "reels": activity.get("reels", []),
            "stories": activity.get("stories", []),
        }), 200
    except Exception as e:
        log_error("api_profile_activity_failed", error=str(e))
        return jsonify({"error": "Activity unavailable"}), 500


@profile_bp.route("/api/wallet-card")
@login_required
def api_profile_wallet_card():
    """Lightweight wallet card endpoint for lazy loading."""
    try:
        viewer = get_current_profile()
        if not viewer:
            return jsonify({"error": "Unauthorized"}), 401
        from services.profile_service import get_wallet_snapshot
        wallet = get_wallet_snapshot(viewer["id"]) or {}
        return jsonify({
            "coin_balance": wallet.get("coin_balance", 0),
            "gift_earnings": wallet.get("gift_earnings", 0),
            "pending_withdrawal": wallet.get("pending_withdrawal", 0),
        }), 200
    except Exception as e:
        log_error("api_profile_wallet_card_failed", error=str(e))
        return jsonify({"error": "Wallet unavailable"}), 500


@profile_bp.route("/api/creator-card")
@login_required
def api_profile_creator_card():
    """Lightweight creator tools endpoint for lazy loading."""
    try:
        viewer = get_current_profile()
        if not viewer:
            return jsonify({"error": "Unauthorized"}), 401
        from services.profile_service import get_creator_tools
        creator_tools = get_creator_tools(viewer["id"]) or {}
        return jsonify({
            "studio_enabled": creator_tools.get("studio_enabled", False),
            "creator_notes": creator_tools.get("creator_notes", ""),
            "featured_links": creator_tools.get("featured_links", []),
        }), 200
    except Exception as e:
        log_error("api_profile_creator_card_failed", error=str(e))
        return jsonify({"error": "Creator tools unavailable"}), 500


def _schedule_item(profile_id, content_type, caption, scheduled_at_str):
    import uuid
    from services.neon_service import write_query
    table = "chain_posts" if content_type == "post" else "chain_reels"
    item_id = str(uuid.uuid4())
    write_query(
        f"INSERT INTO {table} (id, profile_id, caption, scheduled_at, created_at) VALUES (%s, %s, %s, %s, now())",
        (item_id, profile_id, caption, scheduled_at_str),
    )
    return item_id


@profile_bp.route("/api/schedule/create", methods=["POST"])
@login_required
def api_schedule_create():
    viewer = get_current_profile()
    if not viewer:
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    content_type = request.form.get("content_type")
    caption = request.form.get("caption", "").strip()
    scheduled_at = request.form.get("scheduled_at")
    if content_type not in ("post", "reel"):
        return jsonify({"status": "error", "error": "content_type must be post or reel"}), 400
    if not caption:
        return jsonify({"status": "error", "error": "caption is required"}), 400
    if not scheduled_at:
        return jsonify({"status": "error", "error": "scheduled_at is required"}), 400
    try:
        item_id = _schedule_item(viewer["id"], content_type, caption, scheduled_at)
        return jsonify({"status": "ok", "item_id": item_id, "content_type": content_type, "scheduled_at": scheduled_at})
    except Exception as e:
        log_error("api_schedule_create_failed", error=str(e))
        return jsonify({"status": "error", "error": str(e)}), 500


@profile_bp.route("/api/scheduled")
@login_required
def api_scheduled_items():
    viewer = get_current_profile()
    if not viewer:
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    try:
        from services.neon_service import fast_query
        limit = min(int(request.args.get("limit", 20)), 50)
        posts = fast_query(
            "SELECT id, caption, scheduled_at, 'post' as content_type FROM chain_posts WHERE profile_id = %s AND scheduled_at IS NOT NULL AND deleted_at IS NULL ORDER BY scheduled_at ASC LIMIT %s",
            (viewer["id"], limit),
        )
        reels = fast_query(
            "SELECT id, caption, scheduled_at, 'reel' as content_type FROM chain_reels WHERE profile_id = %s AND scheduled_at IS NOT NULL AND deleted_at IS NULL ORDER BY scheduled_at ASC LIMIT %s",
            (viewer["id"], limit),
        )
        items = (posts or []) + (reels or [])
        items.sort(key=lambda x: x.get("scheduled_at") or "")
        return jsonify({"status": "ok", "items": items[:limit]})
    except Exception as e:
        log_error("api_scheduled_failed", error=str(e))
        return jsonify({"status": "error", "error": str(e)}), 500


@profile_bp.route("/api/current", methods=["GET"])
def api_current_profile():
    try:
        if not is_logged_in():
            return jsonify({"error": "Authentication required"}), 401
        profile = get_current_profile()
        if not profile:
            log_warning(
                "api_current_profile_missing",
                auth_user_id=session.get("auth_user_id") or session.get("user_id"),
                profile_id=session.get("profile_id"),
                email=session.get("auth_email") or session.get("email"),
            )
            return jsonify({"error": "Profile not found"}), 404
        return jsonify(profile), 200
    except Exception as error:
        log_error("api_current_profile_failed", error=str(error))
        return jsonify({"error": "Profile lookup failed"}), 500


@profile_bp.route("/avatar", methods=["POST"])
@login_required
def avatar_upload():
    viewer = get_current_profile()
    file_obj = request.files.get("avatar")
    try:
        ok, result = upload_profile_avatar(viewer["auth_user_id"], file_obj) if viewer and file_obj else (False, "No avatar file provided.")
    except Exception as error:
        log_warning("profile_avatar_upload_failed", profile_id=(viewer or {}).get("id"), error=str(error))
        ok, result = False, "Avatar upload failed. Please try again."
    if request.accept_mimetypes.best == "application/json" or request.is_json:
        return ({"status": "ok", "avatar_url": (result or {}).get("avatar_url")} if ok else {"error": result}), (200 if ok else 400)
    if ok:
        flash("Profile picture updated.", "success")
    else:
        flash(result, "error")
    return redirect(url_for("profile.edit_profile"))


@profile_bp.route("/cover", methods=["POST"])
@login_required
def cover_upload():
    viewer = get_current_profile()
    file_obj = request.files.get("cover")
    try:
        ok, result = upload_profile_cover(viewer["auth_user_id"], file_obj) if viewer and file_obj else (False, "No cover file provided.")
    except Exception as error:
        log_warning("profile_cover_upload_failed", profile_id=(viewer or {}).get("id"), error=str(error))
        ok, result = False, "Cover upload failed. Please try again."
    if request.accept_mimetypes.best == "application/json" or request.is_json:
        return ({"status": "ok", "cover_url": (result or {}).get("cover_url")} if ok else {"error": result}), (200 if ok else 400)
    if ok:
        flash("Cover photo updated.", "success")
    else:
        flash(result, "error")
    return redirect(url_for("profile.edit_profile"))


def _resolve_target_id(username):
    """Look up a profile_id from @username string."""
    p = get_profile_by_username(username)
    return p.get("id") if p else None


@profile_bp.route("/@<username>/follow", methods=["POST"])
@login_required
def follow(username):
    try:
        viewer = get_current_profile()
        target_id = _resolve_target_id(username)
        if viewer and target_id:
            result = follow_profile(viewer["id"], target_id)
            if result and result.get("success"):
                track_interaction_safe(viewer["id"], "profile", target_id, "follow" if result.get("following") else "unfollow", source_surface="profile")
    except Exception as error:
        log_warning("profile_follow_failed", username=username, error=str(error))
    return _redirect_back(username)


@profile_bp.route("/@<username>/like", methods=["POST"])
@login_required
def like(username):
    viewer = get_current_profile()
    target_id = _resolve_target_id(username)
    if viewer and target_id:
        like_profile(viewer["id"], target_id)
    return _redirect_back(username)


@profile_bp.route("/@<username>/favorite", methods=["POST"])
@login_required
def favorite(username):
    viewer = get_current_profile()
    target_id = _resolve_target_id(username)
    if viewer and target_id:
        favorite_profile(viewer["id"], target_id)
    return _redirect_back(username)


@profile_bp.route("/@<username>/report", methods=["POST"])
@login_required
def report(username):
    viewer = get_current_profile()
    target_id = _resolve_target_id(username)
    if viewer and target_id:
        report_profile(viewer["id"], target_id, reason=request.form.get("reason"))
        track_interaction_safe(viewer["id"], "profile", target_id, "report", source_surface="profile")
    return _redirect_back(username)


@profile_bp.route("/report/<profile_id>", methods=["POST"])
@login_required
def report_by_id(profile_id):
    viewer = get_current_profile()
    ok = False
    if viewer:
        ok = bool(report_profile(viewer["id"], profile_id, reason=request.form.get("reason")))
        if ok:
            track_interaction_safe(viewer["id"], "profile", profile_id, "report", source_surface="profile")
    return {"status": "ok" if ok else "setup", "profile_id": profile_id}, (200 if ok else 202)


@profile_bp.route("/@<username>/block", methods=["POST"])
@login_required
def block(username):
    viewer = get_current_profile()
    target_id = _resolve_target_id(username)
    if viewer and target_id:
        from services.moderation_engine import block_profile as _block
        if _block(viewer["id"], target_id):
            track_interaction_safe(viewer["id"], "profile", target_id, "block", source_surface="profile")
    return _redirect_back(username)


@profile_bp.route("/@<username>/premium")
def premium(username):
    viewer = get_current_profile()
    bundle = get_profile_bundle(username=username, viewer=viewer)
    if not bundle:
        return render_template("profile/not_found.html", username=username), 404
    return _render_profile_index(bundle["profile"], viewer=viewer, bundle=bundle)


@profile_bp.route("/@<username>/creator-tools")
@login_required
def creator_tools(username):
    viewer = get_current_profile()
    bundle = get_profile_bundle(username=username, viewer=viewer)
    if not bundle:
        return render_template("profile/not_found.html", username=username), 404
    profile = bundle.get("profile", {})
    creator_data = get_creator_dashboard_data(profile.get("id"))
    analytics = get_creator_analytics(profile.get("id"), days=30)
    wallet = get_wallet_snapshot(profile.get("id"))
    stats = get_profile_stats(profile.get("id"))
    try:
        from services.friend_service import list_friends
        friends = list_friends(profile.get("id"), limit=8)
    except Exception:
        friends = []
    schedule_count = _count_scheduled(profile.get("id"))
    return render_template(
        "profile/creator_tools.html",
        viewer=viewer, profile=profile, wallet=wallet, stats=stats,
        creator_data=creator_data, analytics=analytics, friends=friends,
        schedule_count=schedule_count, **bundle
    )


def _count_scheduled(profile_id):
    count = 0
    try:
        from services.neon_service import fast_query
        rows = fast_query(
            "SELECT COUNT(*) AS c FROM chain_posts WHERE profile_id = %s AND scheduled_at IS NOT NULL AND scheduled_at > now() AND deleted_at IS NULL",
            (profile_id,), default=[]
        )
        if rows: count += int(rows[0].get("c", 0) or 0)
        rows = fast_query(
            "SELECT COUNT(*) AS c FROM chain_reels WHERE profile_id = %s AND scheduled_at IS NOT NULL AND scheduled_at > now() AND deleted_at IS NULL",
            (profile_id,), default=[]
        )
        if rows: count += int(rows[0].get("c", 0) or 0)
    except Exception:
        pass
    return count


@profile_bp.route("/tab/<tab_name>")
@login_required
def tab_content(tab_name):
    viewer = get_current_profile()
    bundle = get_profile_bundle(profile_id=viewer.get("id"), viewer=viewer)
    template_map = {
        "stories": "profile/tabs/tab_stories.html",
        "messages": "profile/tabs/tab_messages.html",
        "calls": "profile/tabs/tab_calls.html",
        "dating": "profile/tabs/tab_dating.html",
        "wallet": "profile/tabs/tab_wallet.html",
        "notifications": "profile/tabs/tab_notifications.html",
    }
    tpl = template_map.get(tab_name)
    if not tpl:
        return '<div class="manager-empty"><i class="fas fa-exclamation-triangle"></i><p>Tab not found</p></div>'
    extra = {}
    if tab_name == "stories":
        try:
            from services.stories_service import get_stories_feed
            extra["stories"] = get_stories_feed(viewer.get("id"))
        except Exception:
            extra["stories"] = []
    elif tab_name == "wallet":
        extra["wallet_data"] = get_wallet_snapshot(viewer.get("id"))
        try:
            from services.wallet_service import get_wallet_transactions
            extra["recent_txns"] = get_wallet_transactions(viewer.get("id"), limit=5)
        except Exception:
            extra["recent_txns"] = []
    elif tab_name == "notifications":
        try:
            from services.notification_engine import list_notifications_tab, unread_count
            extra["notifications"] = list_notifications_tab(viewer.get("id"), tab="all", page=1, limit=10).get("items", [])
            extra["unread"] = unread_count(viewer.get("id"))
        except Exception:
            extra["notifications"] = []
            extra["unread"] = 0
    elif tab_name == "messages":
        try:
            from services.messaging_engine import list_threads
            extra["threads"] = list_threads(viewer.get("id"), limit=5).get("threads", [])
        except Exception:
            extra["threads"] = []
    elif tab_name == "calls":
        try:
            from services.call_service import list_recent_calls
            extra["calls"] = list_recent_calls(viewer.get("id"))
        except Exception:
            extra["calls"] = []
    elif tab_name == "dating":
        try:
            from services.dating_service import get_matches, get_dating_profile
            extra["dating_profile"] = get_dating_profile(viewer.get("id"))
            extra["matches"] = get_matches(viewer.get("id"), limit=6).get("items", [])
        except Exception:
            extra["dating_profile"] = {}
            extra["matches"] = []
    ctx = {"viewer": viewer, "profile": bundle.get("profile", viewer), "tab_name": tab_name}
    ctx.update(extra)
    return render_template(tpl, **ctx)


@profile_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    profile = _current_profile_or_session_fallback()
    if not profile:
        ok, result = bootstrap_profile_for_current_user()
        profile = result if ok and isinstance(result, dict) else get_current_profile()
        if not profile:
            return redirect(url_for("profile.onboarding"))
    if request.method == "POST":
        data = dict(request.form)
        avatar_file = request.files.get("avatar")
        if avatar_file and avatar_file.filename:
            res, err = upload_avatar(profile["id"], avatar_file)
            if res:
                data["avatar_url"] = res["public_url"]
                data["avatar_upload_id"] = res["upload_id"]
            else:
                flash(f"Avatar upload failed: {err}", "error")
        cover_file = request.files.get("cover")
        if cover_file and cover_file.filename:
            res, err = upload_cover(profile["id"], cover_file)
            if res:
                data["cover_url"] = res["public_url"]
                data["cover_upload_id"] = res["upload_id"]
            else:
                flash(f"Cover upload failed: {err}", "error")
        verification_file = request.files.get("verification")
        if verification_file and verification_file.filename:
            res, err = upload_verification_file(profile["id"], verification_file, upload_type="profile_verification")
            if res:
                data["verification_selfie_url"] = res.get("public_url") or res.get("file_path")
                data["verification_upload_id"] = res.get("upload_id")
            else:
                flash(f"Verification upload failed: {err}", "error")
        ok, result = update_profile_setup(profile["id"], data, current_profile=profile)
        if ok:
            _apply_profile_session(result if isinstance(result, dict) else profile, fallback_email=data.get("email"))
        # Save settings toggles (allow_messages, allow_video_calls, show_online_status, profile_visibility, call_ringtone)
        from services.supabase_safe import safe_insert, safe_update
        ringtone_val = (data.get("call_ringtone") or "").strip()
        if ringtone_val not in ("namvibe_classic", "soft_ring", "premium_beep", "digital_chime", "sunrise", "mellow_tone", "silent"):
            ringtone_val = "namvibe_classic"
        settings_payload = {
            "allow_messages": data.get("allow_messages") == "on",
            "allow_video_calls": data.get("allow_video_calls") == "on",
            "show_online_status": data.get("show_online_status") == "on",
            "profile_visibility": data.get("profile_visibility", "public"),
            "call_ringtone": ringtone_val,
            "allow_public_messages": data.get("allow_public_messages") == "on",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        existing_settings = get_profile_settings(profile["id"])["settings"]
        if existing_settings.get("id"):
            safe_update("chain_user_settings", settings_payload, eq={"id": existing_settings["id"]})
        else:
            safe_insert("chain_user_settings", {"profile_id": profile["id"], **settings_payload})
        # Also sync who_can_message on chain_profiles
        who_val = "everyone" if data.get("allow_public_messages") == "on" else "friends"
        from services.neon_service import execute as _neon_exec
        _neon_exec("UPDATE chain_profiles SET who_can_message = %s, updated_at = NOW() WHERE id = %s", (who_val, profile["id"]))
        if ok:
            flash("Profile updated.", "success")
            return redirect(url_for("profile.settings"))
        flash(result or "Profile could not be saved yet.", "error")
    profile_settings = get_profile_settings(profile["id"]) if profile.get("id") else {"settings": {}, "security": {}}
    return render_template("profile/settings.html", profile=profile, profile_settings=profile_settings["settings"], account_security=profile_settings["security"])


@profile_bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    profile = get_current_profile()
    if not profile:
        ok, result = bootstrap_profile_for_current_user()
        if not ok:
            session[K_PROFILE_WARNING] = True
            return render_template(
                "profile/onboarding.html",
                profile=_session_profile_stub(),
                form=_session_profile_stub(),
                error="Finishing your profile setup...",
                progress=0,
                setup_mode=True,
            ), 200
        profile = result if isinstance(result, dict) else None
        if not profile:
            profile = get_current_profile()
        if not profile:
            profile = _session_profile_stub()

    if profile and profile.get("id"):
        _apply_profile_session(profile)

    adult_state = is_adult_profile(profile)
    if adult_state is False:
        return render_template("auth/profile_error.html", error_detail="NamVibe is only available to users 18 and older."), 200

    if request.method == "POST":
        if not profile or not profile.get("id"):
            log_warning("onboarding_profile_unavailable_after_bootstrap")
            return render_template(
                "profile/onboarding.html",
                profile=_session_profile_stub(),
                form=request.form,
                error="We could not finish linking your profile yet. Please try again.",
                progress=0,
                setup_mode=True,
            ), 200
        data = dict(request.form)
        partial_step = data.get("partial_step")

        # Avatar Upload
        avatar_file = request.files.get("avatar") or request.files.get("camera_avatar")
        if avatar_file and avatar_file.filename:
            res, err = upload_avatar(profile["id"], avatar_file)
            if res:
                data["avatar_url"] = res["public_url"]
                data["avatar_upload_id"] = res["upload_id"]

        # Cover Upload
        cover_file = request.files.get("cover")
        if cover_file and cover_file.filename:
            res, err = upload_cover(profile["id"], cover_file)
            if res:
                data["cover_url"] = res["public_url"]
                data["cover_upload_id"] = res["upload_id"]

        # Map 'interests' and 'languages' from comma-separated strings to lists if needed
        if "interests" in data and isinstance(data["interests"], str):
            data["interests"] = [i.strip() for i in data["interests"].split(",") if i.strip()]
        if "languages" in data and isinstance(data["languages"], str):
            data["languages"] = [l.strip() for l in data["languages"].split(",") if l.strip()]

        ok, result = update_profile_setup(profile["id"], data, current_profile=profile)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json or partial_step:
            if ok and isinstance(result, dict):
                _apply_profile_session(result, fallback_email=data.get("email"))
            return jsonify({"status": "ok" if ok else "error", "message": "Profile updated" if ok else result})

        if ok:
            completed_profile = result if isinstance(result, dict) else profile
            _apply_profile_session(completed_profile, fallback_email=data.get("email"))
            flash("Profile updated.", "success")
            return redirect(url_for("profile.my_profile"))

        log_error("onboarding_profile_write_failed", error=result, profile_id=profile.get("id"), auth_user_id=profile.get("auth_user_id"))

        return render_template(
            "profile/onboarding.html",
            profile=profile,
            form=request.form,
            error=result or "Profile could not be saved yet. Please check the highlighted fields and try again.",
            progress=profile.get("profile_completion", 0),
            setup_mode=True,
        )

    return render_template("profile/onboarding.html", profile=profile, form=profile, progress=profile.get("profile_completion", 0), setup_mode=True)


@profile_bp.route("/verification", methods=["GET", "POST"])
@login_required
def verification():
    profile = _current_profile_or_session_fallback()
    if not profile:
        return redirect(url_for("auth.login", next=request.path))
    from services.profile_completion_service import calculate_profile_completion
    from services.pricing_config import VERIFICATION_FEES, get_verification_fee, coins_to_nad
    from services.supabase_safe import safe_insert, safe_select, safe_update

    # Check profile completion
    completion = calculate_profile_completion(profile)
    profile_complete = completion.get("percentage", 0) >= 55
    verification_type = request.form.get("verification_type", "blue")
    fee = get_verification_fee(verification_type) or get_verification_fee("blue")

    if request.method == "POST":
        # Step 1: Validate profile completion
        if not profile_complete:
            flash("Complete at least 55% of your profile before applying for verification.", "error")
            return redirect(url_for("profile.verification"))

        # Step 2: Process NVC payment for verification fee
        if fee["coins"] > 0:
            from services.wallet_service import get_or_create_wallet, debit_wallet
            wallet = get_or_create_wallet(profile["id"])
            available = wallet.get("balance_cents", 0)
            fee_cents = fee["coins"] * coins_to_nad(1)
            if available < fee_cents:
                nad_needed = fee_cents
                coins_needed = fee["coins"]
                flash(f"Insufficient balance. You need {coins_needed} NVC (N${nad_needed}) for {fee['label']}. Please deposit coins first.", "error")
                return redirect(url_for("profile.verification"))
            # Deduct fee
            tx = debit_wallet(
                profile["id"], fee_cents,
                description=f"{fee['label']} application fee ({fee['coins']} NVC)",
                transaction_type="verification_fee",
                reference_type="verification",
            )
            if not tx:
                flash("Payment processing failed. Please try again.", "error")
                return redirect(url_for("profile.verification"))
            payment_id = tx.get("transaction_id") or tx.get("id")
            # Record payment
            from services.neon_service import execute as neon_execute
            neon_execute(
                "INSERT INTO chain_verification_payments (profile_id, verification_type, coins_paid, nad_paid, transaction_id) VALUES (%s, %s, %s, %s, %s)",
                (profile["id"], verification_type, fee["coins"], fee_cents, payment_id),
                timeout_ms=5000,
            )

        # Step 3: Upload documents
        data = {}
        selfie_file = request.files.get("selfie")
        if selfie_file and selfie_file.filename:
            res, err = upload_verification_file(profile["id"], selfie_file, upload_type='verification_selfie')
            if res:
                data["selfie_url"] = res["public_url"] or res["file_path"]
                data["selfie_upload_id"] = res["upload_id"]
            else:
                flash(f"Selfie upload failed: {err}", "error")
                return redirect(url_for("profile.verification"))

        id_file = request.files.get("id_document")
        if id_file and id_file.filename:
            res, err = upload_verification_file(profile["id"], id_file, upload_type='verification_id')
            if res:
                data["id_document_url"] = res["public_url"] or res["file_path"]
                data["id_document_upload_id"] = res["upload_id"]
            else:
                flash(f"ID document upload failed: {err}", "error")
                return redirect(url_for("profile.verification"))

        if not data.get("selfie_upload_id") or not data.get("id_document_upload_id"):
            flash("Both selfie and ID document are required.", "error")
            return redirect(url_for("profile.verification"))

        # Step 4: Save verification request
        existing = safe_select("chain_user_verifications", filters={"profile_id": profile["id"]}, limit=1, order_by=None)
        payload = {
            "profile_id": profile["id"],
            "verification_status": "pending",
            "verification_type": verification_type,
            "selfie_url": data.get("selfie_url"),
            "selfie_upload_id": data.get("selfie_upload_id"),
            "id_document_url": data.get("id_document_url"),
            "id_document_upload_id": data.get("id_document_upload_id"),
            "profile_completed": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if existing:
            safe_update("chain_user_verifications", payload, eq={"id": existing[0]["id"]})
        else:
            payload["created_at"] = datetime.now(timezone.utc).isoformat()
            safe_insert("chain_user_verifications", payload)

        flash("Verification request submitted successfully.", "success")
        return redirect(url_for("profile.my_profile"))

    # GET: show verification page
    verification_request = (safe_select("chain_user_verifications", filters={"profile_id": profile["id"]}, limit=1, order_by=None) or [None])[0]
    return render_template(
        "profile/verification.html",
        profile=profile,
        verification=verification_request,
        completion=completion,
        profile_complete=profile_complete,
        verification_fees=VERIFICATION_FEES,
    )


@profile_bp.route("/security")
@login_required
def security():
    profile = _current_profile_or_session_fallback()
    if not profile:
        return redirect(url_for("auth.login", next=request.path))
    profile_id = profile.get("id")
    profile_settings = get_profile_settings(profile_id) if profile_id else {"settings": {}, "security": {}}
    verification = {"status": "none"}
    trust = {"trust_level": "new", "report_count": 0, "suspicious_score": 0}
    privacy = {
        "show_online_status": True,
        "show_last_seen": True,
    }
    devices = []
    events = []
    try:
        from services.verification_engine import get_verification_status
        if profile_id:
            verification = get_verification_status(profile_id) or verification
    except Exception as error:
        log_warning("profile_security_verification_failed", profile_id=profile_id, error=str(error))
    try:
        if profile_id:
            trust_summary = get_trust_summary(profile_id) or {}
            trust_score = trust_summary.get("trust") or {}
            trust_level = trust_summary.get("risk_level") or "new"
            trust = {
                "trust_level": "verified" if verification.get("status") == "approved" else trust_level,
                "report_count": _safe_number(trust_score.get("report_count")),
                "suspicious_score": _safe_number(trust_score.get("risk_score")),
            }
            privacy = get_privacy_settings(profile_id) or privacy
            devices = get_device_sessions(profile_id) or []
            events = get_security_events(profile_id, limit=20) or []
    except Exception as error:
        log_warning("profile_security_context_failed", profile_id=profile_id, error=str(error))
    return render_template(
        "profile/security.html",
        profile=profile,
        account_security=profile_settings.get("security", {}),
        verification=verification,
        trust=trust,
        privacy=privacy,
        devices=devices,
        events=events,
    )


@profile_bp.route("/security/set-password", methods=["POST"])
@login_required
def set_password():
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("profile.security"))
    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("profile.security"))
    ok, result = set_current_user_password(password)
    flash(result, "success" if ok else "error")
    return redirect(url_for("profile.security"))


@profile_bp.route("/activity")
@login_required
def activity():
    viewer = get_current_profile()
    bundle = get_profile_bundle(profile_id=viewer["id"], viewer=viewer)
    return render_template("profile/index.html", viewer=viewer, **bundle)


@profile_bp.route("/live")
@login_required
def my_live():
    return redirect(url_for("live.live_channels"))


@profile_bp.route("/posts")
@login_required
def my_posts():
    return redirect(url_for("profile.my_profile"))


@profile_bp.route("/wallet")
@login_required
def my_wallet():
    return redirect(url_for("wallet.index"))


@profile_bp.route("/notifications")
@login_required
def my_notifications():
    return redirect(url_for("notification_engine.index"))


@profile_bp.route("/creator/ai-assist", methods=["POST"])
@login_required
def ai_assist():
    from services.creator_ai_service import get_caption_suggestions, generate_trending_hashtags
    data = request.json or {}
    c_type = data.get("type", "reel")
    topic = data.get("topic", "lifestyle")

    captions = get_caption_suggestions(c_type, topic)
    hashtags = generate_trending_hashtags(topic)

    return jsonify({
        "captions": captions,
        "hashtags": hashtags
    })

@profile_bp.route("/privacy", methods=["GET"])
@login_required
def privacy_settings():
    profile = get_current_profile()
    privacy = get_profile_privacy(profile["id"]) if profile else {}
    return render_template("profile/privacy.html", profile=profile, privacy=privacy)


@profile_bp.route("/page/like/<page_id>", methods=["POST"])
@login_required
def like_page(page_id):
    profile = get_current_profile()
    from services.supabase_safe import safe_insert
    ok = safe_insert("chain_page_likes", {"profile_id": profile["id"], "page_id": page_id})
    return jsonify({"status": "ok" if ok else "error"})


@profile_bp.route("/page/unlike/<page_id>", methods=["POST"])
@login_required
def unlike_page(page_id):
    profile = get_current_profile()
    from services.supabase_safe import write_query
    sql = "DELETE FROM chain_page_likes WHERE profile_id = %s AND page_id = %s"
    ok = write_query(sql, (profile["id"], page_id))
    return jsonify({"status": "ok" if ok else "error"})


@profile_bp.route("/convert-to-page", methods=["POST"])
@login_required
def convert_to_page():
    profile = get_current_profile()
    from services.supabase_safe import safe_update
    ok = safe_update("chain_profiles", {"is_page": True}, eq={"id": profile["id"]})
    return jsonify({"status": "ok" if ok else "error"})


@profile_bp.route("/settings/privacy", methods=["POST"])
@login_required
def update_privacy():
    profile = get_current_profile()
    visibility = request.form.get("visibility", "public")
    allow_audio = request.form.get("allow_audio") == "on"
    allow_video = request.form.get("allow_video") == "on"

    from services.supabase_safe import safe_update
    payload = {
        "profile_visibility": visibility,
        "allow_audio_calls": allow_audio,
        "allow_video_calls": allow_video,
        "allow_group_calls": request.form.get("allow_group_calls") == "on",
        "allow_conference_calls": request.form.get("allow_conference_calls") == "on",
        "allow_add_to_call": request.form.get("allow_add_to_call") == "on",
        "allow_unknown_callers": request.form.get("allow_unknown_callers") == "on",
        "call_quality_audio": request.form.get("call_quality_audio", "auto"),
        "call_quality_video": request.form.get("call_quality_video", "auto"),
        "call_ringtone": request.form.get("call_ringtone", "chain_classic"),
        "call_vibration": request.form.get("call_vibration") == "on",
        "auto_answer_headset": request.form.get("auto_answer_headset") == "on",
        "speaker_default": request.form.get("speaker_default") == "on",
        "noise_suppression": request.form.get("noise_suppression") == "on",
        "echo_cancellation": request.form.get("echo_cancellation") == "on",
        "hd_video": request.form.get("hd_video") == "on",
        "save_call_history": request.form.get("save_call_history") == "on"
    }
    ok = safe_update("chain_profiles", payload, eq={"id": profile["id"]})
    flash("Privacy settings updated.", "success")
    return redirect(url_for("profile.my_profile"))

@profile_bp.route("/<user_id>/follow", methods=["POST"])
@login_required
def toggle_follow(user_id):
    """
    Production-grade follow/unfollow toggle.
    Returns JSON for AJAX frontend.
    """
    from services.neon_service import write_query, fast_query

    viewer = get_current_profile()
    if not viewer:
        return jsonify({"error": "Unauthorized"}), 401

    target_id = user_id
    if user_id.startswith("@"):
        t_rows = fast_query("SELECT id FROM chain_profiles WHERE username = %s LIMIT 1", [user_id[1:]])
        if not t_rows: return jsonify({"error": "User not found"}), 404
        target_id = t_rows[0]["id"]

    if viewer["id"] == target_id:
        return jsonify({"error": "Cannot follow yourself"}), 400

    # Toggle Logic
    existing = fast_query(
        "SELECT 1 FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s",
        [viewer["id"], target_id]
    )

    if existing:
        write_query(
            "DELETE FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s",
            [viewer["id"], target_id]
        )
        following = False
    else:
        write_query(
            "INSERT INTO chain_follows (follower_profile_id, following_profile_id, created_at) VALUES (%s, %s, NOW())",
            [viewer["id"], target_id]
        )
        following = True

    # Recount for response
    counts = fast_query(
        "SELECT COUNT(*) as count FROM chain_follows WHERE following_profile_id = %s",
        [target_id]
    )[0]

    return jsonify({
        "status": "success",
        "following": following,
        "followers_count": counts["count"]
    })

# ── Posts Manager Routes ──────────────────────────────────────────────

@profile_bp.route("/api/posts/<post_id>/visibility", methods=["POST"])
@login_required
def api_post_visibility(post_id):
    profile = get_current_profile()
    visibility = request.json.get("visibility", "public") if request.is_json else request.form.get("visibility", "public")
    allowed = {"public", "followers", "friends", "private"}
    if visibility not in allowed:
        return jsonify({"error": "Invalid visibility"}), 400
    ok = update_post_visibility(post_id, profile["id"], visibility)
    invalidate_profile_cache(profile["id"])
    return jsonify({"status": "ok" if ok else "error"})

@profile_bp.route("/api/posts/<post_id>/comments-toggle", methods=["POST"])
@login_required
def api_post_comments_toggle(post_id):
    profile = get_current_profile()
    row = fetch_one("SELECT comments_enabled FROM chain_posts WHERE id = %s AND profile_id = %s",
                     (post_id, profile["id"]))
    enabled = not bool(row["comments_enabled"]) if row else True
    ok = toggle_post_comments(post_id, profile["id"], enabled)
    return jsonify({"status": "ok" if ok else "error", "comments_enabled": enabled if ok else None})

@profile_bp.route("/api/posts/<post_id>/share-toggle", methods=["POST"])
@login_required
def api_post_share_toggle(post_id):
    profile = get_current_profile()
    row = fetch_one("SELECT sharing_enabled FROM chain_posts WHERE id = %s AND profile_id = %s",
                     (post_id, profile["id"]))
    enabled = not bool(row["sharing_enabled"]) if row else True
    ok = toggle_post_sharing(post_id, profile["id"], enabled)
    return jsonify({"status": "ok" if ok else "error", "sharing_enabled": enabled if ok else None})

@profile_bp.route("/api/posts/<post_id>/pin", methods=["POST"])
@login_required
def api_post_pin(post_id):
    profile = get_current_profile()
    row = fetch_one("SELECT is_pinned FROM chain_posts WHERE id = %s AND profile_id = %s",
                     (post_id, profile["id"]))
    pinned = not bool(row["is_pinned"]) if row else True
    ok = toggle_post_pin(post_id, profile["id"], pinned)
    invalidate_profile_cache(profile["id"])
    return jsonify({"status": "ok" if ok else "error", "pinned": pinned if ok else None})

@profile_bp.route("/api/posts/<post_id>", methods=["DELETE"])
@login_required
def api_post_delete(post_id):
    profile = get_current_profile()
    ok = delete_post(post_id, profile["id"])
    invalidate_profile_cache(profile["id"])
    return jsonify({"status": "ok" if ok else "error"})

@profile_bp.route("/api/posts", methods=["GET"])
@login_required
def api_my_posts():
    profile = get_current_profile()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    visibility = request.args.get("visibility", "all")
    result = get_profile_posts(profile["id"], page=page, per_page=per_page, visibility=visibility)
    return jsonify(result)

@profile_bp.route("/@<username>/posts", methods=["GET"])
def view_posts(username):
    viewer = get_current_profile()
    profile = get_profile_by_username(username) if username else None
    if not profile:
        return render_template("profile/not_found.html", username=username), 404
    page = request.args.get("page", 1, type=int)
    result = get_profile_posts(profile["id"], page=page, per_page=20)
    return render_template("profile/posts.html", profile=profile, viewer=viewer, posts=result.get("posts", []), pagination=result)

# ── Reels Manager Routes ──────────────────────────────────────────────

@profile_bp.route("/api/reels/<reel_id>/visibility", methods=["POST"])
@login_required
def api_reel_visibility(reel_id):
    profile = get_current_profile()
    visibility = request.json.get("visibility", "public") if request.is_json else request.form.get("visibility", "public")
    allowed = {"public", "followers", "friends", "private"}
    if visibility not in allowed:
        return jsonify({"error": "Invalid visibility"}), 400
    ok = update_reel_visibility(reel_id, profile["id"], visibility)
    invalidate_profile_cache(profile["id"])
    return jsonify({"status": "ok" if ok else "error"})

@profile_bp.route("/api/reels/<reel_id>/comments-toggle", methods=["POST"])
@login_required
def api_reel_comments_toggle(reel_id):
    profile = get_current_profile()
    row = fetch_one("SELECT comments_enabled FROM chain_reels WHERE id = %s AND profile_id = %s",
                     (reel_id, profile["id"]))
    enabled = not bool(row["comments_enabled"]) if row else True
    ok = toggle_reel_comments(reel_id, profile["id"], enabled)
    return jsonify({"status": "ok" if ok else "error", "comments_enabled": enabled if ok else None})

@profile_bp.route("/api/reels/<reel_id>/pin", methods=["POST"])
@login_required
def api_reel_pin(reel_id):
    profile = get_current_profile()
    row = fetch_one("SELECT is_pinned FROM chain_reels WHERE id = %s AND profile_id = %s",
                     (reel_id, profile["id"]))
    pinned = not bool(row["is_pinned"]) if row else True
    ok = toggle_reel_pin(reel_id, profile["id"], pinned)
    invalidate_profile_cache(profile["id"])
    return jsonify({"status": "ok" if ok else "error", "pinned": pinned if ok else None})

@profile_bp.route("/api/reels/<reel_id>/share-toggle", methods=["POST"])
@login_required
def api_reel_share_toggle(reel_id):
    profile = get_current_profile()
    row = fetch_one("SELECT sharing_enabled FROM chain_reels WHERE id = %s AND profile_id = %s",
                     (reel_id, profile["id"]))
    enabled = not bool(row["sharing_enabled"]) if row else True
    ok = toggle_reel_sharing(reel_id, profile["id"], enabled)
    return jsonify({"status": "ok" if ok else "error", "sharing_enabled": enabled if ok else None})

@profile_bp.route("/api/reels/<reel_id>", methods=["DELETE"])
@login_required
def api_reel_delete(reel_id):
    profile = get_current_profile()
    ok = delete_reel(reel_id, profile["id"])
    invalidate_profile_cache(profile["id"])
    return jsonify({"status": "ok" if ok else "error"})

@profile_bp.route("/api/reels/analytics/<reel_id>", methods=["GET"])
@login_required
def api_reel_analytics(reel_id):
    profile = get_current_profile()
    analytics = get_reel_analytics(reel_id, profile["id"])
    return jsonify(analytics)

@profile_bp.route("/api/reels", methods=["GET"])
@login_required
def api_my_reels():
    profile = get_current_profile()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    reel_type = request.args.get("type", "own")
    result = get_profile_reels(profile["id"], page=page, per_page=per_page, reel_type=reel_type)
    return jsonify(result)

@profile_bp.route("/@<username>/reels", methods=["GET"])
def view_reels(username):
    viewer = get_current_profile()
    profile = get_profile_by_username(username) if username else None
    if not profile:
        return render_template("profile/not_found.html", username=username), 404
    page = request.args.get("page", 1, type=int)
    reel_type = request.args.get("type", "own")
    result = get_profile_reels(profile["id"], page=page, per_page=20, reel_type=reel_type)
    return render_template("profile/reels.html", profile=profile, viewer=viewer, reels=result.get("reels", []), pagination=result)

# ── Followers / Following / Friends Routes Moved to social_routes.py ──

# ── Privacy Settings Routes ──────────────────────────────────────────

@profile_bp.route("/settings/privacy-advanced", methods=["POST"])
@login_required
def update_privacy_advanced():
    profile = get_current_profile()
    allowed_form_keys = (
        "who_can_follow", "who_can_message", "who_can_call",
        "who_can_view_posts", "who_can_view_reels",
        "who_can_see_posts", "who_can_see_reels", "who_can_see_stories",
        "who_can_see_followers", "who_can_see_following",
        "who_can_send_friend_requests", "who_can_follow_me", "who_can_message_me",
        "profile_visibility", "visibility",
    )
    data = {}
    for key in allowed_form_keys:
        val = request.form.get(key)
        if val is not None:
            data[key] = val
    data["require_coins_to_follow"] = request.form.get("require_coins_to_follow") == "on"
    data["premium_only_follow"] = request.form.get("premium_only_follow") == "on"
    ok = update_profile_privacy(profile["id"], data)
    invalidate_profile_cache(profile["id"])
    flash("Privacy settings updated.", "success")
    return redirect(url_for("profile.privacy_settings"))


# ── Following Mute Routes ────────────────────────────────────────────

@profile_bp.route("/command-center")
@login_required
def command_center():
    viewer = get_current_profile()
    if not viewer:
        return redirect(url_for("auth.login"))
    stats = {}
    try:
        raw = get_profile_stats(viewer["id"])
        stats = {
            "posts": raw.get("posts_count") or raw.get("posts", 0),
            "reels": raw.get("reels_count") or raw.get("reels", 0),
            "followers": raw.get("followers_count") or raw.get("followers", 0),
            "following": raw.get("following_count") or raw.get("following", 0),
            "friends": raw.get("friends_count") or raw.get("friends", 0),
        }
    except Exception:
        pass
    return render_template("profile/command_center.html", profile=viewer, viewer=viewer, stats=stats)


@profile_bp.route("/@<username>/likes")
def view_likes(username):
    viewer = get_current_profile()
    profile = get_profile_by_username(username)
    if not profile:
        return render_template("profile/not_found.html", username=username), 404
    page = request.args.get("page", 1, type=int)
    result = get_profile_posts(profile["id"], page=page, per_page=20, visibility="all")
    return render_template("profile/posts.html", profile=profile, viewer=viewer,
                           posts=result.get("posts", []), pagination=result)


@profile_bp.route("/@<username>/views")
def view_views(username):
    viewer = get_current_profile()
    profile = get_profile_by_username(username)
    if not profile:
        return render_template("profile/not_found.html", username=username), 404
    stats = {}
    try:
        raw = get_profile_stats(profile["id"])
        stats = {
            "posts": raw.get("posts_count") or raw.get("posts", 0),
            "reels": raw.get("reels_count") or raw.get("reels", 0),
            "followers": raw.get("followers_count") or raw.get("followers", 0),
            "following": raw.get("following_count") or raw.get("following", 0),
            "friends": raw.get("friends_count") or raw.get("friends", 0),
        }
    except Exception:
        pass
    return render_template("profile/command_center.html", profile=profile, viewer=viewer, stats=stats)


def _normalize_business_hours(form):
    """Build a validated JSONB-safe hours dict from flat form fields."""
    import re
    HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
    ALLOWED_DAYS = {"monday","tuesday","wednesday","thursday","friday","saturday","sunday"}
    hours = {}
    for day in ALLOWED_DAYS:
        open_time = (form.get(f"hours_{day}_open") or "").strip()
        close_time = (form.get(f"hours_{day}_close") or "").strip()
        is_closed = form.get(f"hours_{day}_closed") == "on"
        day_entry = {"closed": is_closed}
        if is_closed:
            day_entry["open"] = ""
            day_entry["close"] = ""
        else:
            if open_time and HHMM.match(open_time):
                day_entry["open"] = open_time
            else:
                day_entry["open"] = ""
            if close_time and HHMM.match(close_time):
                day_entry["close"] = close_time
            else:
                day_entry["close"] = ""
        if day_entry.get("open") or day_entry.get("close") or is_closed:
            hours[day] = day_entry
    return hours


@profile_bp.route("/business/api/<page_id>/update", methods=["POST"])
@login_required
def business_page_update(page_id):
    viewer = get_current_profile()
    try:
        from services.neon_service import write_query
        from services.supabase_safe import safe_update
        data = {}
        for key in ("name", "description", "website", "location", "contact_email", "contact_phone", "category"):
            val = request.form.get(key)
            if val is not None:
                data[key] = val
        logo = request.files.get("logo")
        if logo and logo.filename:
            from services.content_service import save_media_file
            media, error = save_media_file(logo, upload_type="image", profile_id=page_id)
            if media and isinstance(media, dict):
                data["logo_url"] = media.get("public_url") or media.get("url")
        cover = request.files.get("cover")
        if cover and cover.filename:
            from services.content_service import save_media_file
            media, error = save_media_file(cover, upload_type="image", profile_id=page_id)
            if media and isinstance(media, dict):
                data["cover_url"] = media.get("public_url") or media.get("url")
        if data:
            safe_update("chain_profiles", data, eq={"id": page_id})
        hours = _normalize_business_hours(request.form)
        if hours:
            from services.business_page_service import update_business_profile
            update_business_profile(page_id, opening_hours=hours)
        flash("Business page updated.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(f"/profile/business/{page_id}?tab=settings")


@profile_bp.route("/business/<page_id>")
@login_required
def business_page(page_id):
    viewer = get_current_profile()
    tab = request.args.get("tab", "overview")
    try:
        from services.neon_service import fast_query
        rows = fast_query("SELECT * FROM chain_pages WHERE id = %s LIMIT 1", (page_id,), default=[])
        page = rows[0] if rows else None
        if not page:
            rows = fast_query(
                "SELECT * FROM chain_profiles WHERE id = %s AND (account_kind = 'business' OR account_kind = 'creator' OR account_kind = 'organization' OR is_page = true) LIMIT 1",
                (page_id,), default=[]
            )
            page = rows[0] if rows else None
        if not page:
            return render_template("profile/not_found.html", username=""), 404
        promotions = fast_query(
            "SELECT * FROM chain_campaigns WHERE profile_id = %s ORDER BY created_at DESC",
            (page_id,), default=[]
        )
        page["promotions"] = promotions
        hours_raw = fast_query(
            "SELECT hours FROM chain_business_hours WHERE profile_id = %s",
            (page_id,), default=[]
        )
        page["hours"] = hours_raw[0]["hours"] if hours_raw else {}
        is_following = bool(
            fast_query(
                "SELECT 1 FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s LIMIT 1",
                (viewer["id"], page_id), default=[]
            )
        )
        stats = fast_query(
            "SELECT COUNT(*) AS followers FROM chain_follows WHERE following_profile_id = %s",
            (page_id,), default=[{"followers": 0}]
        )
        followers_count = int(stats[0]["followers"]) if stats else 0
        return render_template(
            "business/page.html",
            page=page, viewer=viewer, is_following=is_following,
            tab=tab, stats={"followers": followers_count},
        )
    except Exception as e:
        return f"Error loading business page: {str(e)}", 500


@profile_bp.route("/@<username>/score")
def view_score(username):
    viewer = get_current_profile()
    profile = get_profile_by_username(username)
    if not profile:
        return render_template("profile/not_found.html", username=username), 404
    return render_template("profile/command_center.html", profile=profile, viewer=viewer)


# ── Security Routes ─────────────────────────────────────────────────────

@profile_bp.route("/security/change-email", methods=["POST"])
@login_required
def security_change_email():
    profile = get_current_profile()
    new_email = request.form.get("new_email", "").strip()
    password = request.form.get("password", "")
    if not new_email or "@" not in new_email:
        flash("Invalid email address.", "error")
        return redirect(url_for("profile.security"))
    try:
        from services.supabase_safe import safe_update
        ok = safe_update("chain_profiles", {"email": new_email}, eq={"id": profile["id"]})
        if ok:
            session["auth_email"] = new_email
            flash("Email updated successfully.", "success")
        else:
            flash("Failed to update email.", "error")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("profile.security"))


@profile_bp.route("/security/change-phone", methods=["POST"])
@login_required
def security_change_phone():
    profile = get_current_profile()
    new_phone = request.form.get("new_phone", "").strip()
    password = request.form.get("password", "")
    if not new_phone:
        flash("Invalid phone number.", "error")
        return redirect(url_for("profile.security"))
    try:
        from services.supabase_safe import safe_update
        ok = safe_update("chain_profiles", {"phone": new_phone}, eq={"id": profile["id"]})
        flash("Phone number updated successfully." if ok else "Failed to update phone number.", "success" if ok else "error")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("profile.security"))


@profile_bp.route("/security/request-data", methods=["POST"])
@login_required
def security_request_data():
    profile = get_current_profile()
    try:
        from services.neon_service import fast_query, write_query
        from datetime import datetime, timezone
        import json
        data_export = {
            "profile": profile,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }
        write_query(
            "INSERT INTO chain_data_requests (profile_id, data_export, status, created_at) VALUES (%s, %s, 'pending', NOW())",
            (profile["id"], json.dumps(data_export)),
            timeout_ms=3000,
        )
        flash("Data export requested. You will be notified when it is ready.", "success")
    except Exception as e:
        flash(f"Error requesting data: {str(e)}", "error")
    return redirect(url_for("profile.security"))


@profile_bp.route("/security/delete-account", methods=["POST"])
@login_required
def security_delete_account():
    profile = get_current_profile()
    password = request.form.get("password", "")
    if len(password) < 8:
        flash("Password required to delete account.", "error")
        return redirect(url_for("profile.security"))
    try:
        from services.supabase_safe import safe_update
        ok = safe_update("chain_profiles", {
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "is_active": False,
            "username": f"deleted_{profile['id'][:8]}",
        }, eq={"id": profile["id"]})
        if ok:
            clear_auth_session()
            flash("Account deleted.", "success")
            return redirect(url_for("auth.login"))
        flash("Failed to delete account.", "error")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("profile.security"))


# ─── Profile 2026 API Endpoints ───

@profile_bp.route("/api/<target>/overview")
def api_profile_overview(target):
    try:
        viewer = get_current_profile() if (session.get("profile_id") or session.get("user_id")) else None
        viewer_id = viewer.get("id") if viewer else None
        from services.profile_2026_service import get_profile_2026, emit_profile_viewed
        data = get_profile_2026(viewer_id, target)
        if data.get("ok"):
            emit_profile_viewed(viewer_id, data.get("id"))
        return jsonify(data)
    except Exception as e:
        log_error("api_profile_overview_error", target=target, error=str(e))
        return jsonify({"ok": False, "error": str(e)})


@profile_bp.route("/api/<target>/content")
def api_profile_content(target):
    try:
        viewer = get_current_profile() if (session.get("profile_id") or session.get("user_id")) else None
        viewer_id = viewer.get("id") if viewer else None
        section = request.args.get("section", "posts")
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 12))
        from services.profile_2026_service import get_profile_content_section
        data = get_profile_content_section(viewer_id, target, section, page, per_page)
        return jsonify(data)
    except Exception as e:
        log_error("api_profile_content_error", target=target, error=str(e))
        return jsonify({"ok": False, "error": str(e)})


@profile_bp.route("/api/<target>/reels")
def api_profile_reels(target):
    try:
        viewer = get_current_profile() if (session.get("profile_id") or session.get("user_id")) else None
        viewer_id = viewer.get("id") if viewer else None
        page = int(request.args.get("page", 1))
        from services.profile_2026_service import get_profile_content_section
        data = get_profile_content_section(viewer_id, target, "reels", page, 12)
        return jsonify(data)
    except Exception as e:
        log_error("api_profile_reels_error", target=target, error=str(e))
        return jsonify({"ok": False, "error": str(e)})


@profile_bp.route("/api/<target>/stories")
def api_profile_stories(target):
    try:
        viewer = get_current_profile() if (session.get("profile_id") or session.get("user_id")) else None
        viewer_id = viewer.get("id") if viewer else None
        from services.profile_2026_service import get_profile_content_section
        data = get_profile_content_section(viewer_id, target, "stories", 1, 20)
        return jsonify(data)
    except Exception as e:
        log_error("api_profile_stories_error", target=target, error=str(e))
        return jsonify({"ok": False, "error": str(e)})


@profile_bp.route("/api/<target>/gallery")
def api_profile_gallery(target):
    try:
        viewer = get_current_profile() if (session.get("profile_id") or session.get("user_id")) else None
        viewer_id = viewer.get("id") if viewer else None
        page = int(request.args.get("page", 1))
        from services.profile_2026_service import get_profile_content_section
        data = get_profile_content_section(viewer_id, target, "gallery", page, 12)
        return jsonify(data)
    except Exception as e:
        log_error("api_profile_gallery_error", target=target, error=str(e))
        return jsonify({"ok": False, "error": str(e)})


@profile_bp.route("/api/<target>/live")
def api_profile_live(target):
    try:
        viewer = get_current_profile() if (session.get("profile_id") or session.get("user_id")) else None
        viewer_id = viewer.get("id") if viewer else None
        from services.profile_2026_service import get_profile_content_section
        data = get_profile_content_section(viewer_id, target, "live", 1, 10)
        return jsonify(data)
    except Exception as e:
        log_error("api_profile_live_error", target=target, error=str(e))
        return jsonify({"ok": False, "error": str(e)})


@profile_bp.route("/api/theme", methods=["POST"])
@login_required
def api_profile_theme():
    """Save the user's selected profile theme."""
    viewer = get_current_profile()
    if not viewer:
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.json or {}
    theme = data.get("theme", "default")
    allowed = {"default", "neon", "diamond", "royal", "crystal", "ocean", "sunset", "emerald", "galaxy", "rose", "minimal"}
    if theme not in allowed:
        return jsonify({"status": "error", "error": "Invalid theme"}), 400
    try:
        from services.neon_service import write_query
        write_query("UPDATE chain_profiles SET profile_theme = %s WHERE id = %s", (theme, viewer["id"]))
        return jsonify({"status": "ok", "theme": theme})
    except Exception as e:
        log_error("api_profile_theme_error", error=str(e))
        return jsonify({"status": "error", "error": str(e)}), 500


@profile_bp.route("/api/<target>/activity")
def api_profile_activity_target(target):
    try:
        viewer = get_current_profile() if (session.get("profile_id") or session.get("user_id")) else None
        viewer_id = viewer.get("id") if viewer else None
        page = int(request.args.get("page", 1))
        from services.profile_2026_service import get_profile_content_section
        data = get_profile_content_section(viewer_id, target, "activity", page, 20)
        return jsonify(data)
    except Exception as e:
        log_error("api_profile_activity_error", target=target, error=str(e))
        return jsonify({"ok": False, "error": str(e)})


@profile_bp.route("/api/ringtone", methods=["GET", "POST"])
@login_required
def api_ringtone():
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        ringtone = (data.get("ringtone") or "").strip()
        valid = ("namvibe_classic", "soft_ring", "premium_beep", "digital_chime", "sunrise", "mellow_tone", "silent")
        if ringtone not in valid:
            return jsonify({"ok": False, "error": "invalid_ringtone"}), 400
        from services.supabase_safe import safe_update, safe_insert
        existing = get_profile_settings(profile["id"])["settings"]
        payload = {"call_ringtone": ringtone, "updated_at": datetime.now(timezone.utc).isoformat()}
        if existing.get("id"):
            safe_update("chain_user_settings", payload, eq={"id": existing["id"]})
        else:
            safe_insert("chain_user_settings", {"profile_id": profile["id"], **payload})
        return jsonify({"ok": True, "ringtone": ringtone})

    # GET: return current ringtone + URL
    ringtone = "namvibe_classic"
    settings = get_profile_settings(profile["id"])["settings"]
    if settings and settings.get("call_ringtone"):
        ringtone = settings["call_ringtone"]
    ringtone_url = url_for("static", filename=f"ringtones/{ringtone}.mp3") if ringtone != "silent" else None
    return jsonify({
        "ok": True,
        "ringtone": ringtone,
        "ringtone_url": ringtone_url,
        "available": {
            "namvibe_classic": url_for("static", filename="ringtones/namvibe_classic.mp3"),
            "soft_ring": url_for("static", filename="ringtones/soft_ring.mp3"),
            "premium_beep": url_for("static", filename="ringtones/premium_beep.mp3"),
            "digital_chime": url_for("static", filename="ringtones/digital_chime.mp3"),
            "sunrise": url_for("static", filename="ringtones/sunrise.mp3"),
            "mellow_tone": url_for("static", filename="ringtones/mellow_tone.mp3"),
            "silent": None,
        }
    })
