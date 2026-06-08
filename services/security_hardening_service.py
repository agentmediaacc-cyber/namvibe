import os


def check_secret_strength(secret_key=None):
    secret = secret_key if secret_key is not None else os.getenv("SECRET_KEY", "")
    weak = not secret or len(secret) < 32 or secret in {"chain-premium-default-secret", "dev", "secret"}
    return {"ok": not weak, "name": "SECRET_KEY strength", "warning": weak, "detail": "Use a 32+ character random secret."}


def check_debug_mode(app=None):
    debug = bool(getattr(app, "debug", False)) or os.getenv("FLASK_DEBUG") == "1"
    return {"ok": not debug, "name": "Debug mode disabled", "warning": debug}


def check_cookie_security(app=None):
    config = getattr(app, "config", {}) if app is not None else {}
    secure = bool(config.get("SESSION_COOKIE_SECURE", os.getenv("FLASK_ENV") == "production"))
    httponly = bool(config.get("SESSION_COOKIE_HTTPONLY", True))
    samesite = config.get("SESSION_COOKIE_SAMESITE", "Lax")
    return {"ok": secure and httponly and bool(samesite), "secure": secure, "httponly": httponly, "samesite": samesite}


def check_csrf_configuration():
    enabled = os.getenv("WTF_CSRF_ENABLED", "1") not in {"0", "false", "False"}
    return {"ok": enabled, "name": "CSRF configuration", "warning": not enabled}


def check_rate_limit_configuration():
    configured = bool(os.getenv("RATELIMIT_STORAGE_URI") or os.getenv("REDIS_URL") or os.getenv("CHAIN_REDIS_URL"))
    return {"ok": True, "configured": configured, "warning": not configured, "detail": "In-memory rate limiting is acceptable only for single-process local mode."}


def check_security_headers():
    https_ready = os.getenv("CHAIN_HTTPS_READY", "0") == "1" or os.getenv("FLASK_ENV") == "production"
    return {
        "ok": True,
        "https_ready": https_ready,
        "headers": ["Content-Security-Policy", "Strict-Transport-Security", "X-Content-Type-Options"],
        "warning": not https_ready,
    }


def generate_security_report(app=None):
    checks = [
        check_secret_strength(),
        check_debug_mode(app),
        check_cookie_security(app),
        check_csrf_configuration(),
        check_rate_limit_configuration(),
        check_security_headers(),
    ]
    warnings = [c for c in checks if c.get("warning")]
    critical = [c for c in checks if not c.get("ok") and c.get("name") in {"SECRET_KEY strength", "Debug mode disabled"}]
    score = max(0, 100 - len(warnings) * 8 - len(critical) * 15)
    return {"ok": not critical, "score": score, "checks": checks, "warnings": warnings, "critical": critical}
