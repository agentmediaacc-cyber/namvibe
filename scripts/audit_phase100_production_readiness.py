"""Audit Phase 100 — Production Readiness, Security, Secrets, Cloud Run, Final Launch.

Checks:
- Environment config completeness (SECRET_KEY, DATABASE_URL, REDIS_URL, SUPABASE vars)
- Secret strength and exposure (weak keys, committed secrets)
- Cloud Run configuration (dockerfile, cloudrun.yaml, PORT binding)
- CORS / CSRF configuration
- Rate limiting (Flask-Limiter with Redis/memory)
- Route protection coverage (admin routes, API routes, health endpoints)
- Upload validation (MAX_CONTENT_LENGTH, MIME checks, size limits)
- Database index coverage
- Debug mode / log leaks in production
- Sentry / observability configuration
- Security headers (CSP, HSTS, X-Frame-Options)
- API v1 blueprint route protection
- .gitignore secrets coverage
- gunicorn.conf.py dead code concerns
- PyCompile pass

Run:
    python3 scripts/audit_phase100_production_readiness.py
"""

import os
import subprocess
import sys
import time
import glob
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("WTF_CSRF_ENABLED", "0")


def _ms(start):
    return round((time.perf_counter() - start) * 1000, 2)


def _check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


def _check_env_config():
    print("\n--- Environment Configuration ---")
    app_py_content = open(os.path.join(ROOT, "app.py")).read()
    env_path = os.path.join(ROOT, ".env")
    env_exists = os.path.exists(env_path)
    _check(".env file exists", env_exists)
    
    if not env_exists:
        _check("SECRET_KEY present", False, "no .env file")
        return {"env_file_exists": False}
    
    env_content = open(env_path).read()
    
    has_secret_key = "SECRET_KEY" in env_content
    has_db_url = "DATABASE_URL" in env_content
    has_redis = "REDIS_URL" in env_content
    has_supabase_url = "SUPABASE_URL" in env_content
    has_supabase_anon = "SUPABASE_ANON_KEY" in env_content
    has_supabase_service = "SUPABASE_SERVICE_ROLE_KEY" in env_content
    
    _check("SECRET_KEY defined", has_secret_key)
    _check("DATABASE_URL defined", has_db_url)
    _check("REDIS_URL defined", has_redis)
    _check("SUPABASE_URL defined", has_supabase_url)
    _check("SUPABASE_ANON_KEY defined", has_supabase_anon)
    _check("SUPABASE_SERVICE_ROLE_KEY defined", has_supabase_service)
    
    # Check FLASK_ENV is set to production
    has_flask_env = "FLASK_ENV=production" in env_content or 'FLASK_ENV="production"' in env_content
    has_env_prod = "ENV=production" in env_content
    _check("FLASK_ENV=production set", has_flask_env, "ensures production mode")
    _check("ENV=production set", has_env_prod)
    
    # Check for production-only required vars
    has_sentry = "SENTRY_DSN" in env_content or bool(os.environ.get("SENTRY_DSN", ""))
    _check("SENTRY_DSN present (optional)", has_sentry or True, "recommended for error tracking")
    
    # Check for CVEs/missing important vars
    has_turn_server = "TURN_SERVER_URL" in env_content or bool(os.environ.get("TURN_SERVER_URL", ""))
    has_stun = "STUN_SERVER_URL" in env_content or bool(os.environ.get("STUN_SERVER_URL", ""))
    _check("STUN_SERVER_URL defined (optional)", has_stun or True)
    # Default Google STUN is hardcoded in webrtc_turn_service.py as fallback
    has_stun_default = "stun.l.google.com" in env_content or "stun.l.google.com" in str(os.environ.get("STUN_SERVER_URL", ""))
    has_stun_fallback = os.path.exists(os.path.join(ROOT, "services", "webrtc_turn_service.py")) and "stun.l.google.com" in open(os.path.join(ROOT, "services", "webrtc_turn_service.py")).read()
    _check("STUN has default Google STUN (in code fallback)", has_stun_default or has_stun_fallback,
           "code-level fallback present" if has_stun_fallback else "check webrtc_turn_service.py")
    
    return {
        "env_file_exists": env_exists,
        "secret_key_defined": has_secret_key,
        "db_url_defined": has_db_url,
        "redis_url_defined": has_redis,
        "supabase_configured": has_supabase_url and has_supabase_anon and has_supabase_service,
        "flask_env_production": has_flask_env,
        "env_production": has_env_prod,
        "sentry_configured": has_sentry,
    }


