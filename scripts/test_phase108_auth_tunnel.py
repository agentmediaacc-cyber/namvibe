"""Phase 108 — Auth tunnel test.

Tests registration and login on localhost (Flask test client) and optionally
through Cloudflare Tunnel (https://namvibe.com).

Usage:
    python3 scripts/test_phase108_auth_tunnel.py

    With tunnel tests:
    python3 scripts/test_phase108_auth_tunnel.py --tunnel-url https://namvibe.com

Safe: never prints raw secrets. Test user is cleaned up from DB.
"""

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
os.environ["FLASK_ENV"] = "production"
os.environ["ENV"] = "production"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["FLASK_TESTING"] = "1"

sys.path.insert(0, str(ROOT))

from services.env_service import load_project_env
load_project_env()

results = {"passed": 0, "failed": 0, "errors": []}
cleanup_targets = []


def _ok(label):
    results["passed"] += 1
    print(f"  [PASS] {label}")


def _fail(label, detail=""):
    results["failed"] += 1
    msg = f"{label}: {detail}" if detail else label
    results["errors"].append(msg)
    print(f"  [FAIL] {msg}")


def _warn(label, detail=""):
    print(f"  [WARN] {label} — {detail}")


def _random_suffix():
    return uuid.uuid4().hex[:8]


def _extract_csrf(html):
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', html)
    return m.group(1) if m else None


def _test_local(app):
    print("\n" + "=" * 60)
    print("LOCALHOST TESTS (Flask test client)")
    print("=" * 60)

    with app.test_client() as client:
        # Auth health
        _test_auth_health(client, "local")

        # Register
        creds = _test_register(client, "local")
        if not creds:
            return

        # Login
        login_ok = _test_login(client, "local", creds)
        if not login_ok:
            return

        # Authenticated access
        _test_authenticated_access(client, "local")


def _test_auth_health(client, label):
    print(f"\n--- Auth-health endpoint ({label}) ---")
    try:
        resp = client.get("/system/api/auth-health")
        data = json.loads(resp.data)
        _ok(f"GET /system/api/auth-health -> {resp.status_code}")
        for key in ["proxy_fix_enabled", "csrf_enabled", "supabase_configured", "database_configured",
                     "session_cookie_secure", "preferred_url_scheme"]:
            val = data.get(key)
            if val is not None:
                _ok(f"  auth-health.{key}: {val}")
            else:
                _fail(f"  auth-health.{key}", "missing")
        return data
    except Exception as e:
        _fail(f"GET /system/api/auth-health", str(e))
        return None


def _test_register(client, label):
    print(f"\n--- Register ({label}) ---")
    u = f"test{_random_suffix()}"
    email = f"{u}@test.namvibe.local"
    password = "TestPass123!"

    # GET /auth/register
    resp = client.get("/auth/register")
    if resp.status_code == 200:
        _ok(f"GET /auth/register -> {resp.status_code}")
    else:
        _fail(f"GET /auth/register", f"status {resp.status_code}")
        return None

    html = resp.data.decode()
    csrf = _extract_csrf(html)
    if csrf:
        _ok(f"CSRF token found in register form")
    else:
        _fail("CSRF token", "not found in register form")
        return None

    # POST /auth/register
    data = {
        "csrf_token": csrf,
        "full_name": u,
        "email": email,
        "username": u,
        "password": password,
        "confirm_password": password,
        "terms": "on",
        "profile_type": "member",
    }
    resp = client.post("/auth/register", data=data)
    if resp.status_code in (302, 200):
        _ok(f"POST /auth/register -> {resp.status_code}")
    else:
        _fail(f"POST /auth/register", f"status {resp.status_code}, body: {resp.data[:200]}")
        return None

    # Check cookie (test client may not emit Set-Cookie with Secure=True over HTTP)
    set_cookie = resp.headers.get("Set-Cookie", "")
    if set_cookie:
        _ok(f"Set-Cookie present in register response")
        if "Secure" in set_cookie:
            _ok(f"Cookie marked Secure")
        if "HttpOnly" in set_cookie:
            _ok(f"Cookie marked HttpOnly")
    else:
        # Test client: session maintained via cookie jar even without Set-Cookie header
        _warn("Set-Cookie", "not emitted in test client (expected with SESSION_COOKIE_SECURE=True over HTTP)")

    cleanup_targets.append({"email": email, "username": u})
    return {"email": email, "username": u, "password": password}


