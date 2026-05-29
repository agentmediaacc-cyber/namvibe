import os
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from flask import Flask, g, jsonify, redirect, render_template, request, session, send_from_directory
from werkzeug.exceptions import HTTPException
from engines.cache_engine import init_cache
from engines.performance_engine import timed
from engines.scheduler_engine import init_scheduler
from dotenv import load_dotenv

from api_routes.auth_routes import auth_bp
from api_routes.profile_routes import profile_bp
from api_routes.matching_routes import matching_bp
from api_routes.dating_routes import dating_bp
from api_routes.message_routes import message_bp
from api_routes.call_routes import call_bp
from api_routes.notification_routes import notification_engine_bp
from api_routes.live_routes import live_bp
from api_routes.wallet_routes import wallet_bp
from api_routes.admin_routes import admin_bp, developer_bp
from api_routes.discovery_routes import discovery_bp
from api_routes.activity_routes import activity_bp
from api_routes.search_routes import search_api_bp, search_bp
from api_routes.moderation_routes import moderation_bp
from api_routes.status_routes import status_bp
from api_routes.live_media_routes import live_media_bp
from api_routes.realtime_routes import realtime_bp
from api_routes.reels_routes import reels_bp
from api_routes.presence_routes import presence_bp
from api_routes.feed_routes import feed_bp
from api_routes.verification_routes import verification_bp
from api_routes.mobile_api_routes import mobile_api_bp
from api_routes.engagement_routes import engagement_bp
from api_routes.marketplace_routes import marketplace_bp
from api_routes.creator_routes import creator_bp
from api_routes.post_routes import post_bp
from api_routes.metrics_routes import metrics_bp
from api_v1 import BLUEPRINTS as api_v1_blueprints

from services.homepage_service import get_homepage_data, build_homepage_payload
from services.profile_service import get_current_profile, get_profile_by_username
from services.notification_service import get_my_notifications
from services.auth_service import get_current_user, refresh_chain_session
from api_routes.profile_routes import login_required
from services.neon_service import get_neon_health, get_pool_status, prime_neon_runtime
from services.live_service import prime_live_rooms_public_cache
from utils.supabase_client import SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL, get_supabase, get_supabase_admin

load_dotenv(dotenv_path=".env")
_SUPABASE_HEALTH_CACHE = {"expires_at": 0.0, "payload": None}

from services.request_cache import cache_clear
from services.logging_service import log_error, log_warning
from services.metrics_service import increment, observe_route

from services.socketio_service import init_socketio
from services.rate_limit_service import init_rate_limiter
from services.observability_service import init_observability
from services import socket_events # Registers events


def check_readiness():
    """Verifies that core backend services are responsive."""
    from services.neon_service import get_neon_health
    from services.redis_service import get_redis_health
    from services.logging_service import log_info, log_error
    
    neon = get_neon_health()
    redis = get_redis_health()
    
    is_ready = neon.get("status") == "ok" and redis.get("status") == "ok"
    if is_ready:
        log_info("startup_readiness_check_passed", neon_latency=neon.get("latency_ms"), redis_latency=redis.get("latency_ms"))
    else:
        log_error("startup_readiness_check_failed", neon_status=neon.get("status"), redis_status=redis.get("status"))
    
    return is_ready


def should_start_delayed_prewarm(debug=False):
    if os.getenv("CHAIN_DISABLE_PREWARM") == "1":
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
                check_readiness()
                prime_neon_runtime()
                prime_live_rooms_public_cache(limit=8)
                build_homepage_payload(async_warm=True)
                print("[app] Startup sequence complete")
            except Exception as e:
                print(f"[app] Startup sequence failed: {e}")

    threading.Thread(target=delayed_prewarm, daemon=True).start()
    return True