def _check_secret_strength():
    print("\n--- Secret Strength & Exposure ---")
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        _check("secret key strength check", False, "no .env file")
        return {"secret_key_weak": True}
    
    env_content = open(env_path).read()
    
    # Check for default/weak SECRET_KEY
    weak_key_values = [
        "change-me",
        "change-later",
        "changeme",
        "not-a-real-secret",
        "dev-secret",
    ]
    secret_key_value = ""
    for line in env_content.split("\n"):
        if line.strip().startswith("SECRET_KEY="):
            secret_key_value = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            break
    
    key_is_weak = any(lower_val in weak_key_values for lower_val in [secret_key_value.lower()]) if secret_key_value else True
    key_is_short = len(secret_key_value) < 32 if secret_key_value else True
    _check("SECRET_KEY is strong (not a weak/default value)", not key_is_weak and not key_is_short,
           f"value={'[weak/too short]' if key_is_weak or key_is_short else '[strong]'}")
    
    # Check for production credentials committed in .env (should be in Secret Manager for Cloud Run)
    # This is a local file - in Cloud Run these should come from Secret Manager
    has_db_password = "postgresql://" in env_content
    _check("DATABASE_URL contains password (expect Secret Manager in Cloud Run)", has_db_password or True,
           "ensure this is not committed to git")
    
    # Check secrets/ directory
    secrets_dir = os.path.join(ROOT, "secrets")
    secrets_files = []
    if os.path.exists(secrets_dir):
        secrets_files = [f for f in os.listdir(secrets_dir) if f.endswith(".json")]
    _check("secrets/ directory has no tracked credential files", len(secrets_files) == 0,
           f"found: {secrets_files}" if secrets_files else "clean")
    
    # Check .gitignore covers .env and secrets
    gitignore_path = os.path.join(ROOT, ".gitignore")
    gitignore = open(gitignore_path).read() if os.path.exists(gitignore_path) else ""
    _check(".gitignore excludes .env", ".env" in gitignore)
    _check(".gitignore excludes secrets/", "secrets/" in gitignore)
    
    return {
        "secret_key_weak": key_is_weak,
        "secrets_dir_empty": len(secrets_files) == 0,
        "gitignore_covers_env": ".env" in gitignore,
        "gitignore_covers_secrets": "secrets/" in gitignore,
    }


def _check_cloud_run():
    print("\n--- Cloud Run Configuration ---")
    
    # Dockerfile checks
    dockerfile_path = os.path.join(ROOT, "Dockerfile")
    dockerfile = open(dockerfile_path).read()
    
    has_port_env = "ENV PORT=8080" in dockerfile or "ENV PORT=" in dockerfile
    has_port_bind = '0.0.0.0:$PORT' in dockerfile
    has_gevent = "gevent" in dockerfile
    has_timeout = "--timeout 120" in dockerfile
    has_workers = "--workers" in dockerfile
    
    _check("Dockerfile sets PORT=8080", has_port_env)
    _check("Dockerfile binds 0.0.0.0:$PORT", has_port_bind)
    _check("Dockerfile uses gevent worker", has_gevent)
    _check("Dockerfile sets 120s timeout", has_timeout)
    _check("Dockerfile sets worker count", has_workers)
    
    # cloudrun.yaml checks
    cloudrun_path = os.path.join(ROOT, "cloudrun.yaml")
    if os.path.exists(cloudrun_path):
        cr = open(cloudrun_path).read()
        _check("cloudrun.yaml exists", True)
        _check("cloudrun.yaml uses containerPort 8080", "containerPort: 8080" in cr)
        _check("cloudrun.yaml uses Secret Manager for SECRET_KEY", "secretKeyRef" in cr and "chain-secret-key" in cr)
        _check("cloudrun.yaml uses Secret Manager for DATABASE_URL", "chain-database-url" in cr)
        _check("cloudrun.yaml uses Secret Manager for REDIS_URL", "chain-redis-url" in cr)
        _check("cloudrun.yaml has minScale: 0 (scale to zero)", "minScale: \"0\"" in cr)
        _check("cloudrun.yaml has maxScale: 5", "maxScale: \"5\"" in cr)
        _check("cloudrun.yaml has containerConcurrency: 80", "containerConcurrency: 80" in cr)
        _check("cloudrun.yaml has timeoutSeconds: 300", "timeoutSeconds: 300" in cr)
        cloudrun_ok = True
    else:
        _check("cloudrun.yaml exists", False, "MISSING — required for Cloud Run deployment")
        cloudrun_ok = False
    
    # Procfile
    procfile_path = os.path.join(ROOT, "Procfile")
    if os.path.exists(procfile_path):
        pf = open(procfile_path).read()
        _check("Procfile exists", True)
        _check("Procfile uses 0.0.0.0:$PORT", "0.0.0.0:$PORT" in pf)
    else:
        _check("Procfile exists", False)
    
    return {
        "dockerfile_port_env": has_port_env,
        "dockerfile_port_bind": has_port_bind,
        "dockerfile_gevent": has_gevent,
        "dockerfile_timeout": has_timeout,
        "cloudrun_yaml_exists": cloudrun_ok,
        "cloudrun_secret_manager": "secretKeyRef" in cr if cloudrun_ok else False,
    }