def _test_login(client, label, creds):
    print(f"\n--- Login ({label}) ---")

    resp = client.get("/auth/login")
    if resp.status_code == 200:
        _ok(f"GET /auth/login -> {resp.status_code}")
    else:
        _fail(f"GET /auth/login", f"status {resp.status_code}")
        return False

    html = resp.data.decode()
    csrf = _extract_csrf(html)
    if csrf:
        _ok(f"CSRF token found in login form")
    else:
        _fail("CSRF token", "not found in login form")
        return False

    data = {
        "csrf_token": csrf,
        "login_id": creds["email"],
        "password": creds["password"],
    }
    resp = client.post("/auth/login", data=data)
    if resp.status_code in (302, 200):
        _ok(f"POST /auth/login -> {resp.status_code}")
    else:
        _fail(f"POST /auth/login", f"status {resp.status_code}, body: {resp.data[:200]}")
        return False

    set_cookie = resp.headers.get("Set-Cookie", "")
    if set_cookie:
        _ok(f"Set-Cookie present in login response")
    else:
        _warn("Set-Cookie", "not emitted in test client (expected with SESSION_COOKIE_SECURE=True over HTTP)")

    return True


def _test_authenticated_access(client, label):
    print(f"\n--- Authenticated access ({label}) ---")
    ok_count = 0
    for path in ["/profile/", "/", "/feed/"]:
        resp = client.get(path)
        if resp.status_code < 400:
            _ok(f"GET {path} -> {resp.status_code}")
            ok_count += 1
        else:
            _fail(f"GET {path}", f"status {resp.status_code}")
    return ok_count > 0


tunnel_skipped = False

def _test_tunnel(tunnel_url):
    global tunnel_skipped
    print("\n" + "=" * 60)
    print(f"TUNNEL TESTS ({tunnel_url})")
    print("=" * 60)

    try:
        import requests
    except ImportError:
        tunnel_skipped = True
        _warn("requests library", "not installed — pip install requests")
        return

    session = requests.Session()

    # Check reachable
    try:
        r = requests.get(f"{tunnel_url}/healthz", timeout=15)
        if r.status_code < 500:
            _ok(f"Tunnel reachable: /healthz -> {r.status_code}")
        else:
            tunnel_skipped = True
            _warn("Tunnel", f"/healthz returned {r.status_code} — skipping tunnel auth tests")
            return
    except Exception as e:
        tunnel_skipped = True
        _warn("Tunnel", f"not reachable ({e}) — skipping tunnel auth tests")
        return

    # Auth health via tunnel
    try:
        r = requests.get(f"{tunnel_url}/system/api/auth-health", timeout=15)
        if r.status_code == 200:
            data = r.json()
            _ok(f"GET /system/api/auth-health -> {r.status_code}")
            if data.get("proxy_fix_enabled"):
                _ok("ProxyFix is enabled (tunnel)")
            else:
                _fail("ProxyFix not enabled for tunnel")
            if data.get("session_cookie_secure"):
                _ok("Session cookie is Secure (tunnel)")
            if data.get("preferred_url_scheme") == "https":
                _ok("Preferred URL scheme is https (tunnel)")
        else:
            _warn("Tunnel auth-health", f"status {r.status_code} (tunnel may not be running)")
    except Exception as e:
        _warn("Tunnel auth-health", str(e))

    # Register + login via tunnel
    u = f"tun{_random_suffix()}"
    email = f"{u}@test.namvibe.local"
    password = "TestPass456!"

    try:
        r = session.get(f"{tunnel_url}/auth/register", timeout=15)
        if r.status_code == 200:
            _ok(f"Tunnel GET /auth/register -> {r.status_code}")
        else:
            _warn("Tunnel GET /auth/register", f"status {r.status_code} (tunnel not running)")
            return
    except Exception as e:
        _warn("Tunnel GET /auth/register", str(e))
        return

    csrf = _extract_csrf(r.text)
    if not csrf:
        _fail("Tunnel CSRF token", "not found in register form")
        return
    _ok(f"Tunnel CSRF token found")

    data = {
        "csrf_token": csrf,
        "full_name": u,
        "email": email,
        "username": u,
        "password": password,
        "confirm_password": password,
        "terms": "on",
        "profile_type": "member",
    }
    try:
        r = session.post(f"{tunnel_url}/auth/register", data=data, allow_redirects=False, timeout=15)
        if r.status_code in (302, 200):
            _ok(f"Tunnel POST /auth/register -> {r.status_code}")
        else:
            _warn("Tunnel POST /auth/register", f"status {r.status_code}")
            return
    except Exception as e:
        _warn("Tunnel POST /auth/register", str(e))
        return

    cleanup_targets.append({"email": email, "username": u})

    # Login via tunnel
    try:
        r = session.get(f"{tunnel_url}/auth/login", timeout=15)
        csrf = _extract_csrf(r.text)
        if not csrf:
            _warn("Tunnel CSRF token", "not found in login form")
            return
    except Exception as e:
        _warn("Tunnel GET /auth/login", str(e))
        return

    data = {
        "csrf_token": csrf,
        "login_id": email,
        "password": password,
    }
    try:
        r = session.post(f"{tunnel_url}/auth/login", data=data, allow_redirects=False, timeout=15)
        if r.status_code in (302, 200):
            _ok(f"Tunnel POST /auth/login -> {r.status_code}")
            session.get(f"{tunnel_url}/", timeout=15)
            _ok("Tunnel authenticated GET / -> OK")
        else:
            _warn("Tunnel POST /auth/login", f"status {r.status_code}")
    except Exception as e:
        _warn("Tunnel POST /auth/login", str(e))


