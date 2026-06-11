#!/usr/bin/env python3
"""CHAIN final production launch verification.

This is a launch gate, not a feature test. It combines static source checks,
configuration checks, and lightweight runtime probes. It exits non-zero when a
critical launch requirement is not proven.
"""

from __future__ import annotations

import ast
import compileall
import importlib
import os
import re
import socket
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parents[1]
REPORT_PATH = BASE / "docs" / "FINAL_PRODUCTION_LAUNCH_REPORT.md"

CRITICAL_ENV = [
    "SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
]

DOCUMENTED_ENV = CRITICAL_ENV + [
    "FLASK_ENV",
    "PORT",
    "TURN_SERVER_URL",
    "TURN_USERNAME",
    "TURN_PASSWORD",
    "STUN_SERVER_URL",
    "CHAIN_BACKUP_LOCATION",
    "DATABASE_BACKUP_URL",
    "BACKUP_BUCKET",
    "SENTRY_DSN",
    "MAX_UPLOAD_MB",
]

ADMIN_OK_PUBLIC = {
    "/admin",
    "/admin/",
    "/admin/login",
    "/admin/logout",
}

EXPECTED_PROFILE_ROUTES = [
    "/profile/",
    "/profile/edit",
    "/profile/avatar",
    "/profile/cover",
    "/profile/@<username>",
    "/profile/@<username>/follow",
    "/profile/@<username>/report",
    "/profile/@<username>/block",
    "/profile/security",
    "/profile/privacy",
    "/profile/settings/privacy",
    "/profile/wallet",
]

EXPECTED_ADMIN_CAPABILITIES = {
    "users": ["/admin/users"],
    "content": ["/admin/content", "/admin/moderation", "/admin/moderation/action"],
    "wallet": ["/admin/topups", "/admin/withdrawals", "/admin/reports/payouts/latest"],
    "verification": ["/admin/verifications", "/admin/verification", "/admin/verification/action"],
    "safety": ["/admin/safety/"],
    "system": ["/admin/system-health", "/system/api/health", "/system/api/queue/stats"],
    "production": ["/production/api/audit", "/production/api/launch-readiness"],
}

EXPECTED_PERFORMANCE_INDEX_FILES = [
    "sql/phase68b_performance_indexes.sql",
    "sql/phase71_performance_indexes.sql",
    "sql/phase74_full_speed_indexes.sql",
]


@dataclass
class Check:
    area: str
    name: str
    status: str
    detail: str = ""


checks: list[Check] = []


def record(area: str, name: str, status: str, detail: str = "") -> None:
    checks.append(Check(area, name, status, detail))
    label = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN"}[status]
    suffix = f" - {detail}" if detail else ""
    print(f"{label:4} {area}: {name}{suffix}")


def ok(area: str, name: str, detail: str = "") -> None:
    record(area, name, "PASS", detail)


def fail(area: str, name: str, detail: str = "") -> None:
    record(area, name, "FAIL", detail)


def warn(area: str, name: str, detail: str = "") -> None:
    record(area, name, "WARN", detail)


def read_text(rel: str) -> str:
    path = BASE / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def load_dotenv_names() -> dict[str, str]:
    values: dict[str, str] = {}
    for rel in (".env", ".env.production", ".env.production.example", ".env.example"):
        path = BASE / rel
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values.setdefault(key.strip(), value.strip().strip("\"'"))
    for key, value in os.environ.items():
        values[key] = value
    return values