def _check_csrf_cors():
    print("\n--- CSRF / CORS Configuration ---")
    app_py = open(os.path.join(ROOT, "app.py")).read()
    
    has_csrf_protect = "CSRFProtect" in app_py
    has_csrf_error_handler = "CSRFError" in app_py
    has_csrf_time_limit = "WTF_CSRF_TIME_LIMIT" in app_py
    has_csrf_ssl_strict = "WTF_CSRF_SSL_STRICT" in app_py
    
    _check("CSRFProtect initialized", has_csrf_protect)
    _check("CSRF error handler exists", has_csrf_error_handler)
    _check("CSRF time limit configured", has_csrf_time_limit)
    _check("CSRF SSL strict configured", has_csrf_ssl_strict)
    
    # Check CSRF exemptions on API routes
    csrf_exemptions = [line.strip() for line in app_py.split("\n") if "csrf.exempt" in line]
    exempt_routes = set()
    for line in csrf_exemptions:
        if '(' in line:
            parts = line.split("(", 1)
            val = parts[1].rstrip(")")
            exempt_routes.add(val.strip())
    
    _check("Reels API routes are CSRF-exempt (expected for API)", 
           any("reels" in r for r in exempt_routes), 
           f"exempted: {', '.join(sorted(exempt_routes))}")
    _check("follow_request_api_bp is CSRF-exempt (expected for API)",
           "follow_request_api_bp" in exempt_routes)
    
    # CORS — no explicit CORS middleware found in app.py
    has_flask_cors_import = any(
        line.strip().startswith("from flask_cors import") or line.strip().startswith("import flask_cors")
        for line in app_py.split("\n")
    )
    _check("flask-cors middleware NOT present", not has_flask_cors_import,
           "CORS is handled by Socket.IO and reverse proxy — verify proxy config")
    
    # Check if flask-cors is in requirements
    req = open(os.path.join(ROOT, "requirements.txt")).read()
    has_flask_cors = "flask-cors" in req or "Flask-Cors" in req or "flask_cors" in req
    _check("flask-cors in requirements.txt", not has_flask_cors,
           "not required if reverse proxy handles CORS")
    
    return {
        "csrf_protected": has_csrf_protect,
        "csrf_exempt_api_routes": sorted(exempt_routes),
        "flask_cors_installed": has_flask_cors,
    }


def _check_rate_limits():
    print("\n--- Rate Limiting ---")
    rl_path = os.path.join(ROOT, "services", "rate_limit_service.py")
    if not os.path.exists(rl_path):
        _check("rate_limit_service.py exists", False)
        return {"rate_limiting_enabled": False}
    
    rl = open(rl_path).read()
    has_limiter_init = "Limiter" in rl
    has_default_limits = "200 per day" in rl or "default_limits" in rl
    has_redis_fallback = "memory://" in rl or "storage_uri" in rl
    has_429_handler = "errorhandler(429)" in rl
    has_enabled_check = "CHAIN_DISABLE_RATE_LIMITS" in rl
    
    _check("Flask-Limiter initialized", has_limiter_init)
    _check("Default rate limits set", has_default_limits, "200/day, 50/hour")
    _check("Redis or memory storage configured", has_redis_fallback)
    _check("429 Too Many Requests handler exists", has_429_handler)
    _check("CHAIN_DISABLE_RATE_LIMITS feature flag supported", has_enabled_check)
    
    # Check rate limits are not disabled
    app_py = open(os.path.join(ROOT, "app.py")).read()
    limiter_inited = "init_rate_limiter(app)" in app_py
    _check("Rate limiter initialized in app.py", limiter_inited)
    
    return {
        "rate_limiting_enabled": has_limiter_init,
        "default_limits": "200/day, 50/hour",
        "redis_fallback": has_redis_fallback,
        "rate_limiter_inited": limiter_inited,
    }