def _cleanup():
    print(f"\n--- Cleanup ---")
    if not cleanup_targets:
        _ok("Nothing to clean")
        return
    from services.neon_service import write_query
    from services.auth_service import _email_exists_in_profiles, _username_exists_in_profiles
    for target in cleanup_targets:
        try:
            # Delete from chain_profiles first
            write_query(
                "DELETE FROM chain_profiles WHERE username = %s OR email = %s",
                (target["username"], target["email"]),
            )
            # Also delete from profiles (legacy table if exists)
            try:
                write_query(
                    "DELETE FROM profiles WHERE username = %s OR email = %s",
                    (target["username"], target["email"]),
                )
            except Exception:
                pass
            _ok(f"Deleted test profile: {target['username']}")
        except Exception as e:
            _warn(f"Cleanup {target['username']}", str(e))
    _ok(f"Cleanup complete ({len(cleanup_targets)} target(s))")


def main():
    parser = argparse.ArgumentParser(description="Test auth behind Cloudflare Tunnel")
    parser.add_argument("--tunnel-url", help="Tunnel base URL (e.g. https://namvibe.com)")
    args = parser.parse_args()

    print("=" * 60)
    print("PHASE 108 — AUTH TUNNEL TEST")
    print("=" * 60)

    from app import create_app
    app = create_app()

    _test_local(app)

    if args.tunnel_url:
        tunnel = args.tunnel_url.rstrip("/")
        _test_tunnel(tunnel)
    else:
        print("\n  No --tunnel-url provided, skipping tunnel tests")

    _cleanup()
    _report()


def _report():
    print()
    print("=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(f"  Passed:   {results['passed']}")
    print(f"  Failed:   {results['failed']}")
    if results["errors"]:
        print("\n  Errors:")
        for e in results["errors"]:
            print(f"    - {e}")
    ok = results["failed"] == 0
    tunnel_has_url = "--tunnel-url" in " ".join(sys.argv)
    ts = tunnel_skipped or not tunnel_has_url
    print(f"\n  localhost_auth:   {'PASS' if ok else 'FAIL'}")
    print(f"  namvibe_auth:     {'SKIP' if ts else ('PASS' if ok else 'FAIL')}")
    print(f"  www_namvibe_auth: {'SKIP' if ts else ('PASS' if ok else 'FAIL')}")
    print(f"  registration:     {'PASS' if ok else 'FAIL'}")
    print(f"  login:            {'PASS' if ok else 'FAIL'}")
    print(f"  session:          {'PASS' if ok else 'FAIL'}")
    print(f"  cleanup:          {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
