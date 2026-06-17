#!/usr/bin/env python3
import os
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VENV_PYTHON = ROOT / "venv" / "bin" / "python3"
if os.environ.get("PHASE66C_VENV_REEXEC") != "1" and VENV_PYTHON.exists() and Path(sys.executable) != VENV_PYTHON:
    os.environ["PHASE66C_VENV_REEXEC"] = "1"
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])


def check(label, ok, details=""):
    status = "PASS" if ok else "FAIL"
    suffix = f" - {details}" if details else ""
    print(f"{status}: {label}{suffix}")
    return ok


def read(path):
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def route_exists(app, rule):
    return any(str(item) == rule for item in app.url_map.iter_rules())


def main():
    os.chdir(ROOT)
    os.environ.setdefault("FLASK_TESTING", "1")
    os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
    os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
    os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
    os.environ.setdefault("CHAIN_DISABLE_RATE_LIMITS", "1")

    checks = []

    from services.env_service import get_env, load_project_env

    load_project_env()
    from services.profile_context_service import build_profile_template_context

    sample_profile = {
        "id": "11111111-1111-4111-8111-111111111111",
        "username": "phase66",
        "display_name": "Phase 66",
    }
    context = build_profile_template_context(sample_profile, active_tab="reels")
    required_context = {
        "profile",
        "current_profile",
        "hero_profile",
        "viewer_profile",
        "viewer",
        "current",
        "public_stats",
        "profile_nav",
        "active_tab",
        "stats",
        "content",
        "wallet",
        "creator",
        "marketplace",
        "dating",
        "completion",
        "level",
        "pinned",
        "presence",
    }
    missing_context = sorted(required_context - set(context))
    checks.append(check("profile template context includes required variables", not missing_context, ", ".join(missing_context)))

    public_stats = context.get("public_stats") or {}
    expected_stats = {
        "posts",
        "reels",
        "followers",
        "following",
        "likes",
        "views",
        "posts_count",
        "reels_count",
        "followers_count",
        "following_count",
        "likes_count",
        "views_count",
    }
    checks.append(check("public_stats includes safe zero defaults", expected_stats.issubset(public_stats)))

    reels_source = read("api_routes/reels_routes.py")
    checks.append(check("reels upload uses shared profile context", "build_profile_template_context" in reels_source and "_render_upload" in reels_source))
    checks.append(check("reels upload redirects missing login context", "url_for(\"auth.login\"" in reels_source))

    try:
        from app import app
        app.config["TESTING"] = False
        app.config["WTF_CSRF_ENABLED"] = False
        with app.test_client() as client:
            response = client.get("/reels/upload", follow_redirects=False)
            checks.append(check("/reels/upload returns 200 or 302, not 500", response.status_code in {200, 302}, str(response.status_code)))
    except Exception as exc:
        checks.append(check("/reels/upload returns 200 or 302, not 500", False, f"{type(exc).__name__}: {exc}"))

    base_html = read("templates/base.html")
    upload_html = read("templates/reels/upload.html")
    checks.append(check("csrf-token meta exists", 'name="csrf-token"' in base_html and "csrf_token()" in base_html))
    checks.append(check("window.chainCsrfHeaders exists", "window.chainCsrfHeaders" in base_html))
    checks.append(check("unsafe fetch CSRF patch exists", "window.__chainCsrfFetchPatched" in base_html and "unsafeMethod(method)" in base_html))
    checks.append(check("form auto CSRF injection exists", 'input.name = "csrf_token"' in base_html))
    checks.append(check("reels upload form includes explicit CSRF token", 'name="csrf_token"' in upload_html and "csrf_token()" in upload_html))

    route_files = [
        "api_routes/post_routes.py",
        "api_routes/status_routes.py",
        "api_routes/stories_v2_routes.py",
        "api_routes/reels_routes.py",
        "api_routes/message_upgrade_routes.py",
        "api_routes/call_routes.py",
    ]
    exempt_hits = []
    for rel in route_files:
        path = ROOT / rel
        if path.exists():
            for index, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if "csrf.exempt" in line or "@csrf_exempt" in line:
                    exempt_hits.append(f"{rel}:{index}")
    checks.append(check("normal user POST APIs are not broadly CSRF-disabled", not exempt_hits, ", ".join(exempt_hits)))

    redis_url = get_env("REDIS_URL")
    checks.append(check("REDIS_URL is loaded", bool(redis_url)))
    redis_service = read("services/redis_service.py")
    redis_hardening = read("services/redis_hardening_service.py")
    checks.append(check("redis service prefers REDIS_URL", 'get_env("REDIS_URL")' in redis_service))
    checks.append(check("redis hardening prefers REDIS_URL", 'get_env("REDIS_URL")' in redis_hardening))
    checks.append(check("localhost Redis fallback is gated to missing env/local mode", "_DEFAULT_LOCAL_REDIS_URL" in redis_service and "_DEFAULT_LOCAL_REDIS_URL" in redis_hardening))

    if redis_url:
        from services import redis_service as redis_module
        checks.append(check("redis service does not ignore REDIS_URL", redis_module._REDIS_URL == redis_url))

    hardcoded_hits = []
    for rel in ["services/redis_service.py", "services/redis_hardening_service.py"]:
        for index, line in enumerate(read(rel).splitlines(), 1):
            if "redis://localhost:6379" in line and "_DEFAULT_LOCAL_REDIS_URL" not in line:
                hardcoded_hits.append(f"{rel}:{index}")
    checks.append(check("no hardcoded redis://localhost:6379 outside fallback constants", not hardcoded_hits, ", ".join(hardcoded_hits)))

    for rel in [
        "api_routes/reels_routes.py",
        "api_routes/call_routes.py",
        "services/redis_service.py",
        "services/redis_hardening_service.py",
        "services/profile_context_service.py",
    ]:
        try:
            py_compile.compile(str(ROOT / rel), doraise=True)
            checks.append(check(f"compile passes for {rel}", True))
        except Exception as exc:
            checks.append(check(f"compile passes for {rel}", False, str(exc)))

    failures = sum(1 for ok in checks if not ok)
    if failures:
        print(f"FAIL: phase66C audit found {failures} issue(s)")
        return 1
    print("PASS: phase66C real failure fixes audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
