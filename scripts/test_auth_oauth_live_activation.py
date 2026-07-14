#!/usr/bin/env python3
"""
Test suite: OAuth Live Activation — Google & Facebook
Covers all 20 required checks for NamVibe OAuth activation.
"""
import os
import re
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ["GOOGLE_OAUTH_ENABLED"] = "true"
os.environ["FACEBOOK_OAUTH_ENABLED"] = "true"
os.environ["SUPABASE_SITE_URL"] = "https://namvibe.com"
os.environ["SUPABASE_AUTH_REDIRECT_URL"] = "https://namvibe.com/auth/callback"

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


def _env_file_has(key, expected_value):
    env_path = ROOT / ".env"
    if not env_path.exists():
        return False
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        k, v = stripped.split("=", 1)
        if k.strip() == key:
            return v.strip().lower() == expected_value.lower()
    return False


def _env_file_has_any(key):
    env_path = ROOT / ".env"
    if not env_path.exists():
        return False
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        k, v = stripped.split("=", 1)
        if k.strip() == key:
            return v.strip() != ""
    return False


def main():
    from app import create_app
    from services.auth_service import (
        _oauth_provider_enabled,
        _oauth_redirect_to,
        _supabase_site_url,
        get_supabase_auth_configuration_status,
        get_oauth_url,
        handle_oauth_callback,
    )

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    # ─────────────────────────────────────────────
    # 1. .env contains GOOGLE_OAUTH_ENABLED=true
    # ─────────────────────────────────────────────
    check("1. .env GOOGLE_OAUTH_ENABLED=true",
          _env_file_has("GOOGLE_OAUTH_ENABLED", "true"))

    # ─────────────────────────────────────────────
    # 2. .env contains FACEBOOK_OAUTH_ENABLED=true
    # ─────────────────────────────────────────────
    check("2. .env FACEBOOK_OAUTH_ENABLED=true",
          _env_file_has("FACEBOOK_OAUTH_ENABLED", "true"))

    # ─────────────────────────────────────────────
    # 3. Google route reads current environment value
    # ─────────────────────────────────────────────
    check("3. Google route reads env value",
          _oauth_provider_enabled("google") is True)

    # ─────────────────────────────────────────────
    # 4. Facebook route reads current environment value
    # ─────────────────────────────────────────────
    check("4. Facebook route reads env value",
          _oauth_provider_enabled("facebook") is True)

    # ─────────────────────────────────────────────
    # 5. Google route redirects to a Supabase OAuth URL
    # ─────────────────────────────────────────────
    with patch("api_routes.auth_routes.get_oauth_url",
               return_value="https://kcxphxihykonzuagtgke.supabase.co/auth/v1/authorize?provider=google") as oauth_mock:
        with app.test_client() as client:
            resp = client.get("/auth/google")
            loc = resp.headers.get("Location", "")
            check("5. Google route redirects to Supabase URL",
                  resp.status_code == 302 and "supabase.co" in loc,
                  f"status={resp.status_code} loc={loc[:80]}")
            check("5b. Google redirect uses provider=google",
                  "provider=google" in loc)

    # ─────────────────────────────────────────────
    # 6. Facebook route redirects to a Supabase OAuth URL
    # ─────────────────────────────────────────────
    with patch("api_routes.auth_routes.get_oauth_url",
               return_value="https://kcxphxihykonzuagtgke.supabase.co/auth/v1/authorize?provider=facebook") as oauth_mock:
        with app.test_client() as client:
            resp = client.get("/auth/facebook")
            loc = resp.headers.get("Location", "")
            check("6. Facebook route redirects to Supabase URL",
                  resp.status_code == 302 and "supabase.co" in loc,
                  f"status={resp.status_code} loc={loc[:80]}")
            check("6b. Facebook redirect uses provider=facebook",
                  "provider=facebook" in loc)

    # ─────────────────────────────────────────────
    # 7. Google redirect uses the correct callback
    # ─────────────────────────────────────────────
    callback_url = _oauth_redirect_to("google")
    check("7. Google redirect callback is correct",
          callback_url == "https://namvibe.com/auth/callback",
          f"got={callback_url}")

    # ─────────────────────────────────────────────
    # 8. Facebook redirect uses the correct callback
    # ─────────────────────────────────────────────
    callback_url_fb = _oauth_redirect_to("facebook")
    check("8. Facebook redirect callback is correct",
          callback_url_fb == "https://namvibe.com/auth/callback",
          f"got={callback_url_fb}")

    # ─────────────────────────────────────────────
    # 9. Google route does not expose secrets
    # ─────────────────────────────────────────────
    with patch("api_routes.auth_routes.get_oauth_url",
               return_value="https://supabase.test/auth/v1/authorize?provider=google"):
        with app.test_client() as client:
            resp = client.get("/auth/google")
            body = resp.data.decode("utf-8", errors="replace")
            check("9. Google route does not expose secrets",
                  "service_role" not in body.lower()
                  and "SUPABASE_SERVICE_ROLE_KEY" not in body
                  and "secret_key" not in body.lower()
                  and resp.status_code in (302, 303))

    # ─────────────────────────────────────────────
    # 10. Facebook route does not expose secrets
    # ─────────────────────────────────────────────
    with patch("api_routes.auth_routes.get_oauth_url",
               return_value="https://supabase.test/auth/v1/authorize?provider=facebook"):
        with app.test_client() as client:
            resp = client.get("/auth/facebook")
            body = resp.data.decode("utf-8", errors="replace")
            check("10. Facebook route does not expose secrets",
                  "service_role" not in body.lower()
                  and "SUPABASE_SERVICE_ROLE_KEY" not in body
                  and "secret_key" not in body.lower()
                  and resp.status_code in (302, 303))

    # ─────────────────────────────────────────────
    # 11. Disabled-provider behavior when flag is false
    # ─────────────────────────────────────────────
    with patch.dict(os.environ, {"GOOGLE_OAUTH_ENABLED": "false"}, clear=False):
        with patch("api_routes.auth_routes._provider_template_flags",
                   return_value={"google_oauth_enabled": False, "facebook_oauth_enabled": True}):
            with app.test_client() as client:
                resp = client.get("/auth/google")
                loc = resp.headers.get("Location", "")
                check("11. Disabled Google redirects to login with oauth_error",
                      resp.status_code == 302 and "/auth/login" in loc and "oauth_error" in loc,
                      f"status={resp.status_code} loc={loc}")

    # ─────────────────────────────────────────────
    # 12. Callback does not misclassify OAuth as password recovery
    # ─────────────────────────────────────────────
    with app.test_client() as client:
        resp = client.get("/auth/callback?code=abc123")
        loc = resp.headers.get("Location", "")
        check("12. Callback handles OAuth code (not recovery)",
              resp.status_code == 302 and "reset-password" not in loc,
              f"loc={loc}")

    # ─────────────────────────────────────────────
    # 13. Callback does not trust query user_id
    # ─────────────────────────────────────────────
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["auth_provider"] = "google"
            sess["oauth_state"] = "expected_state"
        resp = client.get("/auth/callback?code=abc&state=expected_state&user_id=spoofed_id&email=spoofed@evil.com")
        loc = resp.headers.get("Location", "")
        check("13. Callback ignores query user_id",
              resp.status_code == 302 and "spoofed" not in loc,
              f"loc={loc}")

    # ─────────────────────────────────────────────
    # 14. Callback blocks open redirects
    # ─────────────────────────────────────────────
    with patch("api_routes.auth_routes.handle_oauth_callback", return_value=(True, "/profile/")):
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["auth_provider"] = "google"
                sess["oauth_state"] = "state1"
                sess["auth_next"] = "https://evil.example.com/steal"
            resp = client.get("/auth/callback?code=abc&state=state1")
            loc = resp.headers.get("Location", "")
            check("14. Callback blocks open redirect",
                  resp.status_code == 302 and loc == "/profile/",
                  f"loc={loc}")

    # ─────────────────────────────────────────────
    # 15. Login template contains both provider buttons
    # ─────────────────────────────────────────────
    with app.test_client() as client:
        resp = client.get("/auth/login")
        html = resp.data.decode("utf-8", errors="replace")
        has_google = "Continue with Google" in html and "/auth/google" in html
        has_facebook = "Continue with Facebook" in html and "/auth/facebook" in html
        check("15. Login template has both provider buttons",
              has_google and has_facebook)

    # ─────────────────────────────────────────────
    # 16. Existing email login still works
    # ─────────────────────────────────────────────
    with app.test_client() as client:
        resp = client.get("/auth/login")
        html = resp.data.decode("utf-8", errors="replace")
        check("16. Email login form present",
              'name="login_id"' in html and 'name="password"' in html and "Log In" in html)

    # ─────────────────────────────────────────────
    # 17. Registration still works
    # ─────────────────────────────────────────────
    with app.test_client() as client:
        resp = client.get("/auth/register")
        html = resp.data.decode("utf-8", errors="replace")
        check("17. Registration page works",
              resp.status_code == 200 and "Create Account" in html)

    # ─────────────────────────────────────────────
    # 18. No service-role key appears in rendered HTML
    # ─────────────────────────────────────────────
    _svc_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    with app.test_client() as client:
        for path in ("/auth/login", "/auth/register"):
            resp = client.get(path)
            html = resp.data.decode("utf-8", errors="replace")
            check(f"18. No service-role key in {path}",
                  "SUPABASE_SERVICE_ROLE_KEY" not in html
                  and (_svc_role_key not in html if _svc_role_key else True)
                  and "service_role_key" not in html.lower())

    # ─────────────────────────────────────────────
    # 19. Recommendations remain disabled
    # ─────────────────────────────────────────────
    rec_enabled = os.getenv("NAMVIBE_AI_RECOMMENDATIONS_ENABLED", "false").strip().lower()
    check("19. Recommendations remain disabled",
          rec_enabled in ("false", "0", ""))

    # ─────────────────────────────────────────────
    # 20. External AI remains disabled
    # ─────────────────────────────────────────────
    ext_ai = os.getenv("NAMVIBE_AI_EXTERNAL_CALLS_ENABLED", "false").strip().lower()
    check("20. External AI remains disabled",
          ext_ai in ("false", "0", ""))

    # ─────────────────────────────────────────────
    # BONUS: Safe config diagnostic
    # ─────────────────────────────────────────────
    status = get_supabase_auth_configuration_status()
    check("Bonus: Status reports Supabase URL configured",
          bool(status.get("supabase_url_configured")))
    check("Bonus: Status reports Supabase anon key configured",
          bool(status.get("supabase_anon_key_configured")))
    check("Bonus: Status reports Google enabled",
          bool(status.get("google_provider_expected")))
    check("Bonus: Status reports Facebook enabled",
          bool(status.get("facebook_provider_expected")))
    check("Bonus: Status does not contain keys",
          "eyJ" not in str(status)
          and _svc_role_key not in str(status)
          and "service_role_key" not in str(status).lower())

    print(f"\nRESULT {PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
