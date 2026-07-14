import os

def _apply_async_monkey_patch():
    if os.getenv("CHAIN_ASYNC_PATCHED") == "1":
        return

    async_worker = (os.getenv("CHAIN_GUNICORN_WORKER") or "").strip().lower()
    if async_worker == "eventlet":
        try:
            import eventlet
            eventlet.monkey_patch()
            os.environ["CHAIN_ASYNC_PATCHED"] = "1"
        except ImportError:
            pass
        return

    try:
        import gevent.monkey
        gevent.monkey.patch_all()
        os.environ["CHAIN_ASYNC_PATCHED"] = "1"
    except ImportError:
        pass


_apply_async_monkey_patch()

import hmac
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from flask import Flask, flash, g, jsonify, make_response, redirect, render_template, request, session, send_from_directory, url_for
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from engines.cache_engine import init_cache
from engines.performance_engine import timed
from engines.scheduler_engine import init_scheduler
from services.env_service import get_env, load_project_env

load_project_env()

from api_routes.auth_routes import auth_bp
from api_routes.profile_routes import profile_bp
from api_routes.dashboard_routes import dashboard_bp
from api_routes.public_routes import public_bp
from api_routes.matching_routes import matching_bp
from api_routes.dating_routes import dating_bp
from api_routes.message_routes import message_bp
from api_routes.messaging_routes import messaging_api_bp
from api_routes.call_routes import call_bp, messages_call_bp, api_calls_bp
from api_routes.notification_routes import notification_engine_bp
from api_routes.wallet_routes import wallet_bp
from api_routes.admin_routes import admin_bp, developer_bp
from api_routes.discovery_routes import discovery_bp
from api_routes.activity_routes import activity_bp
from api_routes.search_routes import search_api_bp, search_bp
from api_routes.moderation_routes import moderation_bp
from api_routes.status_routes import status_bp
from api_routes.stories_v2_routes import stories_bp as stories_v2_bp
from api_routes.live_media_routes import live_media_bp
from api_routes.realtime_routes import realtime_bp
from api_routes.reels_routes import reels_bp
from api_routes.presence_routes import presence_bp
from api_routes.safety_routes import safety_bp
from api_routes.admin_safety_routes import admin_safety_bp
from api_routes.system_routes import system_bp
from api_routes.founder_routes import founder_bp
from api_routes.production_routes import production_bp
from api_routes.feed_routes import feed_bp
from api_routes.homepage_api import homepage_api_bp, feed_preload_bp
from api_routes.verification_routes import verification_bp
from api_routes.content_controls_routes import content_controls_bp
from api_routes.mobile_api_routes import mobile_api_bp
from api_routes.engagement_routes import engagement_bp
from api_routes.marketplace_routes import marketplace_bp
from api_routes.creator_routes import creator_bp
from api_routes.creator_studio_routes import studio_bp
from api_routes.social_routes import social_api_bp, social_bp
from api_routes.post_routes import post_bp, media_bp
from api_routes.metrics_routes import metrics_bp
from api_routes.push_routes import push_bp

from api_routes.security_routes import security_bp
from api_routes.privacy_routes import privacy_api_bp
from api_routes.group_call_routes import group_call_bp
from api_routes.push_notification_routes import push_notifications_api_bp
from api_routes.encryption_routes import encryption_bp
from api_routes.config_routes import config_bp
from api_routes.notification_center_routes import notification_center_bp
from api_routes.ai_routes import ai_bp
from api_routes.performance_routes import performance_bp
from api_routes.dev_diagnostics_routes import dev_bp as dev_diagnostics_bp
from api_routes.explore_routes import explore_bp
from api_routes.comments_routes import comments_bp
from api_routes.friend_routes import friend_bp
from api_routes.contacts_routes import contacts_bp, contacts_api_bp
from api_routes.inbox_routes import inbox_bp
from api_routes.follow_request_routes import follow_request_api_bp
from api_routes.gallery_routes import gallery_bp
from api_routes.social_graph_routes import social_graph_bp, profile_extra_bp
from api_routes.verification_admin_routes import verification_admin_bp
from api_routes.ad_admin_routes import ad_admin_bp
from api_routes.advertising_routes import advertising_bp
from api_routes.rpromo_routes import rpromo_bp
from api_routes.live_routes import register_live_routes
from api_routes.support_routes import support_bp, support_page_bp
from api_routes.connecting_you_routes import register_connecting_you_routes
from api_v1 import BLUEPRINTS as api_v1_blueprints

from services.homepage_service import get_homepage_data, build_homepage_payload, build_tiktok_home_payload
from services.homepage_phase141_service import (
    fetch_stories_v2,
    fetch_reels_v2,
    fetch_posts_v2,
    fetch_live_rooms_v2,
    fetch_suggested_people_v2,
    fetch_profiles_batch,
)
from services.homepage_warmup_service import warm_homepage_cache
from services.homepage_cache_service import get_full, HOMEPAGE_TTL_SECONDS
from services.cache_service import set as cache_set
from services.content_service import hashtag_links
from services.profile_service import get_current_profile, get_profile_by_username
from services.notification_service import get_my_notifications
from services.auth_service import get_current_user, refresh_chain_session
from api_routes.profile_routes import login_required
from services.neon_service import get_neon_health, get_pool_status, prime_neon_runtime, fetch_one, fetch_all
from services.live_service import prime_live_rooms_public_cache
from utils.supabase_client import SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL, get_supabase, get_supabase_admin

_SUPABASE_HEALTH_CACHE = {"expires_at": 0.0, "payload": None}


def _is_production_env():
    return get_env("FLASK_ENV") == "production" or get_env("ENV") == "production"


if not _is_production_env():
    os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
    os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")


def _flag_enabled(name):
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _startup_fast_mode():
    return any(
        _flag_enabled(name)
        for name in (
            "CHAIN_FAST_LOCAL",
            "CHAIN_DISABLE_PREWARM",
            "CHAIN_DISABLE_DB_PING",
            "CHAIN_DISABLE_SCHEMA_CHECK",
        )
    )


def _app_test_mode():
    return _flag_enabled("FLASK_TESTING")


def _is_apk_request():
    ua = (request.headers.get("User-Agent") or "").lower()
    return any(token in ua for token in ("android", "capacitor", " wv", "namvibe"))


def _apply_local_session_cookie_config(app):
    app.config["SESSION_COOKIE_SECURE"] = False
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_DOMAIN"] = None
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)


def _is_local_debug_request():
    host = (request.host or "").split(":", 1)[0]
    return host in {"127.0.0.1", "localhost", "192.168.179.30"} or _is_apk_request()

from services.request_cache import cache_clear
from services.logging_service import log_error, log_warning, log_info
from services.metrics_service import increment, observe_route

from services.socketio_service import init_socketio
from services.rate_limit_service import init_rate_limiter
from services.observability_service import init_observability
from services import socket_events # Registers events


def check_readiness():
    """Verifies that core backend services are responsive."""
    if _startup_fast_mode():
        return True

    from services.neon_service import get_neon_health
    from services.redis_service import get_redis_health, _REDIS_URL
    from services.logging_service import log_info, log_error

    neon = get_neon_health()
    redis = get_redis_health()

    # Redis is optional — skip check if no URL configured
    redis_configured = bool(_REDIS_URL)
    redis_ok = redis.get("status") == "ok" or not redis_configured
    is_ready = neon.get("status") == "ok" and redis_ok
    if is_ready:
        log_info("startup_readiness_check_passed", neon_latency=neon.get("latency_ms"), redis_latency=redis.get("latency_ms"))
    else:
        log_error("startup_readiness_check_failed", neon_status=neon.get("status"), redis_status=redis.get("status"))

    return is_ready


def should_start_delayed_prewarm(debug=False):
    if _startup_fast_mode():
        return False
    if not debug:
        return True
    return os.environ.get("WERKZEUG_RUN_MAIN") == "true"


def schedule_delayed_homepage_prewarm(app, debug=False):
    if not should_start_delayed_prewarm(debug=debug):
        return False

    def delayed_prewarm():
        time.sleep(2)
        print("[app] Performing delayed homepage prewarm and readiness check...")
        with app.app_context():
            try:
                prime_neon_runtime()
                check_readiness()
                prime_live_rooms_public_cache(limit=8)
                warm_homepage_cache()
                print("[app] Startup sequence complete")
            except Exception as e:
                print(f"[app] Startup sequence failed: {e}")

    threading.Thread(target=delayed_prewarm, daemon=True).start()
    return True