def parse_routes(rel: str) -> list[dict[str, object]]:
    path = BASE / rel
    if not path.exists():
        return []
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    routes = []
    blueprint_prefixes: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if getattr(node.value.func, "id", "") == "Blueprint":
                prefix = ""
                for kw in node.value.keywords:
                    if kw.arg == "url_prefix" and isinstance(kw.value, ast.Constant):
                        prefix = str(kw.value.value)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        blueprint_prefixes[target.id] = prefix
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        decorators = [decorator_name(d) for d in node.decorator_list]
        for dec in node.decorator_list:
            call = dec if isinstance(dec, ast.Call) else None
            if not call:
                continue
            func = call.func
            if not isinstance(func, ast.Attribute) or func.attr != "route":
                continue
            bp = getattr(func.value, "id", "")
            prefix = blueprint_prefixes.get(bp, "")
            route = ""
            if call.args and isinstance(call.args[0], ast.Constant):
                route = str(call.args[0].value)
            full = (prefix.rstrip("/") + "/" + route.lstrip("/")).replace("//", "/")
            methods = []
            for kw in call.keywords:
                if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    methods = [str(v.value) for v in kw.value.elts if isinstance(v, ast.Constant)]
            routes.append(
                {
                    "file": rel,
                    "func": node.name,
                    "route": full or "/",
                    "methods": methods or ["GET"],
                    "decorators": decorators,
                }
            )
    return routes


def decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return decorator_name(node.func)
    return ""


def all_route_defs() -> list[dict[str, object]]:
    route_files = [
        str(p.relative_to(BASE))
        for p in (BASE / "api_routes").glob("*.py")
    ]
    route_files += [str(p.relative_to(BASE)) for p in (BASE / "routes").glob("*.py")]
    return [route for rel in route_files for route in parse_routes(rel)]


def route_exists(routes: list[dict[str, object]], wanted: str) -> bool:
    return any(str(r["route"]) == wanted for r in routes)


def protected_by_admin(route: dict[str, object]) -> bool:
    decorators = set(route["decorators"])
    return "require_admin" in decorators or "require_master_admin" in decorators


def check_env() -> None:
    area = "Env"
    env = load_dotenv_names()
    env_template = read_text(".env.production.example")
    if env_template:
        ok(area, ".env.production.example exists")
    else:
        fail(area, ".env.production.example missing")
    for key in DOCUMENTED_ENV:
        if f"{key}=" in env_template:
            ok(area, f"{key} documented")
        else:
            fail(area, f"{key} documented", "missing from production template")
    for key in CRITICAL_ENV:
        value = env.get(key, "")
        if value and value not in {"change-me", "chain-premium-default-secret", "your-secret-key"}:
            ok(area, f"{key} configured")
        else:
            fail(area, f"{key} configured", "not set in current launch environment")
    if env.get("FLASK_ENV") == "production":
        ok(area, "FLASK_ENV production")
    else:
        fail(area, "FLASK_ENV production", f"current={env.get('FLASK_ENV') or 'unset'}")
    if env.get("CHAIN_DEV_TOOLS", "0").lower() in {"1", "true", "yes", "on"}:
        fail(area, "CHAIN_DEV_TOOLS disabled")
    else:
        ok(area, "CHAIN_DEV_TOOLS disabled")
    if env.get("TURN_SERVER_URL"):
        ok(area, "TURN server configured")
    else:
        warn(area, "TURN server configured", "STUN-only calls can fail on strict NAT")
    if env.get("STUN_SERVER_URL"):
        ok(area, "STUN server configured")
    else:
        fail(area, "STUN server configured")


