import os
from flask import jsonify, request, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from services.log_sanitizer import sanitize_connection_url
from services.redis_service import _REDIS_URL, log_redis_warning, redis_available
from services.logging_service import log_warning, safe_print
from services.metrics_service import increment


limiter = Limiter(
    key_func=get_remote_address,
    strategy="fixed-window",
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    enabled=os.getenv("CHAIN_DISABLE_RATE_LIMITS") != "1",
)


def user_or_ip_key():
    return session.get("auth_user_id") or request.headers.get("X-Forwarded-For") or get_remote_address()

def init_rate_limiter(app):
    """Initializes Flask-Limiter with Redis or memory fallback."""
    storage_url = "memory://"
    try:
        if redis_available():
            storage_url = _REDIS_URL
            safe_print(f"[limiter] Using Redis storage: {sanitize_connection_url(storage_url)}")
        else:
            log_redis_warning("redis_limiter_fallback", "[limiter] Redis unavailable, using in-memory storage")
    except Exception as error:
        log_redis_warning("redis_limiter_init_error", f"[limiter] Redis check failed, using in-memory storage: {error}")

    try:
        app.config["RATELIMIT_STORAGE_URI"] = storage_url
        app.config["RATELIMIT_ENABLED"] = os.getenv("CHAIN_DISABLE_RATE_LIMITS") != "1"
        limiter.enabled = app.config["RATELIMIT_ENABLED"]
        limiter.init_app(app)
    except Exception as error:
        app.config["RATELIMIT_STORAGE_URI"] = "memory://"
        app.config["RATELIMIT_ENABLED"] = False
        limiter.enabled = False
        log_redis_warning("rate_limiter_disabled", f"[limiter] Failed to initialize limiter, disabling: {error}")

    @app.errorhandler(429)
    def _rate_limit_handler(error):
        message = "Too many requests. Please slow down and try again shortly."
        increment("rate_limit_violations")
        log_warning("rate_limited", path=request.path, key=user_or_ip_key())
        if request.path.startswith("/api/"):
            return jsonify({"error": "rate_limited", "message": message}), 429
        return message, 429
    return limiter


def limit_for_route(limiter, rule, key_func=None):
    def decorator(view_func):
        return limiter.limit(rule, key_func=key_func or get_remote_address)(view_func)
    return decorator