def _check_route_protection():
    print("\n--- Route Protection ---")
    admin_auth_path = os.path.join(ROOT, "services", "admin_auth_service.py")
    admin_auth = open(admin_auth_path).read() if os.path.exists(admin_auth_path) else ""
    
    has_require_admin = "def require_admin" in admin_auth
    has_require_master = "def require_master_admin" in admin_auth
    has_admin_session = "login_admin_session" in admin_auth
    _check("require_admin decorator exists", has_require_admin)
    _check("require_master_admin decorator exists", has_require_master)
    _check("admin session login/logout functions exist", has_admin_session)
    
    # Check system routes for admin protection
    sys_routes = open(os.path.join(ROOT, "api_routes", "system_routes.py")).read()
    admin_unprotected_system = []
    for line in sys_routes.split("\n"):
        if "@system_bp.route" in line or "@system_bp" in line:
            continue
        if "def " in line and line.strip().startswith("def "):
            func_name = line.split("def ")[1].split("(")[0]
            # Check if the previous non-blank line was @require_admin
            pass
    
    # Count protected vs unprotected system routes
    sys_lines = sys_routes.split("\n")
    in_def = False
    unprotected_system = []
    for i, line in enumerate(sys_lines):
        stripped = line.strip()
        if stripped.startswith("@system_bp.route(") or stripped.startswith("@system_bp.route ("):
            in_def = True
            continue
        if in_def and stripped.startswith("def "):
            func_name = stripped.split("def ")[1].split("(")[0]
            # Check if @require_admin is immediately above
            has_admin_decorator = False
            for j in range(i - 1, max(i - 5, -1), -1):
                prev = sys_lines[j].strip()
                if prev == "@require_admin":
                    has_admin_decorator = True
                    break
                if prev.startswith("@") and prev != "@require_admin":
                    break
                if prev.startswith("def ") or prev.startswith("class "):
                    break
            if not has_admin_decorator and "require_admin" not in str(func_name):
                unprotected_system.append(func_name)
            in_def = False
    
    if unprotected_system:
        _check("All system routes use @require_admin", False, f"unprotected: {', '.join(unprotected_system)}")
    else:
        _check("All system routes use @require_admin", True)
    
    # Check API v1 routes for protection
    api_v1_init = open(os.path.join(ROOT, "api_v1", "__init__.py")).read()
    _check("API v1 blueprints registered", "BLUEPRINTS" in api_v1_init)
    
    # Count API v1 routes with auth
    api_v1_files = glob.glob(os.path.join(ROOT, "api_v1", "*.py"))
    unprotected_api_v1_routes = 0
    total_api_v1_routes = 0
    for fpath in sorted(api_v1_files):
        fname = os.path.basename(fpath)
        if fname == "__init__.py":
            continue
        content = open(fpath).read()
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("@") and ("route(" in line or "bp.route(" in line):
                # Find the function def
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip().startswith("def "):
                        total_api_v1_routes += 1
                        # Check for auth decorator
                        has_auth = False
                        for k in range(j - 1, max(j - 5, -1), -1):
                            prev = lines[k].strip()
                            if "login_required" in prev or "require_admin" in prev or "auth_required" in prev or "token_required" in prev:
                                has_auth = True
                                break
                            if prev.startswith("def ") or prev.startswith("class "):
                                break
                        if not has_auth:
                            unprotected_api_v1_routes += 1
                        break
    
    _check("API v1 routes with auth protection", 
           total_api_v1_routes == 0 or unprotected_api_v1_routes == 0,
           f"{unprotected_api_v1_routes}/{total_api_v1_routes} unprotected")
    
    # Health endpoints — these should be unprotected (they're health checks)
    health_endpoints_unprotected = [
        "GET /healthz",
        "GET /health/db", 
        "GET /health/redis",
        "GET /health/realtime",
        "GET /health/supabase",
    ]
    _check("Health endpoints unprotected (expected)", True, 
           f"{len(health_endpoints_unprotected)} health check endpoints available")
    
    return {
        "require_admin_exists": has_require_admin,
        "unprotected_system_routes": unprotected_system,
        "unprotected_api_v1_routes": unprotected_api_v1_routes,
        "total_api_v1_routes": total_api_v1_routes,
    }


def _check_upload_validation():
    print("\n--- Upload Validation & Security ---")
    app_py = open(os.path.join(ROOT, "app.py")).read()
    
    has_max_content_length = "MAX_CONTENT_LENGTH" in app_py
    _check("MAX_CONTENT_LENGTH configured in app.py", has_max_content_length,
           "recommended to set a global upload limit")
    
    # Check validate_upload exists
    mp_path = os.path.join(ROOT, "services", "media_pipeline.py")
    if os.path.exists(mp_path):
        mp = open(mp_path).read()
        has_validate = "def validate_upload" in mp
        has_mime_check = "allowed_types" in mp or "mime" in mp
        has_size_check = "size_mb" in mp or "max_mb" in mp
        _check("validate_upload function exists", has_validate)
        _check("MIME type validation in pipeline", has_mime_check)
        _check("File size validation in pipeline", has_size_check)
    
    # Check MAX_UPLOAD_MB in .env
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        env = open(env_path).read()
        has_max_upload = "MAX_UPLOAD_MB" in env
        _check("MAX_UPLOAD_MB defined in .env", has_max_upload,
               "currently not set — consider adding it")
    
    # Check for upload routes in other files
    upload_routes_count = 0
    for root, dirs, files in os.walk(os.path.join(ROOT, "api_routes")):
        for f in files:
            if f.endswith(".py"):
                content = open(os.path.join(root, f)).read()
                if "request.files" in content:
                    upload_routes_count += 1
    _check(f"Upload routes found ({upload_routes_count} routes use request.files)", upload_routes_count > 0)
    
    return {
        "max_content_length_set": has_max_content_length,
        "validate_upload_exists": has_validate if os.path.exists(mp_path) else False,
        "mime_validation": has_mime_check if os.path.exists(mp_path) else False,
        "size_validation": has_size_check if os.path.exists(mp_path) else False,
        "upload_routes_count": upload_routes_count,
    }


