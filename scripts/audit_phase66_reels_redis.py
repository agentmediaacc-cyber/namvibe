#!/usr/bin/env python3
import os
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VENV_PYTHON = ROOT / "venv" / "bin" / "python3"
if os.environ.get("PHASE66A_VENV_REEXEC") != "1" and VENV_PYTHON.exists() and Path(sys.executable) != VENV_PYTHON:
    os.environ["PHASE66A_VENV_REEXEC"] = "1"
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])


def check(label, ok, details=""):
    status = "PASS" if ok else "FAIL"
    suffix = f" - {details}" if details else ""
    print(f"{status}: {label}{suffix}")
    return ok


def read(rel_path):
    return (ROOT / rel_path).read_text(encoding="utf-8", errors="ignore")


def main():
    os.chdir(ROOT)
    os.environ.setdefault("FLASK_TESTING", "1")
    os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
    os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
    os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
    os.environ.setdefault("CHAIN_DISABLE_RATE_LIMITS", "1")

    checks = []

    from services.env_service import get_env, load_project_env
    from services.profile_context_service import build_profile_template_context

    load_project_env()

    sample_profile = {
        "id": "11111111-1111-4111-8111-111111111111",
        "username": "phase66a",
        "display_name": "Phase 66A",
        "posts_count": 3,
        "reels_count": 2,
        "followers_count": 5,
        "following_count": 7,
        "total_likes": 11,
        "profile_views": 13,
    }
    context = build_profile_template_context(sample_profile)
    checks.append(check("profile context exists", isinstance(context, dict)))
    checks.append(check("public_stats exists", isinstance(context.get("public_stats"), dict)))

    required = {
        "profile",
        "current_profile",
        "hero_profile",
        "viewer_profile",
        "public_stats",
        "profile_nav",
        "active_tab",
    }
    missing = sorted(required - set(context))
    checks.append(check("profile context has required keys", not missing, ", ".join(missing)))

    stats = context.get("public_stats") or {}
    stats_required = {
        "posts_count",
        "reels_count",
        "followers_count",
        "following_count",
        "likes_count",
        "views_count",
    }
    missing_stats = sorted(stats_required - set(stats))
    checks.append(check("public_stats has required count keys", not missing_stats, ", ".join(missing_stats)))
    checks.append(check("public_stats uses real values when available", stats.get("posts_count") == 3 and stats.get("views_count") == 13))

    reels_source = read("api_routes/reels_routes.py")
    checks.append(check("/reels/upload uses profile context helper", "build_profile_template_context" in reels_source and "_render_upload" in reels_source))

    try:
        from app import app

        app.config["TESTING"] = False
        with app.test_client() as client:
            response = client.get("/reels/upload", follow_redirects=False)
            checks.append(check("/reels/upload returns 200 or 302", response.status_code in {200, 302}, str(response.status_code)))
            checks.append(check("no 500 on reels upload page", response.status_code < 500, str(response.status_code)))
    except Exception as exc:
        checks.append(check("/reels/upload returns 200 or 302", False, f"{type(exc).__name__}: {exc}"))
        checks.append(check("no 500 on reels upload page", False))

    redis_url = get_env("REDIS_URL")
    checks.append(check("REDIS_URL loaded", bool(redis_url)))

    redis_source = read("services/redis_service.py")
    checks.append(check("Redis service prefers REDIS_URL", 'get_env("REDIS_URL")' in redis_source and "redis.from_url(self.url" in redis_source))
    incorrect_fallbacks = []
    for line_no, line in enumerate(redis_source.splitlines(), 1):
        has_local = "localhost:6379" in line or "redis://localhost:6379" in line
        allowed = "_DEFAULT_LOCAL_REDIS_URL" in line
        if has_local and not allowed:
            incorrect_fallbacks.append(f"services/redis_service.py:{line_no}")
    checks.append(check("no incorrect Redis localhost fallback", not incorrect_fallbacks, ", ".join(incorrect_fallbacks)))

    if redis_url:
        from services import redis_service

        checks.append(check("Redis service does not ignore REDIS_URL", redis_service._REDIS_URL == redis_url))

    for rel in [
        "api_routes/reels_routes.py",
        "services/profile_context_service.py",
        "services/redis_service.py",
        "scripts/audit_phase66_reels_redis.py",
    ]:
        try:
            py_compile.compile(str(ROOT / rel), doraise=True)
            checks.append(check(f"compile passes for {rel}", True))
        except Exception as exc:
            checks.append(check(f"compile passes for {rel}", False, str(exc)))

    failures = sum(1 for ok in checks if not ok)
    if failures:
        print(f"FAIL: phase66A reels/redis audit found {failures} issue(s)")
        return 1
    print("PASS: phase66A reels/redis audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