def format_datetime_filter(value):
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return value
    return value.strftime("%b %d, %Y") if hasattr(value, "strftime") else str(value)


from utils.observability_utils import start_request_timer, log_request_performance
from utils.security_utils import check_ip_reputation


APK_CSRF_MAX_AGE_SECONDS = 4 * 60 * 60


def _apk_csrf_salt(path):
    return f"namvibe-apk-csrf:{path}"


def _make_apk_csrf_token(app, path):
    serializer = URLSafeTimedSerializer(app.secret_key, salt=_apk_csrf_salt(path))
    return serializer.dumps({"path": path, "nonce": uuid.uuid4().hex})


def _valid_apk_csrf_token(app, path, token):
    if not token:
        return False
    serializer = URLSafeTimedSerializer(app.secret_key, salt=_apk_csrf_salt(path))
    try:
        payload = serializer.loads(token, max_age=APK_CSRF_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return False
    return hmac.compare_digest(str(payload.get("path") or ""), path)

def create_app():
    app = Flask(__name__)
    app.jinja_env.globals.setdefault("csrf_token", generate_csrf)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    csrf = CSRFProtect(app)
    startup_perf_debug = os.environ.get("CHAIN_STARTUP_PERF_DEBUG", "").lower() in ("1", "true", "yes", "on")
    startup_perf_started = time.perf_counter()

    def _log_startup_stage(stage, **fields):
        if not startup_perf_debug:
            return
        log_info("startup_perf_debug", stage=stage, worker_pid=os.getpid(), **fields)

    _log_startup_stage("create_app_start")
    
    @app.errorhandler(CSRFError)
    def _csrf_friendly_error(e):
        if request.path.startswith("/api/"):
            resp = make_response(jsonify({"error": "csrf_failed", "message": "CSRF token missing or invalid"}), 400)
        elif request.path == "/auth/register" and request.method == "POST":
            apk_token = request.form.get("apk_csrf_token") or request.headers.get("X-NamVibe-Apk-CSRF")
            if _valid_apk_csrf_token(app, "/auth/register", apk_token):
                request.environ["namvibe_csrf_valid"] = True
                from api_routes.auth_routes import register_post
                return register_post()
            resp = make_response(render_template("auth/register.html", error="Your session expired. Please try again.", form=request.form))
        elif request.path == "/auth/register":
            resp = make_response(render_template("auth/register.html", error="Your session expired. Please try again.", form=request.form))
        elif request.path == "/auth/login" and request.method == "POST":
            apk_token = request.form.get("apk_csrf_token") or request.headers.get("X-NamVibe-Apk-CSRF")
            if _valid_apk_csrf_token(app, "/auth/login", apk_token):
                request.environ["namvibe_csrf_valid"] = True
                from api_routes.auth_routes import login
                return login()
            resp = make_response(render_template("auth/login.html", error="Your session expired. Please try again.", oauth_error=None, success_message=None, next_path=session.get("auth_next")))
        elif request.path == "/auth/login":
            resp = make_response(render_template("auth/login.html", error="Your session expired. Please try again.", oauth_error=None, success_message=None, next_path=session.get("auth_next")))
        elif request.path == "/auth/forgot-password":
            resp = make_response(render_template("auth/forgot_password.html", error="Your session expired. Please try again.", success=None))
        elif request.path == "/auth/reset-password":
            resp = make_response(render_template("auth/reset_password.html", error="Your session expired. Please try again.", success=None))
        else:
            resp = make_response(render_template("auth/login.html", error="Your session expired. Please try again.", oauth_error=None, success_message=None, next_path=session.get("auth_next")))
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp, 200
    
    # Phase 13 Performance: Schema Registry Warming
    if os.getenv("CHAIN_WARM_SCHEMA", "0") == "1":
        from services.schema_registry import warm_schema_cache
        warm_schema_cache()

    def _is_fast_public_request():
        if request.method != "GET":
            return False
        return (
            request.path == "/"
            or request.path == "/healthz"
            or request.path.startswith("/health/")
            or request.path.startswith("/discover/")
            or request.path.startswith("/reels/")
            or request.path == "/reels"
            or request.path == "/live/"
        )


    def _skip_first_request_neon_prewarm():
        return request.path == "/reels" or request.path.startswith("/reels/")

    def _log_reels_prewarm(stage, **fields):
        if os.environ.get("CHAIN_REELS_PERF_DEBUG", "").lower() not in ("1", "true", "yes", "on"):
            return
        log_info("reels_prewarm_debug", stage=stage, worker_pid=os.getpid(), **fields)

    @app.before_request
    def before_req():
        if request.path.startswith("/static/"):
            return None
        start_request_timer()
        if request.path == "/healthz" or request.path.startswith("/health/"):
            return None
        if request.path in {"/api/feed/check", "/api/ai/status"} or request.path.startswith("/api/homepage/"):
            return None
        check_ip_reputation()

    @app.after_request
    def after_req(response):
        return log_request_performance(response)

    if _app_test_mode():
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
    
    flask_env = os.getenv("FLASK_ENV", "development")
    is_prod = flask_env == "production"
    
    secret_key = os.getenv("SECRET_KEY")
    if is_prod and not secret_key:
        raise RuntimeError("SECRET_KEY environment variable is required in production.")
    
    if not secret_key and not is_prod:
        secret_key = "namvibe-local-dev-secret-change-before-production"
    app.secret_key = secret_key
    
    # Session and Performance Configuration
    SLOW_REQUEST_MS_LOCAL = 500
    SLOW_REQUEST_MS_PROD = 1000
    app.config.update(
        SLOW_REQUEST_MS_LOCAL=SLOW_REQUEST_MS_LOCAL,
        SLOW_REQUEST_MS_PROD=SLOW_REQUEST_MS_PROD,
        MAX_CONTENT_LENGTH=100 * 1024 * 1024
    )
    
    init_cache(app)
    scheduler = init_scheduler(app)
    if scheduler.running and not _app_test_mode():
        try:
            from services.call_service import check_call_timeouts
            from services.status_service import expire_old_statuses
            scheduler.add_job(check_call_timeouts, 'interval', seconds=60, id='call_timeouts')
            scheduler.add_job(expire_old_statuses, 'interval', minutes=15, id='status_expiry')
        except Exception as e:
            print(f"[app] Failed to add background jobs: {e}")
    init_observability(app)
    app.limiter = init_rate_limiter(app)
    socketio = init_socketio(app)
    
    app.config.from_object("config.settings.Config")
    app.config.setdefault("APP_NAME", os.getenv("APP_NAME", "NamVibe"))
    app.config.setdefault("APP_DOMAIN", os.getenv("APP_DOMAIN", "namvibe.com"))

    # Session and Security Configuration
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=is_prod,
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        SESSION_COOKIE_DOMAIN=None,
    )
    if not is_prod:
        app.config["WTF_CSRF_TIME_LIMIT"] = None
        app.config["WTF_CSRF_SSL_STRICT"] = False
        _apply_local_session_cookie_config(app)
    else:
        app.config.setdefault("WTF_CSRF_TIME_LIMIT", None)
        app.config["PREFERRED_URL_SCHEME"] = "https"

    @app.before_request
    def manage_session():
        if _is_apk_request() or not is_prod:
            _apply_local_session_cookie_config(app)
        # Skip for static files
        if request.path.startswith("/static"):
            return
            
        # Lightweight session restore only for protected routes
        protected_blueprints = {"profile", "message", "messaging_api", "wallet", "admin", "creator", "dating", "call", "notifications"}
        
        # Check if current endpoint is in a protected blueprint
        if request.blueprint in protected_blueprints:
            from services.session_service import is_logged_in, refresh_supabase_session_if_needed
            if not is_logged_in():
                if session.get("refresh_token"):
                    refresh_supabase_session_if_needed()

    @app.context_processor
    def inject_auth_state():
        from services.session_service import is_logged_in
        return dict(
            is_logged_in=is_logged_in(),
            APP_NAME=app.config.get("APP_NAME", "NamVibe"),
            APP_DOMAIN=app.config.get("APP_DOMAIN", "namvibe.com"),
            csrf_token=generate_csrf,
            apk_csrf_token=lambda path=None: _make_apk_csrf_token(app, path or request.path),
        )

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(public_bp)
    app.add_template_filter(format_datetime_filter, "datetime")
    app.add_template_filter(hashtag_links, "hashtag_links")

    @app.get("/api/profile/current")
    def api_profile_current_alias():
        from api_routes.profile_routes import api_current_profile
        return api_current_profile()

    @app.get("/api/profile/<username>/summary")
    def api_public_profile_summary(username):
        from flask import jsonify
        from services.profile_service import get_profile_by_username, get_profile_stats
        profile = get_profile_by_username(username[1:] if username.startswith("@") else username)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404
        stats = get_profile_stats(profile.get("id")) if profile.get("id") else {}
        return jsonify({
            "id": profile.get("id"),
            "username": profile.get("username"),
            "display_name": profile.get("display_name") or profile.get("full_name") or profile.get("username"),
            "avatar_url": profile.get("avatar_url"),
            "cover_url": profile.get("cover_url"),
            "bio": profile.get("bio"),
            "location": profile.get("location") or profile.get("current_location") or profile.get("town"),
            "stats": stats,
        })

    @app.get("/api/profile/me/completion")
    def api_my_profile_completion():
        from flask import jsonify
        from services.profile_service import get_current_profile, get_profile_stats
        from services.profile_completion_service import calculate_profile_completion
        profile = get_current_profile()
        if not profile:
            return jsonify({"error": "Authentication required"}), 401
        stats = get_profile_stats(profile.get("id")) if profile.get("id") else {}
        completion_profile = {
            **profile,
            "posts_count": stats.get("posts", profile.get("posts_count")),
            "reels_count": stats.get("reels", profile.get("reels_count")),
            "stories_count": stats.get("stories", profile.get("stories_count")),
        }
        return jsonify(calculate_profile_completion(completion_profile))

    if os.getenv("FLASK_ENV", "development") != "production":
        @app.get("/dev/profile-debug")
        def dev_profile_debug():
            from flask import abort
            from services.profile_service import get_current_profile, get_profile_bundle

            def _scrub_mapping(value):
                if isinstance(value, dict):
                    scrubbed = {}
                    for key, item in value.items():
                        lower_key = str(key).lower()
                        if any(token in lower_key for token in ("password", "token", "secret", "key", "cookie", "session")):
                            scrubbed[key] = "[redacted]"
                        else:
                            scrubbed[key] = _scrub_mapping(item)
                    return scrubbed
                if isinstance(value, list):
                    return [_scrub_mapping(item) for item in value]
                return value

            flask_env = os.getenv("FLASK_ENV", "development")
            if flask_env == "production" or os.getenv("ENV") == "production":
                abort(404)

            raw_session = dict(session)
            safe_session = {}
            for key, value in raw_session.items():
                lower_key = str(key).lower()
                if any(token in lower_key for token in ("password", "token", "secret", "key", "cookie")):
                    safe_session[key] = "[redacted]"
                else:
                    safe_session[key] = value

            current_profile = get_current_profile()
            bundle = get_profile_bundle(profile_id=current_profile["id"], viewer=current_profile) if current_profile and current_profile.get("id") else None

            return jsonify({
                "environment": flask_env,
                "session": _scrub_mapping(safe_session),
                "session_keys": sorted(list(raw_session.keys())),
                "current_profile": _scrub_mapping(current_profile),
                "profile_bundle": _scrub_mapping(bundle),
            }), 200
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(matching_bp)
    app.register_blueprint(dating_bp)
    app.register_blueprint(message_bp)
    app.register_blueprint(messaging_api_bp)
    app.register_blueprint(call_bp)
    app.register_blueprint(notification_engine_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(developer_bp)
    app.register_blueprint(messages_call_bp)
    app.register_blueprint(api_calls_bp)
    app.register_blueprint(discovery_bp)
    app.register_blueprint(activity_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(moderation_bp)
    app.register_blueprint(search_api_bp)
    app.register_blueprint(marketplace_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(stories_v2_bp)
    app.register_blueprint(live_media_bp)
    app.register_blueprint(realtime_bp)
    app.register_blueprint(reels_bp)
    csrf.exempt("api_routes.reels_routes.api_view")
    csrf.exempt("api_routes.reels_routes.api_like")
    csrf.exempt("api_routes.reels_routes.api_comment")
    csrf.exempt("api_routes.reels_routes.api_save")
    csrf.exempt("api_routes.reels_routes.api_share")
    csrf.exempt("api_routes.reels_routes.api_delete")
    csrf.exempt("api_routes.reels_routes.api_event")
    app.register_blueprint(presence_bp)
    app.register_blueprint(safety_bp)
    app.register_blueprint(admin_safety_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(founder_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(feed_bp)
    app.register_blueprint(verification_bp)
    app.register_blueprint(mobile_api_bp)
    app.register_blueprint(engagement_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(post_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(homepage_api_bp)
    app.register_blueprint(feed_preload_bp)
    app.register_blueprint(creator_bp)
    app.register_blueprint(studio_bp)
    app.register_blueprint(social_bp, url_prefix="/social")
    app.register_blueprint(social_api_bp)
    app.register_blueprint(push_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(privacy_api_bp)
    app.register_blueprint(group_call_bp)
    app.register_blueprint(push_notifications_api_bp)
    app.register_blueprint(encryption_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(notification_center_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(performance_bp)
    app.register_blueprint(explore_bp)
    app.register_blueprint(comments_bp)
    app.register_blueprint(friend_bp)
    app.register_blueprint(follow_request_api_bp)
    csrf.exempt(follow_request_api_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(contacts_api_bp)
    app.register_blueprint(inbox_bp)
    app.register_blueprint(gallery_bp)
    from api_routes.block_routes import block_bp
    app.register_blueprint(block_bp)
    app.register_blueprint(social_graph_bp)
    app.register_blueprint(profile_extra_bp)
    app.register_blueprint(verification_admin_bp)
    app.register_blueprint(advertising_bp)
    app.register_blueprint(ad_admin_bp)
    app.register_blueprint(content_controls_bp)
    app.register_blueprint(rpromo_bp)
    register_live_routes(app)
    register_connecting_you_routes(app)
    app.register_blueprint(support_bp)
    app.register_blueprint(support_page_bp)
    csrf.exempt(support_bp)

    try:
        from services.content_service import ensure_content_schema
        if os.getenv("CHAIN_BOOTSTRAP_SCHEMA", "0") == "1":
            ensure_content_schema()
    except Exception as error:
        log_warning("content_schema_bootstrap_failed", error=str(error))

    for bp in api_v1_blueprints:
        app.register_blueprint(bp, url_prefix=f"/api/v1{bp.url_prefix}")

    _log_startup_stage("blueprints_registered", elapsed_ms=round((time.perf_counter() - startup_perf_started) * 1000, 2))

    @app.get("/debug/session")
    def debug_session_app():
        if _is_production_env() and not _is_local_debug_request():
            from flask import abort
            abort(404)
        from api_routes.auth_routes import _debug_session_payload
        return jsonify(_debug_session_payload())

    auth_audit_paths = {"/auth/register", "/auth/login", "/auth/debug-session", "/profile/"}
    print("[route-audit] active auth/profile routes")
    for rule in sorted(app.url_map.iter_rules(), key=lambda item: item.rule):
        if rule.rule in auth_audit_paths:
            methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
            print(f"[route-audit] {methods:8s} {rule.rule} -> {rule.endpoint}")

    @app.after_request
    def after_request_cleanup(response):
        if request.path.startswith("/static/"):
            response.headers.setdefault("Cache-Control", "public, max-age=86400")
            return response
        cache_clear()
        # Add latency header for monitoring
        if hasattr(g, 'request_started_at'):
            latency = (time.perf_counter() - g.request_started_at) * 1000
            response.headers["X-Response-Time-Ms"] = f"{latency:.1f}"
            if latency > 1000:
                log_warning("slow_request_detected", path=request.path, latency_ms=latency)
        return response

    from services.neon_service import NeonError, CircuitOpenError
    
    @app.errorhandler(CircuitOpenError)
    def handle_circuit_open(e):
        return jsonify({"error": "Database circuit breaker open", "retry_after": 30}), 503

    @app.errorhandler(NeonError)
    def handle_neon_error(e):
        log_error("app_db_error", error=e)
        return jsonify({"error": "Database error", "type": e.__class__.__name__}), 500

    @app.before_request
    def redirect_www_to_canonical():
        host = request.host.lower()
        if host.startswith("www."):
            canonical = host.removeprefix("www.")
            return redirect(f"{request.scheme}://{canonical}{request.full_path}", 301)

    @app.before_request
    def track_request_start():
        if request.path.startswith("/static/"):
            return None
        g.request_started_at = time.perf_counter()
        g.request_id = str(uuid.uuid4())
        g.current_profile_id = session.get("auth_user_id")
        g._before_request_started = time.perf_counter()
        if (
            session.get("refresh_token")
            and not session.get("access_token")
            and request.endpoint != "static"
            and not _is_fast_public_request()
        ):
            refresh_chain_session()

    @app.context_processor
    def inject_global_data():
        current_profile = None
        unread_count = 0
        wallet_balance = 0
        available_routes = {rule.rule for rule in app.url_map.iter_rules()}
        feature_candidates = {
            "home": ["/"],
            "discover": ["/discover/"],
            "live": ["/live/"],
            "messages": ["/messages/"],
            "calls": ["/calls/", "/calls/recent"],
            "wallet": ["/wallet/"],
            "profile": ["/profile/"],
            "login": ["/auth/login"],
            "register": ["/auth/register"],
            "friends": ["/social/friend-requests", "/discover/"],
            "reels": ["/reels/", "/discover/"],
            "notifications": ["/notifications/", "/profile/"],
            "dating": ["/dating/discover", "/discover/"],
            "create_post": ["/posts/create", "/features/create-post", "/post/create", "/create-post"],
            "create_story": ["/status/create", "/profile/"],
            "upload_reel": ["/reels/upload", "/features/upload-reel", "/reels/"],
            "upload_video": ["/features/upload-video", "/upload/video", "/media/upload"],
            "go_live": ["/live/studio", "/live/"],
            "settings": ["/profile/settings", "/discover/"],
            "security": ["/security/privacy", "/security"],
            "help": ["/discover/"],
        }

        def route_exists(path):
            return path in available_routes

        def safe_link(feature_name, logged_in=None):
            signed_in = current_profile is not None if logged_in is None else bool(logged_in)
            fallback_logged_in = "/profile/" if signed_in else "/auth/login"
            fallback_logged_out = "/auth/login"
            candidates = feature_candidates.get(feature_name, [])
            for candidate in candidates:
                if candidate in available_routes:
                    if not signed_in and candidate.startswith(("/messages/", "/wallet/", "/profile/", "/notifications/")):
                        return fallback_logged_out
                    return candidate
            return fallback_logged_in if signed_in else fallback_logged_out

        def session_profile_stub():
            email = session.get("auth_email") or ""
            username = session.get("username") or (email.split("@")[0] if "@" in email else "chainuser")
            full_name = session.get("full_name") or username.replace("_", " ").title()
            return {
                "id": session.get("profile_id"),
                "auth_user_id": session.get("auth_user_id"),
                "email": email,
                "username": username,
                "full_name": full_name,
                "display_name": full_name,
                "avatar_url": None,
            }
        
        fast_local = _flag_enabled("CHAIN_FAST_LOCAL") and not _is_production_env()
        fast_public_page = request.method == "GET" and (
            request.path == "/"
            or request.path.startswith("/discover/")
            or request.path in {"/reels/", "/reels", "/live/"}
        )

        # Priority: auth_user_id in session
        if "auth_user_id" in session:
            if fast_local or fast_public_page or session.get("profile_warning") or session.get("age_check_required"):
                current_profile = session_profile_stub()
            else:
                current_profile = get_current_profile()
                if not current_profile:
                    current_profile = session_profile_stub()

        if current_profile and current_profile.get("id") and not fast_local and not fast_public_page:
            from services.notification_engine import unread_count
            unread_count = unread_count(current_profile["id"])
            
            from services.wallet_engine import ensure_wallet
            try:
                wallet = ensure_wallet(current_profile["id"])
                if wallet:
                    wallet_balance = wallet.get("coin_balance", 0)
            except Exception:
                wallet_balance = 0

        return {
            "g_current": current_profile,
            "g_unread_count": unread_count,
            "g_wallet_balance": wallet_balance,
            "session": session,
            "safe_link": safe_link,
            "route_exists": route_exists,
            "get_world_countries": __import__("services.country_service", fromlist=["get_world_countries"]).get_world_countries,
        }

    @app.route("/feed")
    def feed_page():
        from flask import render_template
        from services.profile_service import get_current_profile
        profile = get_current_profile()
        return render_template("feed/index.html", profile=profile)

    @app.route("/reels")
    def reels_page():
        return redirect(url_for("reels.index"))

    @app.route("/stories")
    @app.route("/stories/")
    def stories_root():
        return redirect(url_for("stories_v2.index"))

    @app.route("/live/create")
    def live_create_root_redirect():
        return redirect("/live/studio", code=302)

    @app.route("/dating")
    def dating_root_redirect():
        return redirect("/dating/discover", code=302)

    @app.route("/api/stories/<story_id>/react", methods=["POST"])
    def api_story_react(story_id):
        from services.stories_service import react_to_story
        profile = get_current_profile()
        viewer_id = (profile or {}).get("id")
        if not viewer_id:
            return jsonify({"error": "Not authenticated"}), 401
        data = request.get_json(silent=True) or {}
        react_to_story(story_id, viewer_id, data.get("reaction", "like"))
        return jsonify({"success": True}), 200

    @app.route("/api/stories/<story_id>/reply", methods=["POST"])
    def api_story_reply(story_id):
        from services.stories_service import reply_to_story
        profile = get_current_profile()
        viewer_id = (profile or {}).get("id")
        if not viewer_id:
            return jsonify({"error": "Not authenticated"}), 401
        data = request.get_json(silent=True) or {}
        reply_to_story(story_id, viewer_id, data.get("reply_text", ""))
        return jsonify({"success": True}), 200

    @app.route("/api/stories/feed", methods=["GET"])
    def api_story_feed():
        from services.status_service import list_active_statuses
        profile = get_current_profile()
        viewer_id = (profile or {}).get("id")
        stories = list_active_statuses(viewer_profile_id=viewer_id)
        return jsonify({"stories": stories}), 200

    @app.route("/api/stories/<story_id>", methods=["GET"])
    def api_story_detail(story_id):
        from services.status_service import get_status, can_view_status
        from services.ai.interaction_service import track_interaction_safe
        profile = get_current_profile()
        viewer_id = (profile or {}).get("id")
        allowed, reason = can_view_status(story_id, viewer_id)
        if not allowed:
            return jsonify({"error": "Cannot view status", "reason": reason}), 403
        story = get_status(story_id, viewer_profile_id=viewer_id)
        if not story:
            return jsonify({"error": "Not found"}), 404
        if viewer_id:
            track_interaction_safe(
                viewer_id,
                target_type="story",
                target_id=story_id,
                action_type="open",
                source_surface="story",
            )
        return jsonify({"story": story}), 200

    @app.route("/api/stories/<story_id>/view", methods=["POST"])
    def api_story_view(story_id):
        from services.status_service import record_view, can_view_status
        from services.ai.interaction_service import track_interaction_safe
        profile = get_current_profile()
        viewer_id = (profile or {}).get("id")
        if not viewer_id:
            return jsonify({"error": "Not authenticated"}), 401
        allowed, reason = can_view_status(story_id, viewer_id)
        if not allowed:
            return jsonify({"error": "Cannot view status", "reason": reason}), 403
        data = request.get_json(silent=True) or {}
        ok = record_view(
            story_id,
            viewer_id,
            reaction=data.get("reaction"),
            reply_message=data.get("reply_message"),
        )
        if ok:
            track_interaction_safe(
                viewer_id,
                target_type="story",
                target_id=story_id,
                action_type="view",
                source_surface="story",
            )
        return jsonify({"success": bool(ok)}), 200 if ok else 400

    @app.route("/api/stories/<story_id>/viewers", methods=["GET"])
    def api_story_viewers_exact(story_id):
        from services.status_service import list_viewers
        profile = get_current_profile()
        viewer_id = (profile or {}).get("id")
        if not viewer_id:
            return jsonify({"error": "Not authenticated"}), 401
        viewers = list_viewers(story_id, requesting_profile_id=viewer_id)
        return jsonify({"viewers": viewers}), 200

    @app.route("/api/stories/<story_id>", methods=["DELETE"])
    @login_required
    def api_story_delete(story_id):
        from services.status_service import delete_status
        from services.content_service import get_session_profile_id
        profile_id = get_session_profile_id()
        if not profile_id:
            return jsonify({"error": "Unauthorized"}), 401
        if delete_status(story_id, profile_id):
            return jsonify({"ok": True})
        return jsonify({"error": "delete_failed"}), 403

    @app.route("/api/reels/<reel_id>/comments", methods=["POST"])
    @login_required
    def api_reel_comments_create(reel_id):
        from services.engagement_service import add_comment
        from services.content_service import get_session_profile_id
        profile_id = get_session_profile_id()
        if not profile_id:
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        body = data.get("body") or request.form.get("body", "")
        if not body.strip():
            return jsonify({"error": "Comment body is required"}), 400
        result = add_comment(profile_id, "reel", reel_id, body.strip())
        if result.get("success"):
            return jsonify(result), 201
        return jsonify({"error": result.get("error", "comment_failed")}), 400

    @app.route("/api/reels/comments/<comment_id>/reply", methods=["POST"])
    @login_required
    def api_reel_comment_reply(comment_id):
        from services.comments_service import add_comment as reply_to_comment
        from services.content_service import get_session_profile_id
        profile_id = get_session_profile_id()
        if not profile_id:
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        body = data.get("body") or request.form.get("body", "")
        if not body.strip():
            return jsonify({"error": "Reply body is required"}), 400
        comment_id_result = reply_to_comment("reel", None, profile_id, body.strip(), parent_id=comment_id)
        if comment_id_result:
            return jsonify({"ok": True, "comment_id": comment_id_result}), 201
        return jsonify({"error": "Failed to reply"}), 400

    @app.route("/api/reels/comments/<comment_id>", methods=["DELETE"])
    @login_required
    def api_reel_comment_delete(comment_id):
        from services.engagement_service import delete_comment
        from services.content_service import get_session_profile_id
        profile_id = get_session_profile_id()
        if not profile_id:
            return jsonify({"error": "Unauthorized"}), 401
        result = delete_comment(profile_id, "reel", comment_id)
        if result.get("success"):
            return jsonify({"ok": True})
        return jsonify({"error": result.get("error", "delete_failed")}), 400

    @app.route("/api/stories/create", methods=["POST"])
    @login_required
    def api_stories_create():
        from services.status_service import create_status
        from services.content_service import get_session_profile_id
        profile_id = get_session_profile_id()
        if not profile_id:
            return jsonify({"error": "Unauthorized"}), 401
        caption = request.form.get("caption")
        media_file = request.files.get("media")
        visibility = request.form.get("visibility", "followers")
        visibility = request.form.get("audience") or visibility
        visibility = visibility.lower() if visibility else "followers"
        if visibility not in ("followers", "private", "subscribers", "locked"):
            visibility = "followers"
        media_type = request.form.get("media_type", "image")
        status, error = create_status(
            profile_id,
            caption,
            media_file,
            visibility=visibility,
            media_type=media_type,
            duration_seconds=request.form.get("duration_seconds", 0),
            background_color=request.form.get("background_color"),
            text_content=request.form.get("text_content"),
        )
        if error:
            return jsonify({"ok": False, "error": error}), 400
        if status:
            return jsonify({"ok": True, "story": status}), 201
        return jsonify({"ok": False, "error": "Failed to create"}), 400

    @app.route("/api/posts/create", methods=["POST"])
    @login_required
    def api_posts_create():
        from services.post_service import create_post
        from services.content_service import get_session_profile_id
        profile_id = get_session_profile_id()
        if not profile_id:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        caption = request.form.get("caption") or request.form.get("body") or ""
        media_file = request.files.get("media")
        link_url = request.form.get("link_url") or ""
        town_tag = request.form.get("town_tag") or request.form.get("location") or ""
        visibility = request.form.get("visibility", "public")
        visibility = request.form.get("audience") or visibility
        visibility = visibility.lower() if visibility else "public"
        if visibility not in ("public", "followers", "private"):
            visibility = "public"
        post, error = create_post(profile_id, caption, media_file, link_url=link_url, town_tag=town_tag, visibility=visibility)
        if error:
            return jsonify({"ok": False, "error": error}), 400
        if post:
            return jsonify({"ok": True, "post": post}), 201
        return jsonify({"ok": False, "error": "Failed to create post"}), 400

    @app.route("/api/reels/create", methods=["POST"])
    @login_required
    def api_reels_create():
        from services.reels_engine import create_reel
        from services.content_service import get_session_profile_id
        profile_id = get_session_profile_id()
        if not profile_id:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        video_file = request.files.get("video")
        if not video_file:
            return jsonify({"ok": False, "error": "Video file is required"}), 400
        caption = request.form.get("caption", "")
        music_title = request.form.get("music_title", "")
        visibility = request.form.get("visibility", "public")
        visibility = request.form.get("audience") or visibility
        visibility = visibility.lower() if visibility else "public"
        if visibility not in ("public", "followers", "private"):
            visibility = "public"
        reel_id, error = create_reel(profile_id, caption, video_file, None, music_title=music_title, visibility=visibility)
        if error:
            return jsonify({"ok": False, "error": error}), 400
        if reel_id:
            return jsonify({"ok": True, "reel_id": reel_id}), 201
        return jsonify({"ok": False, "error": "Failed to create reel"}), 400

    @app.route("/stories/create", methods=["GET", "POST"])
    @login_required
    def stories_create_page():
        from services.status_service import create_status
        from services.content_service import get_session_profile_id, session_profile_stub
        from services.profile_service import get_current_profile
        if request.method == "POST":
            pid = get_session_profile_id()
            if not pid:
                return redirect(url_for("auth.login"))
            caption = request.form.get("caption")
            media_file = request.files.get("media")
            visibility = request.form.get("visibility") or "followers"
            visibility = request.form.get("audience") or visibility
            visibility = visibility.lower() if visibility else "followers"
            if visibility not in ("followers", "private", "subscribers", "locked"):
                visibility = "followers"
            media_type = request.form.get("media_type", "image")
            result, error = create_status(
                pid,
                caption,
                media_file,
                visibility=visibility,
                media_type=media_type,
                duration_seconds=request.form.get("duration_seconds", 0),
                background_color=request.form.get("background_color"),
                text_content=request.form.get("text_content"),
            )
            if error:
                flash(error, "error")
            elif result:
                flash("Story posted!", "success")
                return redirect("/stories")
            flash("Could not post story.", "error")
        profile = get_current_profile() or (session_profile_stub() if get_session_profile_id() else None)
        return render_template("status/create.html", profile=profile)

    @app.route("/settings")
    def settings_root_redirect():
        return redirect("/profile/settings", code=302)

    @app.route("/settings/notifications")
    def notification_settings():
        from services.push_notification_service import get_preferences, get_vapid_public_key
        from services.profile_service import get_current_profile
        profile = get_current_profile()
        profile_id = (profile or {}).get("id") or session.get("profile_id")
        prefs = get_preferences(profile_id) if profile_id else {}
        vapid_key = get_vapid_public_key()
        return render_template("settings/notifications.html",
            preferences=prefs,
            vapid_configured=bool(vapid_key),
            profile=profile,
        )

    @app.route("/settings/")
    def settings_landing():
        if not (session.get("profile_id") or session.get("auth_user_id")):
            return redirect("/auth/login?next=/settings/", code=302)
        return redirect("/profile/settings", code=302)

    # Module-level caches for online stats & public groups (shared across requests)
    _stats_cache = {"data": None, "expires_at": 0}
    _groups_cache = {"data": None, "expires_at": 0}

    def _get_online_stats():
        now = time.time()
        cached = _stats_cache["data"]
        if cached and now < _stats_cache["expires_at"]:
            return cached
        try:
            from api_routes.homepage_api import _build_homepage_contract
            payload = _build_homepage_contract(viewer_id=(get_current_profile() or {}).get("id"), limit=20)
            result = {
                "online_count": len(payload.get("online_users") or []),
                "live_count": int((payload.get("counts") or {}).get("live_now") or 0),
                "online_users": payload.get("online_users") or [],
            }
            _stats_cache["data"] = result
            _stats_cache["expires_at"] = now + 30
            return result
        except Exception:
            return _stats_cache["data"] or {"online_count": 0, "live_count": 0, "online_users": []}

    def _get_cached_public_groups():
        now = time.time()
        cached = _groups_cache["data"]
        if cached and now < _groups_cache["expires_at"]:
            return cached
        try:
            ns = __import__("services.neon_service", fromlist=["fast_query"])
            result = ns.fast_query(
                "SELECT g.*, COALESCE(gm.c,0) AS member_count FROM chain_groups g"
                " LEFT JOIN (SELECT group_id,COUNT(*) AS c FROM chain_group_members"
                " WHERE status='active' GROUP BY group_id) gm ON gm.group_id=g.id"
                " WHERE g.visibility='public' ORDER BY member_count DESC,g.created_at DESC LIMIT 5",
                (), timeout_ms=2000, default=[],
            ) or []
            _groups_cache["data"] = result
            _groups_cache["expires_at"] = now + 30
            return result
        except Exception:
            return _groups_cache["data"] or []

    @app.route("/")
    @app.route("/home")
    def home():
        town = request.args.get("town", "")
        region = request.args.get("region", "")
        avail = AVAIL_ROUTES
        is_in = bool(session.get("profile_id") or session.get("auth_user_id"))
        base_routes = {
            "home_route": "/",
            "discover_route": "/discover/" if "/discover/" in avail else "/",
            "live_route": "/live/" if "/live/" in avail else "/",
            "reel_route": "/reels/" if "/reels/" in avail else "/discover/",
            "stories_route": "/stories/" if "/stories/" in avail else "/discover/",
            "support_route": "/support" if "/support" in avail else "/",
            "terms_route": "/terms" if "/terms" in avail else "/",
            "privacy_route": "/privacy" if "/privacy" in avail else "/",
            "reel_create": "/reels/upload" if "/reels/upload" in avail else "/features/upload-reel",
            "story_create": "/status/create" if "/status/create" in avail else "/profile/",
            "composer_fallback": "/features/create-post" if "/features/create-post" in avail else "/posts/create",
            "upload_video_route": "/features/upload-video" if "/features/upload-video" in avail else "/upload/video",
            "dating_route": "/dating/discover" if "/dating/discover" in avail else "/discover/",
            "dating_label": "Connecting You" if "/dating/discover" in avail else "Discover",
            "friends_route": "/social/friend-requests" if "/social/friend-requests" in avail else "/discover/",
            "login_route": "/auth/login",
            "register_route": "/auth/register",
            "drawer_profile": "/profile/" if is_in else "/auth/login",
            "drawer_messages": "/messages/" if is_in and "/messages/" in avail else ("/auth/login" if not is_in else "/"),
            "drawer_calls": "/calls/" if is_in and "/calls/" in avail else ("/auth/login" if not is_in else "/calls/recent"),
            "drawer_notifications": "/notifications/" if is_in and "/notifications/" in avail else ("/auth/login" if not is_in else "/profile/"),
            "drawer_wallet": "/wallet/" if is_in and "/wallet/" in avail else ("/auth/login" if not is_in else "/"),
            "drawer_settings": "/profile/settings" if is_in and "/profile/settings" in avail else ("/auth/login" if not is_in else "/discover/"),
            "drawer_security": "/security/privacy" if "/security/privacy" in avail else "/security",
            "reel_available": "/reels/" in avail or "/reels/upload" in avail,
            "story_available": True,
            "live_available": "/live/" in avail,
            "upload_video_available": "/features/upload-video" in avail,
            "post_available": True,
        }
        shell = {
            "feed_for_you": [],
            "posts": [],
            "reels": [],
            "stories": [],
            "suggested_people": [],
            "live_rooms": [],
            "friend_activity": [],
            "online_stats": {"online_count": 0, "live_count": 0, "online_users": []},
            "homepage_degraded": True,
            "homepage_message": "Loading latest NamVibe content...",
            **base_routes,
        }

        def build_fast_shell(cached_payload=None):
            if cached_payload:
                data = dict(shell)
                data["feed_items"] = cached_payload.get("feed_items") or []
                data["feed_for_you"] = list(data["feed_items"])
                data["posts"] = cached_payload.get("posts") or list(data["feed_items"])
                data["stories"] = cached_payload.get("stories") or []
                data["reels"] = cached_payload.get("reels") or []
                data["reels_items"] = cached_payload.get("reels") or []
                data["live_rooms"] = cached_payload.get("live_rooms") or []
                data["suggested_people"] = cached_payload.get("suggested_creators") or cached_payload.get("suggested_people") or []
                data["suggested_creators"] = list(data["suggested_people"])
                data["trending_hashtags"] = cached_payload.get("trending_hashtags") or []
                data["hashtags"] = list(data["trending_hashtags"])
                data["friend_activity"] = cached_payload.get("friend_activity") or []
                data["homepage_degraded"] = bool(cached_payload.get("homepage_degraded"))
                data["homepage_message"] = ""
                data["homepage_timings"] = cached_payload.get("timings") or {}
                data["homepage_payload"] = {
                    "stories": data["stories"],
                    "feed_items": data["feed_items"],
                    "posts": data["posts"],
                    "reels": data["reels"],
                    "friend_activity": data["friend_activity"],
                    "online_users": cached_payload.get("online_users") or [],
                    "counts": (cached_payload.get("counts") or {}),
                    "timings": data["homepage_timings"],
                }
                online_users_list = cached_payload.get("online_users") or cached_payload.get("_online_users") or []
                data["online_stats"] = {
                    "online_count": cached_payload.get("counts", {}).get("online_count", 0) or len(online_users_list),
                    "live_count": len(data["live_rooms"]),
                    "online_users": online_users_list,
                }
                data["wallet_balance"] = (cached_payload.get("wallet") or {}).get("coin_balance", 0)
                return data
            try:
                from api_routes.homepage_api import _build_homepage_contract
                fast_payload = _build_homepage_contract(
                    limit=20,
                    viewer_id=(get_current_profile() or {}).get("id"),
                    include_widgets=False,
                ) or {}
            except Exception:
                if not _app_test_mode():
                    try:
                        from services.homepage_service import get_homepage_data
                        fast_payload = get_homepage_data() or {}
                    except Exception:
                        fast_payload = {}
                else:
                    fast_payload = {}
            data = dict(shell)
            data["feed_items"] = fast_payload.get("feed_items") or []
            data["feed_for_you"] = list(data["feed_items"])
            data["posts"] = fast_payload.get("posts") or list(data["feed_items"])
            data["stories"] = fast_payload.get("stories") or []
            data["reels"] = fast_payload.get("reels") or []
            data["reels_items"] = fast_payload.get("reels") or []
            data["live_rooms"] = fast_payload.get("live_rooms") or []
            data["suggested_people"] = fast_payload.get("suggested_creators") or fast_payload.get("suggested_people") or []
            data["suggested_creators"] = list(data["suggested_people"])
            data["trending_hashtags"] = fast_payload.get("trending_hashtags") or []
            data["hashtags"] = list(data["trending_hashtags"])
            data["friend_activity"] = fast_payload.get("friend_activity") or []
            data["homepage_degraded"] = bool(fast_payload.get("homepage_degraded"))
            data["homepage_message"] = ""
            data["homepage_timings"] = fast_payload.get("timings") or {}
            online_users_list = fast_payload.get("online_users") or []
            data["homepage_payload"] = {
                "stories": data["stories"],
                "feed_items": data["feed_items"],
                "posts": data["posts"],
                "reels": data["reels"],
                "friend_activity": data["friend_activity"],
                "online_users": online_users_list,
                "counts": (fast_payload.get("counts") or {}),
                "timings": data["homepage_timings"],
            }
            data["online_stats"] = {
                "online_count": len(online_users_list),
                "live_count": len(data["live_rooms"]),
                "online_users": online_users_list,
            }
            data["wallet_balance"] = 0
            return data

        with timed("home"):
            home_start = time.perf_counter()
            cached_payload = get_full("public")
            data = build_fast_shell(cached_payload=cached_payload)
            if not cached_payload:
                try:
                    cache_set("homepage:full:public", data, ttl=HOMEPAGE_TTL_SECONDS)
                except Exception:
                    pass
            data.update(base_routes)
            data["chats"] = []
            data["notifications"] = []
            data["marketplace_items"] = []
            data["chats"] = []
            response = make_response(render_template("chain_home.html", **data), 200)
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            total_ms = round((time.perf_counter() - home_start) * 1000, 2)
            log_info(
                "homepage_timing",
                homepage_cache_hit=bool(cached_payload),
                homepage_total_ms=total_ms,
                homepage_posts_ms=(data.get("homepage_timings") or {}).get("posts", 0),
                homepage_posts_normalize_ms=(data.get("homepage_timings") or {}).get("posts_normalize", 0),
                homepage_stories_ms=(data.get("homepage_timings") or {}).get("stories", 0),
                homepage_reels_ms=(data.get("homepage_timings") or {}).get("reels", 0),
                homepage_live_ms=(data.get("homepage_timings") or {}).get("live", 0),
                homepage_hashtags_ms=(data.get("homepage_timings") or {}).get("hashtags", 0),
                homepage_suggestions_ms=(data.get("homepage_timings") or {}).get("suggestions", 0),
                homepage_online_users_ms=(data.get("homepage_timings") or {}).get("online_users", 0),
                homepage_notifications_ms=(data.get("homepage_timings") or {}).get("notifications", 0),
                homepage_wallet_ms=(data.get("homepage_timings") or {}).get("wallet", 0),
                homepage_unread_messages_ms=(data.get("homepage_timings") or {}).get("unread_messages", 0),
            )
            log_info("homepage_route_total", duration_ms=total_ms)
            return response

    @app.route("/live")
    @app.route("/live/")
    def live_hub():
        profile = get_current_profile()
        return render_template("live_hub.html")

    @app.route("/live/studio")
    def live_studio():
        profile = get_current_profile()
        if not profile:
            return redirect(url_for("auth.login", next=request.path), code=302)
        return render_template("live/studio.html", profile=profile, current=profile)

    @app.route("/live/<room_id>")
    def live_room(room_id):
        from services.ai.interaction_service import track_interaction_safe
        pid = (get_current_profile() or {}).get("id")
        room = None
        try:
            row = fetch_one(
                """SELECT r.*, COALESCE(p.display_name, p.username, 'Host') AS host_name,
                   p.username AS host_username, p.avatar_url AS host_avatar, p.is_verified
                   FROM chain_live_rooms r
                   JOIN chain_profiles p ON p.id = r.profile_id
                   WHERE r.id = %s""",
                (room_id,)
            )
            if row:
                owner_id = row.get("profile_id") or row.get("host_id") or row.get("creator_id")
                room = {
                    "id": row["id"],
                    "title": row.get("title", "Untitled Stream"),
                    "category": row.get("category", ""),
                    "type": row.get("type", "music"),
                    "status": row.get("status", "live"),
                    "viewer_count": row.get("viewer_count", 0),
                    "host_name": row.get("host_name", "Host"),
                    "host_username": row.get("host_username", ""),
                    "host_avatar": row.get("host_avatar") or "",
                    "is_verified": row.get("is_verified", False),
                    "tags": row.get("tags") or [],
                    "products": [],
                }
                prod_rows = fetch_all(
                    "SELECT * FROM chain_live_products WHERE room_id = %s ORDER BY sort_order ASC LIMIT 20",
                    (room_id,)
                ) or []
                for pr in prod_rows:
                    room["products"].append({
                        "id": pr["id"],
                        "title": pr.get("title", ""),
                        "price": float(pr.get("price", 0)),
                        "currency": pr.get("currency", "NAD"),
                        "image_url": pr.get("image_url", ""),
                        "discount_pct": pr.get("discount_pct", 0),
                    })
        except Exception as e:
            print(f"[live] Error loading room {room_id}: {e}")

        if not room:
            return render_template("live_hub.html", error="Stream not found"), 404

        owner_id = row.get("profile_id") or row.get("host_id") or row.get("creator_id")
        if pid:
            track_interaction_safe(
                pid,
                target_type="live",
                target_id=room_id,
                action_type="open",
                source_surface="live",
            )
        return render_template(
            "live_room.html",
            room=room,
            is_host=pid is not None and str(owner_id) == str(pid),
        )

    @app.route("/login")
    def legacy_login():
        return redirect("/auth/login", code=302)

    @app.route("/register")
    def legacy_register():
        return redirect("/auth/register", code=302)

    @app.route("/terms", strict_slashes=False)
    def terms():
        return render_template("dashboard/legal.html", page_title="Terms of Service", page_intro="These terms explain how NamVibe works, what users can expect, and the standards for using premium live, chat, wallet, and discovery features.")

    @app.route("/privacy", strict_slashes=False)
    def privacy():
        return render_template("dashboard/legal.html", page_title="Privacy Policy", page_intro="This page explains how NamVibe stores profile data, wallet activity, live interactions, and notifications when connected to Supabase.")

    @app.route("/healthz")
    def healthz():
        """Lightweight health check for load balancers. No external DB touch."""
        payload = {
            "ok": True,
            "components": {
                "app": {"ok": True, "status": "ok"},
                "database": {"ok": True, "status": "not_checked"},
            },
        }
        payload["status"] = "ok" if payload.get("ok") else "degraded"
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        return jsonify(payload), 200

    @app.route("/health/db")
    def health_db():
        """Cached database health check."""
        health = get_neon_health()
        status = 200 if (health.get("connected") or health.get("stale_cache")) else 503
        return jsonify({"service": "neon", **health}), status

    @app.route("/health/redis")
    def health_redis():
        """Cached Redis health check."""
        from services.redis_service import get_redis_health
        health = get_redis_health()
        health["available"] = bool(health.get("connected"))
        health["unavailable"] = not bool(health.get("connected"))
        health["fallback_mode"] = bool(health.get("fallback"))
        status = 200 if health.get("status") == "ok" else 503
        return jsonify({"service": "redis", **health}), status

    @app.route("/health/realtime")
    def health_realtime():
        """Socket.IO and Realtime status."""
        from services.redis_service import redis_available
        from services.socketio_service import socketio
        health = {
            "service": "realtime",
            "socketio_ready": True,
            "redis_backed": redis_available(),
            "async_mode": socketio.async_mode
        }
        return jsonify(health), 200

    @app.route("/system/socketio-status")
    def system_socketio_status():
        """Health/debug endpoint for Socket.IO status."""
        from services.redis_service import redis_available, _REDIS_URL
        from services.socketio_service import socketio
        async_mode = getattr(socketio, 'async_mode', None) or 'unknown'
        websocket_supported = async_mode == 'gevent'
        transports = ['websocket', 'polling'] if websocket_supported else ['polling']
        return jsonify({
            "ok": True,
            "async_mode": async_mode,
            "websocket_supported": websocket_supported,
            "transports": transports,
            "redis_manager_enabled": bool(_REDIS_URL),
            "redis_available": redis_available(),
            "server_ready": getattr(socketio, 'server', None) is not None,
        })

    @app.route("/health/supabase")
    def health_supabase():
        """Cached Supabase health check."""
        now = time.monotonic()
        cached = _SUPABASE_HEALTH_CACHE.get("payload")
        if cached is not None and _SUPABASE_HEALTH_CACHE.get("expires_at", 0) > now:
            return jsonify(cached), 200
        
        health = {
            "service": "supabase",
            "url_present": bool(SUPABASE_URL),
            "anon_key_present": bool(SUPABASE_ANON_KEY),
            "service_role_present": bool(SUPABASE_SERVICE_ROLE_KEY),
            "client_ready": False,
            "admin_ready": False,
            "auth_ready": False,
            "storage_ready": False,
            "error": None,
            "latency_ms": None
        }
        
        started = time.perf_counter()
        try:
            client = get_supabase()
            admin = get_supabase_admin()
            health["client_ready"] = True
            health["admin_ready"] = True
            health["auth_ready"] = hasattr(client, "auth")
            storage = getattr(admin, "storage", None)
            health["storage_ready"] = storage is not None
        except Exception as error:
            health["error"] = str(error)
        
        health["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        _SUPABASE_HEALTH_CACHE["payload"] = dict(health)
        _SUPABASE_HEALTH_CACHE["expires_at"] = now + 60 # Cache for 60s as requested
        
        status = 200 if health["url_present"] and health["anon_key_present"] and health["service_role_present"] else 503
        return jsonify(health), status

    @app.route("/reels/<reel_id>")
    def reel_detail(reel_id):
        from services.reels_engine import get_reel
        from services.profile_service import get_current_profile
        from services.engagement_service import is_liked
        from services.ai.interaction_service import track_interaction_safe
        profile = get_current_profile()
        reel = get_reel(reel_id)
        if not reel:
            return render_template("errors/post_not_found.html",
                message="This reel could not be found. It may have been deleted or made private.",
                profile=profile), 404
        # Visibility check: anonymous users see only public reels
        reel_visibility = reel.get("visibility") or "public"
        pid = (profile or {}).get("id")
        if not pid and reel_visibility != "public":
            return render_template("errors/post_not_found.html",
                message="This reel is not publicly available.",
                profile=profile), 404
        if pid and reel_visibility not in ("public", None):
            if reel_visibility == "private" and reel.get("profile_id") != pid:
                return render_template("errors/post_not_found.html",
                    message="This reel is private.", profile=profile), 404
            if reel_visibility == "followers" and reel.get("profile_id") != pid:
                from services.relationship_privacy_service import can_view_posts
                if not can_view_posts(pid, reel.get("profile_id")):
                    return render_template("errors/post_not_found.html",
                        message="This reel is for followers only.", profile=profile), 404
        has_liked = False
        if profile:
            has_liked = is_liked(profile.get("id"), "reel", reel_id)
            track_interaction_safe(
                profile.get("id"),
                target_type="reel",
                target_id=reel_id,
                action_type="open",
                source_surface="reels",
            )
        return render_template("reels/detail.html",
            reel=reel, comments=[], profile=profile,
            has_liked=has_liked)

    @app.route("/post/<post_id>")
    def post_detail(post_id):
        from services.content_service import get_post_by_id
        from services.comments_service import get_comments
        from services.profile_service import get_current_profile
        from services.engagement_service import is_liked
        from services.ai.interaction_service import track_interaction_safe
        profile = get_current_profile()
        post = get_post_by_id(post_id, viewer_profile_id=(profile or {}).get("id"))
        if not post:
            return render_template("errors/post_not_found.html",
                message="This post could not be found. It may have been deleted or made private.",
                profile=profile), 404
        comments = get_comments("post", post_id)
        has_liked = False
        if profile:
            has_liked = is_liked(profile.get("id"), "post", post_id)
            track_interaction_safe(
                profile.get("id"),
                target_type="post",
                target_id=post_id,
                action_type="open",
                source_surface="profile",
            )
        return render_template("posts/detail.html",
            post=post, comments=comments, profile=profile,
            has_liked=has_liked)

    @app.route("/features/create-post")
    @login_required
    def feature_create_post():
        return redirect(url_for("posts.create"))

    @app.route("/features/upload-reel")
    @login_required
    def feature_upload_reel():
        return redirect(url_for("reels.upload"))

    @app.route("/features/upload-video")
    @login_required
    def feature_upload_video():
        return redirect(url_for("marketplace.marketplace_create"))

    @app.route("/business/flyer-generator")
    @login_required
    def flyer_generator():
        from services.profile_service import get_current_profile
        profile = get_current_profile()
        return render_template("business/flyer_generator.html", current_user=profile or {})

    @app.route("/games/")
    def games_redirect():
        return redirect(url_for("discovery.section"), 302)

    @app.route("/favicon.ico")
    def favicon():
        favicon_path = os.path.join(app.static_folder or "static", "img", "favicon.ico")
        if os.path.exists(favicon_path):
            return send_from_directory(os.path.join(app.static_folder or "static", "img"), "favicon.ico")
        return ("", 204)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def handle_500(e):
        log_error("internal_server_error", error=e)
        if request.path.startswith("/api/"):
            return jsonify({"error": "internal_error", "request_id": getattr(g, "request_id", None)}), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(Exception)
    def page_error(error):
        if isinstance(error, HTTPException):
            return error
        log_error("request_error", error=error, status_code=500)
        if request.path.startswith("/api/"):
            return jsonify({"error": "internal_error", "request_id": getattr(g, "request_id", None)}), 500
        return render_template("errors/500.html"), 500

    _prewarm_done = False

    @app.before_request
    def _first_request_warm():
        nonlocal _prewarm_done
        if _prewarm_done:
            return
        _prewarm_done = True
        _log_reels_prewarm("considered", path=request.path, prewarm_considered=True)
        if _skip_first_request_neon_prewarm() or _is_fast_public_request():
            _log_reels_prewarm(
                "skipped",
                path=request.path,
                prewarm_skipped=True,
                skip_reason="fast_public_request" if _is_fast_public_request() else "reels_request",
            )
            return
        _log_reels_prewarm(
            "skipped",
            path=request.path,
            prewarm_skipped=True,
            skip_reason="worker_background_warm_disabled",
        )

    @app.after_request
    def apply_performance_headers(response):
        started = getattr(g, "request_started_at", None)
        if started is not None:
            elapsed_ms = (time.perf_counter() - started) * 1000
            response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.1f}"
            response.headers["X-Request-Id"] = getattr(g, "request_id", "")
            observe_route(request.path, elapsed_ms, response.status_code)
            
            is_prod = os.getenv("ENV") == "production"
            threshold = app.config.get("SLOW_REQUEST_MS_PROD" if is_prod else "SLOW_REQUEST_MS_LOCAL")
            
            if elapsed_ms >= threshold:
                # Log slow request once per 60s per route
                cache_key_slow = f"slow_log_{request.endpoint}_{request.path}"
                from engines.cache_engine import get_cache, set_cache
                if not get_cache(cache_key_slow):
                    log_warning("slow_request", duration_ms=round(elapsed_ms, 1), status_code=response.status_code, threshold_ms=threshold)
                    set_cache(cache_key_slow, True, ttl=60)
            if os.environ.get("CHAIN_REELS_PERF_DEBUG", "").lower() in {"1", "true", "yes", "on"} and request.path.startswith("/reels"):
                log_info(
                    "reels_request_timing",
                    request_id=getattr(g, "request_id", None),
                    worker_pid=os.getpid(),
                    path=request.path,
                    request_total_ms=round(elapsed_ms, 2),
                    after_request_total_ms=round((time.perf_counter() - started) * 1000, 2),
                    homepage_background_tasks_active=0,
                )
        if response.status_code >= 500:
            increment("http_5xx")

        response.headers.setdefault("Vary", "Accept-Encoding, Cookie")
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        elif request.method == "GET" and request.path in {"/", "/home"}:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif request.method == "GET" and (request.path.startswith(("/discover/", "/feed/", "/feed")) or request.path in {"/search", "/reels/", "/reels", "/status/", "/dating/discover", "/live/"}):
            response.headers["Cache-Control"] = "public, max-age=30"
        elif request.method == "GET" and request.path.startswith(("/auth/", "/profile/", "/chat/", "/wallet/", "/notifications/")):
            response.headers["Cache-Control"] = "no-store"

        if _is_production_env():
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.before_request
    def prime_neon_on_first_request():
        """Prime the Neon pool on the very first request."""
        if _app_test_mode():
            return
        if not getattr(app, '_neon_primed', False):
            app._neon_primed = True
            _log_reels_prewarm("considered", path=request.path, prewarm_considered=True)
            if _is_fast_public_request() or _skip_first_request_neon_prewarm():
                _log_reels_prewarm(
                    "skipped",
                    path=request.path,
                    prewarm_skipped=True,
                    skip_reason="fast_public_request" if _is_fast_public_request() else "reels_request",
                )
                return
            if _flag_enabled("CHAIN_ALLOW_WORKER_BACKGROUND_WARM"):
                try:
                    _log_reels_prewarm("started", path=request.path, prewarm_started=True)
                    from services.neon_service import prime_neon_runtime
                    prime_neon_runtime()
                except Exception:
                    pass

    _log_startup_stage("create_app_complete", create_app_total_ms=round((time.perf_counter() - startup_perf_started) * 1000, 2))

    return app


def _startup_background_prewarm(app):
    """Start background prewarm thread for homepage cache and Neon pool."""
    if _startup_fast_mode() or _app_test_mode() or not _flag_enabled("CHAIN_ALLOW_WORKER_BACKGROUND_WARM"):
        return

    def delayed_prewarm():
        time.sleep(2)
        print("[app] Prewarming homepage cache and Neon pool...")
        with app.app_context():
            try:
                prime_neon_runtime()
                check_readiness()
                prime_live_rooms_public_cache(limit=8)
                warm_homepage_cache()
                print("[app] Startup prewarm complete")
            except Exception as e:
                print(f"[app] Startup prewarm failed: {e}")

    threading.Thread(target=delayed_prewarm, daemon=True).start()


app = create_app()


if os.getenv("CHAIN_DEV_DIAGNOSTICS") == "1":
    app.register_blueprint(dev_diagnostics_bp)

AVAIL_ROUTES = {rule.rule for rule in app.url_map.iter_rules()}

if __name__ == "__main__":
    from services.socketio_service import socketio

    is_production = os.getenv("FLASK_ENV") == "production" or os.getenv("ENV") == "production"
    port = int(os.getenv("PORT", "5000"))
    
    # Use socketio.run in all environments to enable WebSocket support
    # In production, use gunicorn with GeventWebSocketWorker (gunicorn.conf.py)
    socketio.run(app, host="0.0.0.0", port=port, debug=not is_production, use_reloader=False)