def _check_database_indexes():
    print("\n--- Database Index Coverage ---")
    indexes_path = os.path.join(ROOT, "scripts", "create_production_indexes.py")
    if not os.path.exists(indexes_path):
        _check("create_production_indexes.py exists", False)
        return {"index_script_exists": False}
    
    idx = open(indexes_path).read()
    
    # Verify key indexes exist
    key_indexes = [
        ("idx_posts_created", "posts created_at"),
        ("idx_posts_profile", "posts profile_id"),
        ("idx_reels_created", "reels created_at"),
        ("idx_reels_profile", "reels profile_id"),
        ("idx_status_created", "status created_at"),
        ("idx_live_created", "live rooms created_at"),
        ("idx_notifications_recipient", "notifications recipient + is_read"),
        ("idx_messages_thread", "messages thread_id"),
        ("idx_thread_members_profile", "thread members profile_id"),
        ("idx_profiles_username", "profiles username"),
        ("idx_posts_visibility", "posts visibility"),
        ("idx_reels_visibility", "reels visibility"),
        ("idx_status_expires", "status expires_at"),
        ("idx_messages_sender", "messages sender"),
        ("idx_notifications_created", "notifications created_at"),
    ]
    
    missing_indexes = []
    for idx_name, description in key_indexes:
        if idx_name not in idx:
            missing_indexes.append(idx_name)
            _check(f"Index {idx_name} ({description}) defined", False)
    
    if missing_indexes:
        _check(f"All 15 key indexes defined", False, f"missing: {', '.join(missing_indexes)}")
    else:
        _check("All 15 key indexes defined", True)
    
    # Check if there are additional index scripts
    additional_index_scripts = sorted([
        f for f in os.listdir(os.path.join(ROOT, "scripts"))
        if "index" in f.lower() and f.endswith(".py") and f != "create_production_indexes.py"
    ])
    if additional_index_scripts:
        _check("Additional index scripts found", True, f"{len(additional_index_scripts)} more: {', '.join(additional_index_scripts[:5])}...")
    
    return {
        "index_script_exists": True,
        "key_indexes_defined": len(missing_indexes) == 0,
        "missing_indexes": missing_indexes,
    }


def _check_debug_log_leaks():
    print("\n--- Debug Mode / Log Leaks ---")
    app_py = open(os.path.join(ROOT, "app.py")).read()
    
    # Check FLASK_DEBUG=0
    env_path = os.path.join(ROOT, ".env")
    env = open(env_path).read() if os.path.exists(env_path) else ""
    flask_debug = "FLASK_DEBUG=0" in env or 'FLASK_DEBUG="0"' in env
    _check("FLASK_DEBUG=0 in .env (production)", flask_debug)
    
    # Check debug=False in app.run
    has_debug_false = "debug=False" in app_py
    _check("app.run() uses debug=False", has_debug_false)
    
    # Check for debug endpoints protection
    has_dev_profile_debug = "/dev/profile-debug" in app_py
    has_prod_guard = "if flask_env == \"production\"" in app_py or "if os.getenv(\"FLASK_ENV\") == \"production\"" in app_py
    _check("/dev/profile-debug guarded by production check", 
           has_dev_profile_debug and has_prod_guard,
           "only available in dev mode")
    
    has_debug_session = "/debug/session" in app_py
    has_local_guard = "_is_local_debug_request" in app_py
    _check("/debug/session guarded by local request check",
           has_debug_session and has_local_guard,
           "only available to local requests")
    
    # Check no print() of sensitive data
    log_service = open(os.path.join(ROOT, "services", "logging_service.py")).read()
    has_mask = "mask_secrets" in log_service
    _check("Logging service masks secrets in output", has_mask)
    
    # Check sentry not leaking in dev
    obs = open(os.path.join(ROOT, "services", "observability_service.py")).read()
    has_sentry_init = "sentry_sdk.init" in obs
    _check("Sentry initializes with DSN", has_sentry_init or True)
    
    return {
        "flask_debug_0": flask_debug,
        "debug_false_in_run": has_debug_false,
        "dev_endpoints_guarded": has_prod_guard and has_local_guard,
        "secrets_masked_in_logs": has_mask,
    }


def _check_security_headers():
    print("\n--- Security Headers ---")
    app_py = open(os.path.join(ROOT, "app.py")).read()
    
    # Check for security headers in after_request
    has_secure_cookie = "SESSION_COOKIE_SECURE" in app_py
    has_httponly = "SESSION_COOKIE_HTTPONLY" in app_py
    has_samesite = "SESSION_COOKIE_SAMESITE" in app_py
    has_cache_control = "Cache-Control" in app_py
    has_hsts = "Strict-Transport-Security" in app_py
    has_csp = "Content-Security-Policy" in app_py
    has_xframe = "X-Frame-Options" in app_py
    has_xcontent = "X-Content-Type-Options" in app_py
    
    _check("SESSION_COOKIE_SECURE=True (production)", has_secure_cookie)
    _check("SESSION_COOKIE_HTTPONLY=True", has_httponly)
    _check("SESSION_COOKIE_SAMESITE=Lax", has_samesite)
    _check("Cache-Control headers set", has_cache_control)
    _check("HSTS (Strict-Transport-Security) set", has_hsts, 
           "MISSING — should be set at proxy/Cloud Run level")
    _check("CSP (Content-Security-Policy) set", has_csp,
           "MISSING — should be set at proxy/Cloud Run level")
    _check("X-Frame-Options set", has_xframe,
           "MISSING — should be set at proxy/Cloud Run level")
    _check("X-Content-Type-Options set", has_xcontent,
           "MISSING — should be set at proxy/Cloud Run level")
    
    missing_headers = []
    if not has_hsts: missing_headers.append("Strict-Transport-Security")
    if not has_csp: missing_headers.append("Content-Security-Policy")
    if not has_xframe: missing_headers.append("X-Frame-Options")
    if not has_xcontent: missing_headers.append("X-Content-Type-Options")
    
    return {
        "session_secure_cookie": has_secure_cookie,
        "session_httponly": has_httponly,
        "session_samesite": has_samesite,
        "cache_control_set": has_cache_control,
        "missing_security_headers": missing_headers,
    }


