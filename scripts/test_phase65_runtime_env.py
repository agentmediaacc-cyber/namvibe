#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VENV_PYTHON = ROOT / "venv" / "bin" / "python3"
if os.environ.get("PHASE65_VENV_REEXEC") != "1" and VENV_PYTHON.exists() and Path(sys.executable) != VENV_PYTHON:
    os.environ["PHASE65_VENV_REEXEC"] = "1"
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

from services.env_service import ENV_PATH, get_env, load_project_env

REQUIRED_ENV = [
    "DATABASE_URL",
    "REDIS_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
]


def fail(message):
    print(f"FAIL: {message}")
    return 1


def main():
    load_project_env()
    if not ENV_PATH.exists():
        return fail(f".env missing at {ENV_PATH}")

    missing = [name for name in REQUIRED_ENV if not get_env(name)]
    if missing:
        return fail(f"missing env names: {', '.join(missing)}")

    os.environ.setdefault("FLASK_TESTING", "1")
    os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
    os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
    os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
    os.environ.setdefault("CHAIN_DISABLE_RATE_LIMITS", "1")

    try:
        from app import app
    except Exception as exc:
        return fail(f"app import failed: {type(exc).__name__}: {exc}")

    app.config["TESTING"] = True

    with app.test_client() as client:
        health = client.get("/healthz")
        if health.status_code >= 500:
            return fail(f"/healthz returned {health.status_code}")
        if health.status_code not in {200, 302}:
            return fail(f"/healthz returned unexpected status {health.status_code}")
        print(f"PASS: /healthz returned {health.status_code}")

        feed = client.get("/api/home/feed?tab=for_you&page=1")
        if feed.status_code >= 500:
            return fail(f"/api/home/feed returned {feed.status_code}")
        if feed.status_code not in {200, 302}:
            return fail(f"/api/home/feed returned unexpected status {feed.status_code}")
        print(f"PASS: /api/home/feed returned {feed.status_code}")

    print("PASS: runtime env test complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