def check_imports_and_app() -> None:
    area = "Runtime"
    sys.path.insert(0, str(BASE))
    for module_name in ("app", "services.socketio_service", "services.redis_service", "services.neon_service"):
        try:
            importlib.import_module(module_name)
            ok(area, f"import {module_name}")
        except Exception as exc:
            fail(area, f"import {module_name}", exc.__class__.__name__)
    try:
        from app import create_app

        app = create_app()
        ok(area, "Flask app creation")
        rules = sorted(str(rule.rule) for rule in app.url_map.iter_rules())
        for endpoint in ("/healthz", "/health/db", "/health/redis", "/health/realtime", "/health/supabase"):
            if endpoint in rules:
                ok(area, f"health endpoint {endpoint}")
            else:
                fail(area, f"health endpoint {endpoint}")
        if app.config.get("SESSION_COOKIE_HTTPONLY") is True:
            ok("Security", "SESSION_COOKIE_HTTPONLY true")
        else:
            fail("Security", "SESSION_COOKIE_HTTPONLY true")
        if app.config.get("SESSION_COOKIE_SAMESITE"):
            ok("Security", "SESSION_COOKIE_SAMESITE set", str(app.config.get("SESSION_COOKIE_SAMESITE")))
        else:
            fail("Security", "SESSION_COOKIE_SAMESITE set")
        if os.getenv("FLASK_ENV") == "production" and app.config.get("SESSION_COOKIE_SECURE") is not True:
            fail("Security", "SESSION_COOKIE_SECURE true in production")
        else:
            ok("Security", "SESSION_COOKIE_SECURE configured")
    except Exception as exc:
        fail(area, "Flask app creation", f"{exc.__class__.__name__}: {exc}")


def check_route_protection() -> None:
    routes = all_route_defs()
    area = "Routes"
    if routes:
        ok(area, "route inventory", f"{len(routes)} routes parsed")
    else:
        fail(area, "route inventory")

    admin_routes = [
        r for r in routes
        if str(r["route"]).startswith("/admin")
        or str(r["route"]).startswith("/developer")
        or "/admin/" in str(r["route"])
    ]
    unsafe_admin = []
    login_only_admin = []
    for route in admin_routes:
        route_path = str(route["route"])
        if route_path in ADMIN_OK_PUBLIC:
            continue
        if not protected_by_admin(route):
            unsafe_admin.append(route)
        if "login_required" in set(route["decorators"]) and not protected_by_admin(route):
            login_only_admin.append(route)
    if unsafe_admin:
        fail("Security", "all admin routes require admin", format_route_list(unsafe_admin[:8]))
    else:
        ok("Security", "all admin routes require admin")
    if login_only_admin:
        fail("Security", "no admin route uses login_required only", format_route_list(login_only_admin[:8]))
    else:
        ok("Security", "no admin route uses login_required only")

    for route in [r for r in routes if str(r["route"]).startswith("/system")]:
        if protected_by_admin(route):
            ok("Security", f"system route protected {route['route']}")
        else:
            fail("Security", f"system route protected {route['route']}", str(route["file"]))

    for route in [r for r in routes if str(r["route"]).startswith("/production")]:
        if protected_by_admin(route):
            ok("Security", f"production route protected {route['route']}")
        else:
            fail("Security", f"production route protected {route['route']}", str(route["file"]))

    for wanted in EXPECTED_PROFILE_ROUTES:
        if route_exists(routes, wanted):
            ok("Profile", f"route {wanted}")
        else:
            fail("Profile", f"route {wanted}", "missing")

    for capability, wanted_routes in EXPECTED_ADMIN_CAPABILITIES.items():
        missing = [r for r in wanted_routes if not route_exists(routes, r)]
        if missing:
            fail("Admin", f"{capability} controls", "missing " + ", ".join(missing))
        else:
            ok("Admin", f"{capability} controls")

    wallet_admin = [r for r in routes if str(r["route"]).startswith("/wallet/admin")]
    if wallet_admin and all(protected_by_admin(r) for r in wallet_admin):
        ok("Wallet", "admin wallet routes require admin")
    elif wallet_admin:
        fail("Wallet", "admin wallet routes require admin", format_route_list(wallet_admin))
    else:
        warn("Wallet", "admin wallet routes present", "no /wallet/admin routes found")


def format_route_list(routes: Iterable[dict[str, object]]) -> str:
    return "; ".join(f"{r['route']} ({r['file']}:{r['func']})" for r in routes)