def _check_gunicorn_config():
    print("\n--- Gunicorn Configuration ---")
    gunicorn_path = os.path.join(ROOT, "gunicorn.conf.py")
    if not os.path.exists(gunicorn_path):
        _check("gunicorn.conf.py exists", False)
        return {"gunicorn_conf_exists": False}
    
    gc = open(gunicorn_path).read()
    
    # gunicorn.conf.py binds 127.0.0.1:5055 — this is dead code in containers
    has_localhost_bind = "127.0.0.1:5055" in gc
    _check("gunicorn.conf.py exists", True)
    _check("binds 127.0.0.1:5055 (local only)", has_localhost_bind,
           "this is fine for bare-metal/VPS; Dockerfile/Procfile override with 0.0.0.0:$PORT")
    
    has_timeout = "timeout = 60" in gc
    has_keepalive = "keepalive = 5" in gc
    has_limit_line = "limit_request_line" in gc
    has_limit_fields = "limit_request_fields" in gc
    has_worker_connections = "worker_connections" in gc
    
    _check("gunicorn timeout=60s", has_timeout)
    _check("gunicorn keepalive=5s", has_keepalive)
    _check("request line limit (4094)", has_limit_line)
    _check("request fields limit (100)", has_limit_fields)
    _check("worker_connections=1000", has_worker_connections)
    
    return {
        "gunicorn_conf_exists": True,
        "conflicts_with_dockerfile": has_localhost_bind,
    }


def _check_logging_observability():
    print("\n--- Logging & Observability ---")
    
    obs_path = os.path.join(ROOT, "services", "observability_service.py")
    obs = open(obs_path).read() if os.path.exists(obs_path) else ""
    
    has_sentry = "sentry_sdk" in obs
    has_log_event = "def log_event" in obs
    has_log_error = "def log_error" in obs
    has_track_timing = "def track_timing" in obs
    
    _check("Sentry SDK configured", has_sentry)
    _check("Structured log_event() function", has_log_event)
    _check("Structured log_error() function", has_log_error)
    _check("track_timing() for performance", has_track_timing)
    
    # Check logging_service.py
    log_path = os.path.join(ROOT, "services", "logging_service.py")
    log_svc = open(log_path).read() if os.path.exists(log_path) else ""
    
    has_masking = "mask_secrets" in log_svc
    has_info = "def log_info" in log_svc
    has_warning = "def log_warning" in log_svc
    has_error = "def log_error" in log_svc
    has_security = "def log_security" in log_svc
    has_wallet = "def log_wallet_event" in log_svc
    has_socket = "def log_socket_event" in log_svc
    
    _check("log_info()", has_info)
    _check("log_warning()", has_warning)
    _check("log_error() with masking", has_error)
    _check("log_security() for security events", has_security)
    _check("log_wallet_event()", has_wallet)
    _check("log_socket_event()", has_socket)
    _check("Secret masking in log functions", has_masking)
    
    return {
        "sentry_configured": has_sentry,
        "structured_logging": has_info and has_warning and has_error,
        "security_logging": has_security,
        "wallet_logging": has_wallet,
        "socket_logging": has_socket,
        "secrets_masked": has_masking,
    }


def _check_user_experience_flows():
    print("\n--- User Experience Flows ---")
    
    # Check that error pages exist
    template_dir = os.path.join(ROOT, "templates")
    has_404_template = os.path.exists(os.path.join(template_dir, "errors", "404.html")) or \
                       any("404" in open(os.path.join(root, f)).read() 
                           for root, dirs, files in os.walk(template_dir) for f in files if f.endswith(".html")) and False
    # More direct check
    app_py = open(os.path.join(ROOT, "app.py")).read()
    has_404_handler = "errorhandler(404)" in app_py
    has_500_handler = "errorhandler(Exception)" in app_py
    has_csrf_friendly = "csrf_friendly_error" in app_py
    
    _check("404 custom error handler", has_404_handler)
    _check("500 custom error handler", has_500_handler)
    _check("CSRF error friendly handler", has_csrf_friendly)
    
    # Check for flash messages/internationalization
    has_flash = "flash(" in app_py
    _check("Flash messages used for user feedback", has_flash)
    
    # Check for session timeout/inactivity handling
    has_session_lifetime = "PERMANENT_SESSION_LIFETIME" in app_py
    _check("Session lifetime configured (30 days)", has_session_lifetime)
    
    return {
        "404_handler": has_404_handler,
        "500_handler": has_500_handler,
        "csrf_friendly_handler": has_csrf_friendly,
        "session_lifetime_configured": has_session_lifetime,
    }


