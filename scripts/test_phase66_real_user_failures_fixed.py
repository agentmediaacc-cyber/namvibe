#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VENV_PYTHON = ROOT / "venv" / "bin" / "python3"
if os.environ.get("PHASE66C_ROUTE_VENV_REEXEC") != "1" and VENV_PYTHON.exists() and Path(sys.executable) != VENV_PYTHON:
    os.environ["PHASE66C_ROUTE_VENV_REEXEC"] = "1"
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])


ROUTES = [
    "/reels/upload",
    "/reels",
    "/stories",
    "/messages/",
    "/calls/recent",
    "/wallet/",
    "/dating/discover",
    "/api/home/feed?tab=for_you&page=1",
]


def fail(message):
    print(f"FAIL: {message}")
    return 1


def main():
    os.chdir(ROOT)
    os.environ.setdefault("FLASK_TESTING", "1")
    os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
    os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
    os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
    os.environ.setdefault("CHAIN_DISABLE_RATE_LIMITS", "1")

    try:
        from app import app
    except Exception as exc:
        return fail(f"app import failed: {type(exc).__name__}: {exc}")

    app.config["TESTING"] = False
    app.config["WTF_CSRF_ENABLED"] = True

    with app.test_client() as client:
        for route in ROUTES:
            response = client.get(route, follow_redirects=True)
            if response.status_code == 400:
                return fail(f"{route} returned 400 on GET")
            if response.status_code == 404:
                return fail(f"{route} returned 404")
            if response.status_code >= 500:
                return fail(f"{route} returned {response.status_code}")
            if response.status_code not in {200, 302}:
                return fail(f"{route} returned unexpected status {response.status_code}")
            print(f"PASS: {route} returned {response.status_code}")

        pages = ["/reels", "/stories", "/messages/"]
        for route in pages:
            response = client.get(route, follow_redirects=True)
            if response.status_code >= 500:
                return fail(f"{route} page returned {response.status_code} while checking CSRF helpers")
            html = response.get_data(as_text=True)
            if "csrf-token" not in html:
                return fail(f"{route} page missing csrf-token meta")
            if "chainCsrfHeaders" not in html:
                return fail(f"{route} page missing chainCsrfHeaders helper")
            if "__chainCsrfFetchPatched" not in html:
                return fail(f"{route} page missing unsafe fetch CSRF patch")
            print(f"PASS: {route} includes browser CSRF helpers")

    print("PASS: phase66C real route test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