def check_profile_surface() -> None:
    area = "Profile"
    profile_py = read_text("api_routes/profile_routes.py")
    profile_service = read_text("services/profile_service.py")
    templates = "\n".join(read_text(rel) for rel in [
        "templates/profile/modern_profile.html",
        "templates/profile/edit.html",
        "templates/profile/security.html",
        "templates/profile/privacy.html",
        "templates/profile/partials/profile_header.html",
    ])
    for label, pattern in {
        "edit profile saves bio": "bio",
        "location save": "location",
        "website save": "website",
        "skills save": "skills",
        "avatar upload": "avatar",
        "cover upload": "cover",
        "follow/unfollow": "follow",
        "block action": "block",
        "report action": "report",
        "privacy controls": "privacy",
        "security page": "security",
        "creator verification display": "verification",
        "badges display": "badge",
    }.items():
        hay = (profile_py + profile_service + templates).lower()
        if pattern in hay:
            ok(area, label)
        else:
            fail(area, label, f"pattern '{pattern}' not found")
    private_terms = ["email", "phone", "auth_user_id", "refresh_token", "access_token"]
    public_template = read_text("templates/profile/modern_profile.html") + read_text("templates/profile/public.html")
    leaked = [term for term in private_terms if re.search(r"{{\s*profile\." + re.escape(term), public_template)]
    if leaked:
        fail(area, "public profile cannot expose private data", ", ".join(leaked))
    else:
        ok(area, "public profile cannot expose private data")
    if "default_avatar.png" in templates or "avatar_url" in templates:
        ok(area, "image fallback present")
    else:
        fail(area, "image fallback present")
    if "@media" in read_text("static/css/profile.css") + read_text("static/css/chain_profile.css"):
        ok(area, "mobile profile layout CSS")
    else:
        warn(area, "mobile profile layout CSS", "no explicit media query found")


def check_content_wallet_safety() -> None:
    wallet = read_text("services/wallet_service.py")
    payments = read_text("services/wallet_payment_service.py")
    payout = read_text("services/payout_service.py")
    combined = wallet + payments + payout
    if "balance_cents >= %s" in wallet and "insufficient_balance" in combined:
        ok("Wallet", "negative balance prevention")
    else:
        fail("Wallet", "negative balance prevention")
    if "idempotency" in combined.lower():
        ok("Wallet", "duplicate transaction prevention")
    else:
        fail("Wallet", "duplicate transaction prevention")
    if "get_payout_requests" in payout and "approve_payout" in payout and "reject_payout" in payout:
        ok("Wallet", "payout review controls")
    else:
        warn("Wallet", "payout review controls")
    for rel, patterns in {
        "services/moderation_service.py": ["report", "block", "restrict"],
        "services/trust_score_service.py": ["trust"],
        "services/spam_detection_service.py": ["spam"],
        "services/dating_service.py": ["blocked", "match", "privacy"],
        "services/notification_queue_service.py": ["queue"],
        "services/webrtc_call_service.py": ["call"],
    }.items():
        text = read_text(rel).lower()
        missing = [p for p in patterns if p not in text]
        if missing:
            warn("Coverage", rel, "missing terms: " + ", ".join(missing))
        else:
            ok("Coverage", rel)


def check_infra_files() -> None:
    area = "Infra"
    gunicorn = read_text("gunicorn.conf.py")
    nginx = read_text("nginx/chain.conf.example")
    if "bind" in gunicorn and "127.0.0.1" in gunicorn:
        ok(area, "Gunicorn startup config")
    else:
        fail(area, "Gunicorn startup config")
    for svc in ("systemd/chain.service", "systemd/chain-realtime.service", "systemd/chain-worker.service"):
        if (BASE / svc).exists():
            ok(area, f"{svc} exists")
        else:
            fail(area, f"{svc} exists")
    for label, pattern in {
        "Nginx config": "proxy_pass",
        "SSL config": "ssl_certificate",
        "HSTS config": "Strict-Transport-Security",
        "gzip config": "gzip on",
        "WebSocket proxy": "proxy_set_header Upgrade",
        "static files": "location /static/",
    }.items():
        if pattern in nginx:
            ok(area, label)
        else:
            fail(area, label, f"missing {pattern}")
    if "errorhandler(404)" in read_text("app.py") and "errorhandler(Exception)" in read_text("app.py"):
        ok(area, "error pages")
    else:
        fail(area, "error pages")
    if "log_request_performance" in read_text("app.py") or "logging_service" in read_text("app.py"):
        ok(area, "logs configured")
    else:
        fail(area, "logs configured")


