#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ["GOOGLE_OAUTH_ENABLED"] = "true"

PASS = 0
FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} {detail}")


def main():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["auth_provider"] = "google"
            sess["oauth_state"] = "expected"
        resp = client.get("/auth/callback?code=abc&state=wrong&user_id=spoofed")
        check("OAuth callback rejects invalid state", resp.status_code == 302 and "/auth/login" in (resp.headers.get("Location") or ""))

    with app.test_client() as client:
        resp = client.get("/auth/callback?error=access_denied&error_description=cancelled")
        check("OAuth error handled without 500", resp.status_code == 302 and "/auth/login" in (resp.headers.get("Location") or ""))

    with patch("api_routes.auth_routes.handle_oauth_callback", return_value=(True, "/profile/")):
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["auth_provider"] = "google"
                sess["oauth_state"] = "state1"
                sess["auth_next"] = "https://evil.example"
            resp = client.get("/auth/callback?code=abc&state=state1")
            check("Open redirect is blocked", resp.status_code == 302 and resp.headers.get("Location") == "/profile/")

    login_html = app.test_client().get("/auth/login").data.decode("utf-8", errors="replace")
    register_html = app.test_client().get("/auth/register").data.decode("utf-8", errors="replace")
    check("Service role key absent from HTML", "SUPABASE_SERVICE_ROLE_KEY" not in login_html and "SUPABASE_SERVICE_ROLE_KEY" not in register_html)

    print(f"\nRESULT {PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