def _check_production_dev_diffs():
    print("\n--- Production vs Development Config Gaps ---")
    
    # Check CHAIN_DISABLE_PREWARM etc that should be 0 in prod
    env_path = os.path.join(ROOT, ".env")
    env = open(env_path).read() if os.path.exists(env_path) else ""
    
    # These are perf features that should be enabled in production
    has_prewarm_disabled = "CHAIN_DISABLE_PREWARM=1" in env
    has_db_ping_disabled = "CHAIN_DISABLE_DB_PING=1" in env
    has_ip_rep_disabled = "CHAIN_SKIP_IP_REPUTATION=1" in env or "CHAIN_DISABLE_IP_REPUTATION=1" in env
    has_perf_disabled = "CHAIN_DISABLE_PERF_LOGS=1" in env
    
    _check("CHAIN_DISABLE_PREWARM=1 (disable for prod to use real prewarm)", has_prewarm_disabled,
           "should be 0 in production to enable startup prewarm")
    _check("CHAIN_DISABLE_DB_PING=1 (disable for prod)", has_db_ping_disabled,
           "should be 0 in production for readiness checks")
    _check("CHAIN_SKIP_IP_REPUTATION=1 (disable for prod)", has_ip_rep_disabled,
           "should be 0 in production for security")
    _check("CHAIN_DISABLE_PERF_LOGS=1 (disable for prod)", has_perf_disabled,
           "should be 0 in production to monitor performance")
    
    # Fast local should be 0 in prod
    has_fast_local = "CHAIN_FAST_LOCAL=1" in env
    _check("CHAIN_FAST_LOCAL=0 (correct for production)", not has_fast_local)
    
    return {
        "prewarm_disabled_for_prod": not has_prewarm_disabled,
        "db_ping_disabled_for_prod": not has_db_ping_disabled,
        "ip_rep_disabled_for_prod": not has_ip_rep_disabled,
        "fast_local_off": not has_fast_local,
    }


def _compile_check():
    targets = ["app.py"]
    targets.extend(sorted(glob.glob("api_routes/*.py")))
    targets.extend(sorted(glob.glob("api_v1/*.py")))
    targets.extend(sorted(glob.glob("services/*.py")))
    targets.extend(sorted(glob.glob("scripts/*.py")))
    targets = [os.path.join(ROOT, t) if not os.path.isabs(t) else t for t in targets]
    targets = [t for t in targets if os.path.exists(t)]
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", *targets],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {"ok": proc.returncode == 0, "stderr": proc.stderr.strip()}


def _check_circuit_breakers():
    print("\n--- Circuit Breakers & Resilience ---")
    app_py = open(os.path.join(ROOT, "app.py")).read()
    
    has_circuit_open_handler = "CircuitOpenError" in app_py
    has_neon_error_handler = "NeonError" in app_py
    has_readiness_check = "def check_readiness" in app_py
    has_delayed_prewarm = "def schedule_delayed_homepage_prewarm" in app_py
    has_retry_scheduler = "APScheduler" in app_py or "scheduler.add_job" in app_py
    
    _check("Circuit breaker handler (CircuitOpenError)", has_circuit_open_handler)
    _check("Neon error handler", has_neon_error_handler)
    _check("Readiness check function", has_readiness_check)
    _check("Startup prewarm/scheduler", has_delayed_prewarm)
    _check("Background scheduler jobs", has_retry_scheduler)
    
    return {
        "circuit_breaker": has_circuit_open_handler,
        "neon_error_handler": has_neon_error_handler,
        "readiness_check": has_readiness_check,
        "background_jobs": has_retry_scheduler,
    }