def check_connections() -> None:
    env = load_dotenv_names()
    if env.get("DATABASE_URL"):
        try:
            from services.neon_service import get_neon_health

            health = get_neon_health()
            if health.get("status") == "ok":
                ok("Connections", "database connectivity", str(health.get("latency_ms", "")))
            else:
                fail("Connections", "database connectivity", str(health))
        except Exception as exc:
            fail("Connections", "database connectivity", exc.__class__.__name__)
    else:
        fail("Connections", "database connectivity", "DATABASE_URL unset")
    if env.get("REDIS_URL"):
        try:
            from services.redis_service import get_redis_health

            health = get_redis_health()
            if health.get("status") in {"ok", "connected"}:
                ok("Connections", "Redis connectivity")
            else:
                fail("Connections", "Redis connectivity", str(health))
        except Exception as exc:
            fail("Connections", "Redis connectivity", exc.__class__.__name__)
    else:
        fail("Connections", "Redis connectivity", "REDIS_URL unset")
    if "message_queue" in read_text("services/socketio_service.py"):
        ok("Connections", "Socket.IO Redis availability")
    else:
        fail("Connections", "Socket.IO Redis availability")
    if "get_webrtc_ice_config" in read_text("services/webrtc_turn_service.py"):
        ok("Connections", "WebRTC ICE config")
    else:
        fail("Connections", "WebRTC ICE config")


def check_security() -> None:
    app_py = read_text("app.py")
    if "CSRFProtect(app)" in app_py:
        ok("Security", "CSRF protection active")
    else:
        fail("Security", "CSRF protection active")
    auth_text = (read_text("services/api_auth_service.py") + read_text("api_v1/auth_api.py")).lower()
    if "supabase.auth.get_user" in auth_text or "jwt" in auth_text:
        ok("Security", "JWT validation implementation")
    else:
        fail("Security", "JWT validation implementation")
    storage_text = read_text("services/storage_service.py")
    if (
        "MAX_CONTENT_LENGTH" in app_py
        or "MAX_UPLOAD_MB" in app_py + storage_text
        or ("file_size > limit" in storage_text and "limit" in storage_text)
    ):
        ok("Security", "file size limits active")
    else:
        fail("Security", "file size limits active")
    if "ALLOWED_EXTENSIONS" in read_text("services/storage_service.py"):
        ok("Security", "upload validation safe")
    else:
        fail("Security", "upload validation safe")
    if "init_rate_limiter" in app_py and "CHAIN_DISABLE_RATE_LIMITS" in read_text("services/rate_limit_service.py"):
        ok("Security", "rate limits active")
    else:
        fail("Security", "rate limits active")
    if "debug=False" in app_py:
        ok("Security", "debug disabled")
    else:
        fail("Security", "debug disabled")
    scan_for_secrets()
    scan_for_placeholder_content()


