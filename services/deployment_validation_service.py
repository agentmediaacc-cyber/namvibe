import os


REQUIRED_ENV_VARS = ["SECRET_KEY", "DATABASE_URL"]


def validate_required_env_vars():
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    return {"ok": not missing, "missing": missing, "required": REQUIRED_ENV_VARS}


def validate_ssl_configuration():
    ready = os.getenv("CHAIN_HTTPS_READY", "0") == "1" or os.getenv("FLASK_ENV") == "production"
    domain = os.getenv("CHAIN_PUBLIC_DOMAIN") or os.getenv("APP_DOMAIN")
    return {"ok": ready and bool(domain), "https_ready": ready, "domain_configured": bool(domain)}


def validate_worker_configuration():
    configured = os.getenv("CHAIN_WORKERS_ENABLED", "0") == "1" or os.getenv("WORKER_COUNT")
    return {"ok": bool(configured), "configured": bool(configured), "command": "python scripts/run_worker.py --worker-name worker-1 --worker-type default"}


def validate_scheduler_configuration():
    configured = os.getenv("CHAIN_SCHEDULER_ENABLED", "0") == "1"
    return {"ok": configured, "configured": configured, "command": "python scripts/run_scheduler.py --interval 10"}


def validate_redis_configuration():
    configured = bool(os.getenv("REDIS_URL") or os.getenv("CHAIN_REDIS_URL"))
    return {"ok": configured, "configured": configured}


def validate_database_configuration():
    configured = bool(os.getenv("DATABASE_URL"))
    return {"ok": configured, "configured": configured}


def validate_environment():
    checks = {
        "required_env": validate_required_env_vars(),
        "ssl": validate_ssl_configuration(),
        "workers": validate_worker_configuration(),
        "scheduler": validate_scheduler_configuration(),
        "redis": validate_redis_configuration(),
        "database": validate_database_configuration(),
        "turn": {"ok": bool(os.getenv("TURN_URL") or os.getenv("TWILIO_ACCOUNT_SID")), "configured": bool(os.getenv("TURN_URL") or os.getenv("TWILIO_ACCOUNT_SID"))},
        "push": {"ok": bool(os.getenv("VAPID_PUBLIC_KEY") or os.getenv("FCM_SERVER_KEY")), "configured": bool(os.getenv("VAPID_PUBLIC_KEY") or os.getenv("FCM_SERVER_KEY"))},
        "storage": {"ok": bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY")), "configured": bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))},
    }
    blockers = [name for name, value in checks.items() if not value.get("ok") and name in {"required_env", "database", "ssl"}]
    warnings = [name for name, value in checks.items() if not value.get("ok") and name not in blockers]
    return {"ok": not blockers, "checks": checks, "blockers": blockers, "warnings": warnings}


def generate_deployment_report():
    env = validate_environment()
    score = max(0, 100 - len(env.get("blockers", [])) * 20 - len(env.get("warnings", [])) * 8)
    return {"ok": env.get("ok"), "score": score, **env}