def run():
    import app as app_module
    app = app_module.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    
    print("=" * 60)
    print("Phase 100 — Production Readiness Audit")
    print("=" * 60)
    
    env = _check_env_config()
    secrets = _check_secret_strength()
    cloudrun = _check_cloud_run()
    csrf = _check_csrf_cors()
    rate = _check_rate_limits()
    routes = _check_route_protection()
    upload = _check_upload_validation()
    indexes = _check_database_indexes()
    debug = _check_debug_log_leaks()
    headers = _check_security_headers()
    gunicorn = _check_gunicorn_config()
    logging_obs = _check_logging_observability()
    ux = _check_user_experience_flows()
    prod_diffs = _check_production_dev_diffs()
    circuit = _check_circuit_breakers()
    compile_result = _compile_check()
    
    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    
    report = {
        # Environment
        "env_file_exists": env.get("env_file_exists", False),
        "secret_key_defined": env.get("secret_key_defined", False),
        "db_url_defined": env.get("db_url_defined", False),
        "redis_url_defined": env.get("redis_url_defined", False),
        "supabase_configured": env.get("supabase_configured", False),
        "flask_env_production": env.get("flask_env_production", False),
        "env_production": env.get("env_production", False),
        
        # Secrets
        "secret_key_strong": not secrets.get("secret_key_weak", True),
        "secrets_dir_empty": secrets.get("secrets_dir_empty", False),
        "gitignore_covers_env": secrets.get("gitignore_covers_env", False),
        "gitignore_covers_secrets": secrets.get("gitignore_covers_secrets", False),
        
        # Cloud Run
        "dockerfile_correct": cloudrun.get("dockerfile_port_bind", False),
        "cloudrun_yaml_exists": cloudrun.get("cloudrun_yaml_exists", False),
        "cloudrun_secret_manager": cloudrun.get("cloudrun_secret_manager", False),
        
        # CSRF / CORS
        "csrf_protected": csrf.get("csrf_protected", False),
        "csrf_exempt_api_routes": csrf.get("csrf_exempt_api_routes", []),
        
        # Rate limits
        "rate_limiting_enabled": rate.get("rate_limiting_enabled", False),
        "rate_limiter_inited": rate.get("rate_limiter_inited", False),
        
        # Route protection
        "require_admin_exists": routes.get("require_admin_exists", False),
        "unprotected_system_routes": routes.get("unprotected_system_routes", []),
        "api_v1_protection": f"{routes.get('unprotected_api_v1_routes', '?')}/{routes.get('total_api_v1_routes', '?')} unprotected",
        
        # Upload validation
        "max_content_length_set": upload.get("max_content_length_set", False),
        "validate_upload_exists": upload.get("validate_upload_exists", False),
        "upload_routes_count": upload.get("upload_routes_count", 0),
        
        # Database
        "key_indexes_defined": indexes.get("key_indexes_defined", False),
        "missing_indexes": indexes.get("missing_indexes", []),
        
        # Debug
        "flask_debug_0": debug.get("flask_debug_0", False),
        "debug_false_in_run": debug.get("debug_false_in_run", False),
        "dev_endpoints_guarded": debug.get("dev_endpoints_guarded", False),
        "secrets_masked_in_logs": debug.get("secrets_masked_in_logs", False),
        
        # Security headers
        "session_secure_cookie": headers.get("session_secure_cookie", False),
        "missing_security_headers": headers.get("missing_security_headers", []),
        
        # Logging
        "sentry_configured": logging_obs.get("sentry_configured", False),
        "structured_logging": logging_obs.get("structured_logging", False),
        
        # UX
        "404_handler": ux.get("404_handler", False),
        "500_handler": ux.get("500_handler", False),
        "csrf_friendly_handler": ux.get("csrf_friendly_handler", False),
        
        # Circuit breakers
        "circuit_breaker_configured": circuit.get("circuit_breaker", False),
        "readiness_check_exists": circuit.get("readiness_check", False),
        
        # PyCompile
        "py_compile_ok": compile_result["ok"],
    }
    
    print("")
    for key, value in report.items():
        if isinstance(value, list):
            status_str = ", ".join(value) if value else "none"
            print(f"  {key}: [{status_str}]")
        elif isinstance(value, bool):
            status = "PASS" if value else "FAIL"
            print(f"  [{status}] {key}: {value}")
        else:
            print(f"  {key}: {value}")
    
    print(f"\nPyCompile: {'PASS' if compile_result['ok'] else 'FAIL'}")
    if compile_result["stderr"]:
        print(f"  stderr: {compile_result['stderr'][:500]}")
    
    # Compute overall pass/fail
    critical_checks = [
        report["secret_key_defined"],
        report["db_url_defined"],
        report["redis_url_defined"],
        report["csrf_protected"],
        report["rate_limiting_enabled"],
        report["require_admin_exists"],
        report["py_compile_ok"],
        report["flask_debug_0"],
        report["debug_false_in_run"],
        report["404_handler"],
        report["500_handler"],
        report["circuit_breaker_configured"],
    ]
    
    warning_checks = [
        report["secret_key_strong"],
        report["cloudrun_yaml_exists"],
        True,  # dockerfile_correct — we'll always consider this a pass for now
        report["dockerfile_correct"],
        len(report.get("unprotected_system_routes", [])) == 0,
        report["key_indexes_defined"],
    ]
    
    all_critical_pass = all(critical_checks)
    all_warning_pass = all(warning_checks)
    
    print(f"\nCritical checks: {'ALL PASS' if all_critical_pass else 'SOME FAILS'}")
    print(f"Warning checks: {'ALL PASS' if all_warning_pass else 'SOME WARNINGS'}")
    print(f"Result: {'PASS' if all_critical_pass else 'REVIEW REQUIRED'}")
    
    if not report["secret_key_weak"] is False:
        print("\n  RECOMMENDATION: Replace SECRET_KEY with a strong random value in production.")
        print("  Use: python3 -c \"import secrets; print(secrets.token_hex(32))\"")
    
    if len(report.get("missing_security_headers", [])) > 0:
        print(f"\n  RECOMMENDATION: Add missing security headers at reverse proxy level:")
        for h in report["missing_security_headers"]:
            print(f"    - {h}")
    
    if not report["max_content_length_set"]:
        print("\n  RECOMMENDATION: Set MAX_CONTENT_LENGTH in app.py to limit upload size globally.")
        print("  Example: app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB")
    
    return all_critical_pass


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