def create_app():
    app = Flask(__name__)
    
    flask_env = os.getenv("FLASK_ENV", "development")
    is_prod = flask_env == "production"
    
    secret_key = os.getenv("SECRET_KEY")
    if is_prod and not secret_key:
        raise RuntimeError("SECRET_KEY environment variable is required in production.")
    
    app.secret_key = secret_key or "chain-premium-default-secret"
    
    # Production Security Settings
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        SLOW_REQUEST_MS_LOCAL=500,
        SLOW_REQUEST_MS_PROD=1000
    )
    
    init_cache(app)
    init_scheduler(app)
    init_observability(app)
    app.limiter = init_rate_limiter(app)
    socketio = init_socketio(app)
    
    app.config.from_object("config.settings.Config")

    # Session and Security Configuration
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=is_prod,
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )

    @app.before_request
    def manage_session():
        # Skip for static files
        if request.path.startswith("/static"):
            return
            
        # Lightweight session restore only for protected routes
        protected_blueprints = {"profile", "message", "wallet", "admin", "creator", "dating", "call", "notifications"}
        
        # Check if current endpoint is in a protected blueprint
        if request.blueprint in protected_blueprints:
            from services.session_service import is_logged_in, refresh_supabase_session_if_needed
            if not is_logged_in():
                if session.get("refresh_token"):
                    refresh_supabase_session_if_needed()

    @app.context_processor
    def inject_auth_state():
        from services.session_service import is_logged_in
        return dict(is_logged_in=is_logged_in())

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(matching_bp)
    app.register_blueprint(dating_bp)
    app.register_blueprint(message_bp)
    app.register_blueprint(call_bp)
    app.register_blueprint(notification_engine_bp)
    app.register_blueprint(live_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(developer_bp)
    app.register_blueprint(discovery_bp)
    app.register_blueprint(activity_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(moderation_bp)
    app.register_blueprint(search_api_bp)
    app.register_blueprint(marketplace_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(live_media_bp)
    app.register_blueprint(realtime_bp)
    app.register_blueprint(reels_bp)
    app.register_blueprint(presence_bp)
    app.register_blueprint(feed_bp)
    app.register_blueprint(verification_bp)
    app.register_blueprint(mobile_api_bp)
    app.register_blueprint(engagement_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(post_bp)

    for bp in api_v1_blueprints:
        app.register_blueprint(bp, url_prefix=f"/api/v1{bp.url_prefix}")

    @app.after_request
    def after_request_cleanup(response):
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
    def track_request_start():
        g.request_started_at = time.perf_counter()
        g.request_id = str(uuid.uuid4())
        g.current_profile_id = session.get("auth_user_id")
        if session.get("refresh_token") and not session.get("access_token") and request.endpoint != "static":
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
            "wallet": ["/wallet/"],
            "profile": ["/profile/"],
            "login": ["/auth/login"],
            "register": ["/auth/register"],
            "friends": ["/friends/", "/discover/"],
            "reels": ["/reels/", "/discover/"],
            "notifications": ["/notifications/", "/profile/"],
            "dating": ["/dating/discover", "/discover/"],
            "create_post": ["/features/create-post", "/posts/create", "/post/create", "/create-post", "/profile/"],
            "create_story": ["/status/create", "/profile/"],
            "upload_reel": ["/features/upload-reel", "/reels/", "/profile/"],
            "upload_video": ["/features/upload-video", "/upload/video", "/media/upload", "/profile/"],
            "go_live": ["/live/studio", "/live/"],
            "settings": ["/profile/settings", "/discover/"],
            "help": ["/discover/"],
        }

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
        
        # Priority: auth_user_id in session
        if "auth_user_id" in session:
            if session.get("profile_warning") or session.get("age_check_required"):
                current_profile = session_profile_stub()
            else:
                current_profile = get_current_profile()
                if not current_profile:
                    current_profile = session_profile_stub()

        if current_profile and current_profile.get("id"):
            from services.notification_engine import unread_count
            unread_count = unread_count(current_profile["id"])
            
            from services.wallet_engine import ensure_wallet
            wallet = ensure_wallet(current_profile["id"])
            if wallet:
                wallet_balance = wallet.get("coin_balance", 0)

        return {
            "g_current": current_profile,
            "g_unread_count": unread_count,
            "g_wallet_balance": wallet_balance,
            "session": session,
            "safe_link": safe_link,
        }

    @app.route("/stories")
    @app.route("/stories/")
    def stories_root_redirect():
        return redirect("/status/", code=302)

    @app.route("/live/create")
    def live_create_root_redirect():
        return redirect("/live/studio", code=302)

    @app.route("/")
    def home():
        with timed("home"):
            return render_template("chain_home.html", **get_homepage_data())

    @app.route("/login")
    def legacy_login():
        return redirect("/auth/login", code=302)

    @app.route("/register")
    def legacy_register():
        return redirect("/auth/register", code=302)

    @app.route("/terms")
    def terms():
        return render_template("dashboard/legal.html", page_title="Terms of Service", page_intro="These terms explain how CHAIN works, what users can expect, and the standards for using premium live, chat, wallet, and discovery features.")

    @app.route("/privacy")
    def privacy():
        return render_template("dashboard/legal.html", page_title="Privacy Policy", page_intro="This page explains how CHAIN stores profile data, wallet activity, live interactions, and notifications when connected to Supabase.")

    @app.route("/healthz")
    def healthz():
        """Lightweight health check for load balancers. No external DB touch."""
        return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}), 200

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

    @app.route("/favicon.ico")
    def favicon():
        favicon_path = os.path.join(app.static_folder or "static", "img", "favicon.ico")
        if os.path.exists(favicon_path):
            return send_from_directory(os.path.join(app.static_folder or "static", "img"), "favicon.ico")
        return ("", 204)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("dashboard/feature_page.html", title="404 - Not Found", section="error"), 404

    @app.errorhandler(Exception)
    def page_error(error):
        if isinstance(error, HTTPException):
            return error
        log_error("request_error", error=error, status_code=500)
        if request.path.startswith("/api/"):
            return jsonify({"error": "internal_error", "request_id": getattr(g, "request_id", None)}), 500
        return render_template("dashboard/feature_page.html", title="Error", section="error"), 500

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
        if response.status_code >= 500:
            increment("http_5xx")

        response.headers.setdefault("Vary", "Accept-Encoding, Cookie")
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        elif request.method == "GET" and (request.path.startswith(("/discover/", "/feed/")) or request.path in {"/", "/search", "/reels/", "/status/", "/dating/discover", "/live/"}):
            response.headers["Cache-Control"] = "public, max-age=30"
        elif request.method == "GET" and request.path.startswith(("/auth/", "/profile/", "/chat/", "/wallet/", "/notifications/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    return app

app = create_app()

if __name__ == "__main__":
    from services.socketio_service import socketio

    is_production = os.getenv("FLASK_ENV") == "production" or os.getenv("ENV") == "production"
    port = int(os.getenv("PORT", "5000"))
    schedule_delayed_homepage_prewarm(app, debug=not is_production)
    
    if is_production:
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        socketio.run(app, host="0.0.0.0", port=port, debug=True, use_reloader=True)