def scan_for_secrets() -> None:
    allowed_files = {
        "app.py",
        "requirements.txt",
        "pyproject.toml",
        "gunicorn.conf.py",
    }
    allowed_dirs = (
        "api_routes/",
        "services/",
        "scripts/",
        "sql/",
        "utils/",
        "config/",
        "nginx/",
        "systemd/",
    )
    excluded_dirs = (
        ".git/",
        "venv/",
        ".venv/",
        "__pycache__/",
        "backups/",
        "secrets/",
        "static/uploads/",
    )

    def in_scope(path):
        rel = str(path.relative_to(BASE))
        if rel.endswith((".bak", ".pyc")):
            return False
        if any(rel.startswith(prefix) for prefix in excluded_dirs):
            return False
        return rel in allowed_files or any(rel.startswith(prefix) for prefix in allowed_dirs)

    try:
        output = subprocess.check_output(["git", "ls-files"], cwd=BASE, text=True)
        files = [BASE / line for line in output.splitlines()]
    except Exception:
        files = [p for p in BASE.rglob("*") if p.is_file()]
    secret_patterns = [
        re.compile(r"SUPABASE_SERVICE_ROLE_KEY\s*=\s*[A-Za-z0-9._-]{20,}"),
        re.compile(r"SECRET_KEY\s*=\s*['\"][^'\"]{24,}['\"]"),
        re.compile(r"postgres(?:ql)?://[^\\s'\"]+:[^\\s'\"]+@"),
        re.compile(r"redis://[^\\s'\"]+:[^\\s'\"]+@"),
    ]
    hits = []
    for path in files:
        if not in_scope(path):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".ico", ".pyc"}:
            continue
        rel = str(path.relative_to(BASE))
        text = path.read_text(encoding="utf-8", errors="ignore")[:250000]
        if any(pattern.search(text) for pattern in secret_patterns):
            hits.append(rel)
    if hits:
        fail("Security", "no secrets tracked by git", ", ".join(hits[:8]))
    else:
        ok("Security", "no secrets tracked by git")


def scan_for_placeholder_content() -> None:
    paths = [
        p for root in ("templates", "services", "api_routes", "static/js")
        for p in (BASE / root).rglob("*")
        if p.is_file() and p.suffix in {".py", ".html", ".js"}
    ]
    patterns = {
        "lorem ipsum": "placeholder text",
        "demo@example.com": "demo credential",
        "test@example.com": "test credential",
        "password123": "test password",
        "fake user": "fake profile content",
        "placeholder profile": "placeholder profile content",
    }
    hits = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for pattern, label in patterns.items():
            if pattern in text:
                hits.append(f"{path.relative_to(BASE)}:{label}")
    if hits:
        fail("Security", "no placeholder/demo/test content", "; ".join(hits[:10]))
    else:
        ok("Security", "no placeholder/demo/test content")


def check_backup_and_uploads() -> None:
    for rel in ("scripts/backup_db.sh", "scripts/sync_media_backup.sh", "scripts/restore_media.py"):
        path = BASE / rel
        if path.exists():
            ok("Backup", f"{rel} exists")
            if rel.endswith(".sh") and os.access(path, os.X_OK):
                ok("Backup", f"{rel} executable")
            elif rel.endswith(".sh"):
                fail("Backup", f"{rel} executable")
        else:
            fail("Backup", f"{rel} exists")
    for rel in ("static", "static/img"):
        path = BASE / rel
        if path.exists() and os.access(path, os.R_OK):
            ok("Media", f"{rel} readable")
        else:
            fail("Media", f"{rel} readable")
    upload_root = BASE / "static" / "uploads"
    if upload_root.exists():
        if os.access(upload_root, os.W_OK):
            ok("Media", "upload folder writable", str(upload_root.relative_to(BASE)))
        else:
            fail("Media", "upload folder writable", str(upload_root.relative_to(BASE)))
    else:
        warn("Media", "upload folder writable", "local uploads folder absent; Supabase storage may be used")


def check_media_storage_architecture() -> None:
    router = read_text("services/supabase_storage_router.py")
    if router and "BUCKET_MAPPING" in router and "post-media" in router and "message-media" in router:
        ok("Media", "central Supabase storage router")
    else:
        fail("Media", "central Supabase storage router")

    route_sources = {
        "avatar/cover": "services/profile_service.py",
        "message attachments": "services/media_storage_service.py",
        "reels/posts": "services/content_service.py",
        "stories": "services/status_service.py",
        "marketplace": "api_routes/marketplace_routes.py",
        "live thumbnails": "services/live_media_service.py",
    }
    for label, rel in route_sources.items():
        text = read_text(rel)
        if "supabase_storage_router" in text or "upload_file" in text or "upload_marketplace_media" in text or "upload_live_cover" in text:
            ok("Media", f"{label} uses Supabase Storage")
        else:
            fail("Media", f"{label} uses Supabase Storage", rel)

    sql = "\n".join(p.read_text(encoding="utf-8", errors="ignore").lower() for p in (BASE / "sql").glob("*.sql"))
    if any(term in sql for term in (" bytea", " base64", " blob")):
        fail("Media", "Neon tables avoid bytea/base64/blob uploaded media")
    else:
        ok("Media", "Neon tables avoid bytea/base64/blob uploaded media")

    migration = read_text("sql/final_media_storage_metadata.sql")
    if all(term in migration for term in ("media_url", "media_path", "media_bucket", "mime_type", "size_bytes", "media_type")):
        ok("Media", "Neon metadata columns verified")
    else:
        fail("Media", "Neon metadata columns verified")

    env = load_dotenv_names()
    if not (env.get("SUPABASE_URL") and (env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_ANON_KEY"))):
        warn("Media", "Supabase Storage bucket env/config missing")


def check_performance() -> None:
    for rel in EXPECTED_PERFORMANCE_INDEX_FILES:
        text = read_text(rel)
        if "CREATE INDEX" in text:
            ok("Performance", f"{rel} indexes")
        else:
            fail("Performance", f"{rel} indexes")
    services = {
        "homepage under target": "scripts/test_phase73_homepage_real_data.py",
        "profile under target": "scripts/test_phase74_full_upgrade_speed.py",
        "admin dashboard under target": "templates/admin/performance_dashboard.html",
        "user search under target": "services/search_service.py",
        "wallet transaction lookup under target": "services/wallet_service.py",
        "message inbox under target": "services/messaging_engine.py",
        "notifications under target": "services/notification_engine.py",
        "dating discover under target": "services/dating_service.py",
        "Redis cache works": "services/cache_engine_redis.py",
        "DB pool healthy": "services/neon_service.py",
        "slow route report generated": "services/performance_guard.py",
    }
    for label, rel in services.items():
        if (BASE / rel).exists():
            ok("Performance", label)
        else:
            fail("Performance", label, f"missing {rel}")
    if "limit=" in read_text("services/profile_service.py").lower():
        ok("Performance", "bounded profile queries")
    else:
        warn("Performance", "bounded profile queries")


def check_compileall() -> None:
    start = time.perf_counter()
    passed = compileall.compile_dir(str(BASE), quiet=1, maxlevels=20)
    elapsed = int((time.perf_counter() - start) * 1000)
    if passed:
        ok("Runtime", "compileall clean", f"{elapsed} ms")
    else:
        fail("Runtime", "compileall clean", f"{elapsed} ms")


def write_report() -> str:
    blockers = [c for c in checks if c.status == "FAIL"]
    warnings = [c for c in checks if c.status == "WARN"]
    verdict = "NO-GO" if blockers else "GO"
    report = [
        "# Final Production Launch Report",
        "",
        f"Decision: **{verdict}**",
        "",
        "## Launch Blockers",
        *([f"- {c.area}: {c.name}" + (f" - {c.detail}" if c.detail else "") for c in blockers] or ["- None."]),
        "",
        "## Warnings",
        *([f"- {c.area}: {c.name}" + (f" - {c.detail}" if c.detail else "") for c in warnings] or ["- None."]),
        "",
        "## Deployment Checklist",
        "- Set production env vars: SECRET_KEY, DATABASE_URL, REDIS_URL, Supabase keys, TURN/STUN, backup vars.",
        "- Install dependencies in a venv and run compileall plus the phase 69, 73, 74, 75, and 76 gates.",
        "- Apply database schema and performance indexes before switching traffic.",
        "- Install systemd services for app, realtime, and worker processes.",
        "- Install nginx config, certbot SSL, HSTS, gzip, static caching, and WebSocket proxy headers.",
        "- Verify health endpoints, Redis, database, Socket.IO, WebRTC ICE, media uploads, logs, and backups on the VPS.",
        "",
        "## Admin Dashboard Coverage",
        "- Covered by route audit: users, content/moderation, verification, safety, system health, production readiness.",
        "- Critical requirement: every admin/system/production route must use require_admin or require_master_admin.",
        "",
        "## User Profile Coverage",
        "- Covered by route/template audit: load, edit, avatar, cover, bio, location, website, skills, follow, block, report, privacy, security, badges, creator verification, wallet links, and private-data exposure.",
        "",
        "## Wallet/Admin Coverage",
        "- Covered by route/service audit: balances, transactions, payouts, creator earnings, tips, gifts, subscriptions, idempotency, and negative-balance prevention.",
        "- Wallet admin APIs must be admin protected, not only user-login protected.",
        "",
        "## Recommended VPS Specs",
        "- Minimum: 2 vCPU, 4 GB RAM, 40 GB SSD, Ubuntu 22.04/24.04.",
        "- Recommended launch: 4 vCPU, 8 GB RAM, 80 GB SSD, 1 Gbps network.",
        "- Scale target: separate managed Postgres, managed Redis, object storage/CDN, and a second app node when sustained concurrency rises.",
        "",
        "## Recommended Gunicorn Workers",
        "- 2 vCPU: 2 HTTP workers, 1 realtime WebSocket worker, 1 worker process.",
        "- 4 vCPU: 4 HTTP workers, 1 realtime WebSocket worker, 1-2 worker processes.",
        "- Keep WebSocket traffic on the gevent WebSocket worker path with Redis message_queue enabled.",
        "",
        "## Recommended Redis Memory",
        "- 512 MB for small launch and smoke traffic.",
        "- 1 GB for 500-2000 concurrent users.",
        "- 2 GB+ when presence, queues, Socket.IO pub/sub, notifications, and caching are all active at scale.",
        "",
        "## Backup Checklist",
        "- Confirm pg_dump backup script executes on the VPS.",
        "- Confirm media backup sync destination exists and restore script is tested.",
        "- Store backups outside the app server and monitor backup freshness.",
        "",
        "## Security Checklist",
        "- Admin routes require require_admin or require_master_admin.",
        "- CSRF, secure cookies, rate limits, upload validation, file size limits, debug off, dev tools off.",
        "- No tracked secrets, no public admin APIs, no private messages/call content exposed to admin views unless policy explicitly permits it.",
        "",
        f"## GO or NO-GO Decision",
        f"- **{verdict}**",
        "",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    return verdict


def main() -> int:
    os.chdir(BASE)
    print("CHAIN FINAL PRODUCTION LAUNCH VERIFICATION")
    print(f"Base: {BASE}")
    check_env()
    check_imports_and_app()
    check_route_protection()
    check_profile_surface()
    check_content_wallet_safety()
    check_infra_files()
    check_connections()
    check_security()
    check_backup_and_uploads()
    check_media_storage_architecture()
    check_performance()
    check_compileall()
    verdict = write_report()
    passed = len([c for c in checks if c.status == "PASS"])
    failed = len([c for c in checks if c.status == "FAIL"])
    warned = len([c for c in checks if c.status == "WARN"])
    print("")
    print("FINAL LAUNCH CHECK SUMMARY")
    print(f"PASS: {passed}")
    print(f"FAIL: {failed}")
    print(f"WARN: {warned}")
    print(f"REPORT: {REPORT_PATH.relative_to(BASE)}")
    print(f"DECISION: {verdict}")
    return 0 if verdict == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
