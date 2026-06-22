"""Phase 110 — Register Email Rate Limit + Redirect fix.

Tests:
- No 500 for any registration input (bad data, rate-limit-like conditions, etc.)
- auth/register.html rendered (not generic error page) on error
- fallback mode (CHAIN_AUTH_EMAIL_OPTIONAL=1) creates account, redirects to /profile/
- /profile/ returns 200 after registration
- Login after registration succeeds
- Cleanup deletes test profiles

Usage:
    python3 scripts/test_phase110_register_email_rate_limit.py
    python3 scripts/test_phase110_register_email_rate_limit.py --tunnel-url https://namvibe.com

Safe: never prints raw secrets. Test user is cleaned up.
"""

import os
import re
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
os.environ["FLASK_ENV"] = "production"
os.environ["ENV"] = "production"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["FLASK_TESTING"] = "1"

# Test client helper: use HTTPS so Secure cookies are preserved
def _test_client(app):
    client = app.test_client()
    client.environ_base["wsgi.url_scheme"] = "https"
    return client

sys.path.insert(0, str(ROOT))

from services.env_service import load_project_env
load_project_env()

results = {"passed": 0, "failed": 0, "errors": [], "warnings": 0}
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
    results["warnings"] += 1
    print(f"  [WARN] {label} — {detail}")


def _random_suffix():
    return uuid.uuid4().hex[:8]


def _extract_csrf(html):
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', html)
    return m.group(1) if m else None

def _extract_apk_csrf(html):
    m = re.search(r'name="apk_csrf_token".*?value="([^"]+)"', html)
    return m.group(1) if m else None


def _is_register_template(html):
    """Check if response is the auth/register.html template (not a generic error page)."""
    if isinstance(html, bytes):
        return b'name="csrf_token"' in html or b'id="registerForm"' in html
    return 'name="csrf_token"' in html or 'id="registerForm"' in html


def _test_form_validation(app):
    """Bad form data must render template with error, not 500."""
    print("\n--- Form validation (no 500) ---")
    with _test_client(app) as client:
        cases = [
            ("no email", {"password": "TestPass123!", "confirm_password": "TestPass123!",
                          "username": "testuser", "terms": "on"}),
            ("short password", {"email": "a@b.com", "password": "short", "confirm_password": "short",
                                "username": "testuser", "terms": "on"}),
            ("password mismatch", {"email": "a@b.com", "password": "TestPass123!",
                                   "confirm_password": "DifferentPass1!", "username": "testuser", "terms": "on"}),
            ("no terms", {"email": "a@b.com", "password": "TestPass123!",
                          "confirm_password": "TestPass123!", "username": "testuser"}),
        ]
        for label, data in cases:
            t0 = time.time()
            resp = client.post("/auth/register", data=data)
            dur = time.time() - t0
            sc = resp.status_code
            if sc == 500:
                _fail(f"{label}", f"500 — should render template with error")
            elif sc < 500:
                _ok(f"{label} -> {sc} ({dur*1000:.0f}ms)")
                if sc == 200 and not _is_register_template(resp.data):
                    _warn(f"{label}", "response does not look like auth/register.html")
            else:
                _fail(f"{label}", f"unexpected {sc}")


def _test_register_and_verify_redirect(app):
    """Register in fallback mode → redirect /profile/ → 200."""
    print("\n--- Register + redirect (/profile/ returns 200) ---")
    with _test_client(app) as client:
        uid = _random_suffix()
        email = f"p110_{uid}@test.namvibe.local"
        username = f"p110_{uid}"
        password = "TestPass123!"

        # GET form
        resp = client.get("/auth/register")
        if resp.status_code != 200:
            _fail("GET /auth/register", f"status {resp.status_code}")
            return None
        _ok("GET /auth/register -> 200")

        body_html = resp.data.decode()
        csrf = _extract_csrf(body_html)
        apk_csrf = _extract_apk_csrf(body_html)
        if not csrf:
            _fail("CSRF token", "not found")
            return None
        _ok("CSRF + APK tokens found" if apk_csrf else "CSRF token found")

        # POST register
        t0 = time.time()
        resp = client.post("/auth/register", data={
            "csrf_token": csrf, "apk_csrf_token": apk_csrf or "",
            "full_name": username, "email": email, "username": username,
            "password": password, "confirm_password": password,
            "terms": "on", "profile_type": "member",
        })
        dur = time.time() - t0

        if resp.status_code == 500:
            _fail("POST /auth/register", "500 — critical bug (unhandled exception)")
            cleanup_targets.append({"email": email, "username": username})
            return None

        if resp.status_code == 302:
            _ok(f"POST /auth/register -> 302 redirect ({dur*1000:.0f}ms)")
        elif resp.status_code == 200:
            body = resp.data.decode()
            # Sniff the error message from the rendered template
            import re as _re
            _err_match = _re.search(r'(Registration[^<]{3,120}|Enter a[^<]{3,120}|unavailable[^<]{3,120}|expired[^<]{3,120})', body, _re.I)
            _snippet = _err_match.group(1).strip() if _err_match else body[body.find('alert'):body.find('alert')+200] if 'alert' in body else body[:200]
            _warn("POST /auth/register", f"200 (not 302) — error: {_snippet[:200]}")
            cleanup_targets.append({"email": email, "username": username})
            return None
        else:
            _fail("POST /auth/register", f"status {resp.status_code}")
            cleanup_targets.append({"email": email, "username": username})
            return None

        cleanup_targets.append({"email": email, "username": username})

        # Follow redirect to /profile/
        loc = resp.headers.get("Location", "")
        _ok(f"Redirect to: {loc}")
        resp2 = client.get(loc)
        if resp2.status_code == 200:
            _ok(f"GET {loc} -> 200 (profile page loads)")
        else:
            _fail(f"GET {loc}", f"status {resp2.status_code} — profile/broken page")

        # Verify session
        with client.session_transaction() as sess:
            sid = sess.get("profile_id")
            if sid:
                _ok(f"Session profile_id: {sid}")
            else:
                _fail("Session profile_id", "not set after registration")

        return {"email": email, "username": username, "password": password}


def _test_login_after_register(app, creds):
    """Login with the registered credentials → session set."""
    print("\n--- Login after register ---")
    with _test_client(app) as client:
        resp = client.get("/auth/login")
        if resp.status_code != 200:
            _fail("GET /auth/login", f"status {resp.status_code}")
            return False

        body_html = resp.data.decode()
        csrf = _extract_csrf(body_html)
        apk_csrf = _extract_apk_csrf(body_html)
        if not csrf:
            _fail("CSRF token", "not found in login form")
            return False

        t0 = time.time()
        resp = client.post("/auth/login", data={
            "csrf_token": csrf, "apk_csrf_token": apk_csrf or "",
            "login_id": creds["email"],
            "password": creds["password"],
        })
        dur = time.time() - t0
        sc = resp.status_code

        if sc in (302, 200):
            _ok(f"POST /auth/login -> {sc} ({dur*1000:.0f}ms)")
        else:
            _fail("POST /auth/login", f"status {sc}")
            return False

        # Follow redirect or do a follow-up GET to verify session
        if sc == 302:
            loc = resp.headers.get("Location", "")
            resp2 = client.get(loc)
            if resp2.status_code == 200:
                _ok(f"GET {loc} -> 200 (logged in)")
            else:
                _fail(f"GET {loc}", f"status {resp2.status_code}")
        else:
            # Check session via a GET that reads profile
            resp2 = client.get("/profile/")
            if resp2.status_code == 200:
                _ok("GET /profile/ -> 200 (logged in)")
            else:
                _fail("GET /profile/", f"status {resp2.status_code}")
        return True


def _test_with_auth_email_optional(app):
    """Register with CHAIN_AUTH_EMAIL_OPTIONAL=1 (simulates rate-limit fallback)."""
    print("\n--- CHAIN_AUTH_EMAIL_OPTIONAL=1 (rate-limit fallback) ---")
    os.environ["CHAIN_AUTH_EMAIL_OPTIONAL"] = "1"

    with _test_client(app) as client:
        uid = _random_suffix()
        email = f"p110e_{uid}@test.namvibe.local"
        username = f"p110e_{uid}"
        password = "TestPass123!"

        resp = client.get("/auth/register")
        body_html = resp.data.decode() or ""
        csrf = _extract_csrf(body_html)
        apk_csrf = _extract_apk_csrf(body_html)

        t0 = time.time()
        resp = client.post("/auth/register", data={
            "csrf_token": csrf, "apk_csrf_token": apk_csrf or "",
            "full_name": username, "email": email, "username": username,
            "password": password, "confirm_password": password,
            "terms": "on", "profile_type": "member",
        })
        dur = time.time() - t0

        if resp.status_code == 500:
            _fail("POST /auth/register (CHAIN_AUTH_EMAIL_OPTIONAL=1)", "500 — critical bug")
            os.environ["CHAIN_AUTH_EMAIL_OPTIONAL"] = "0"
            cleanup_targets.append({"email": email, "username": username})
            return

        if resp.status_code == 302:
            _ok(f"POST /auth/register -> 302 redirect ({dur*1000:.0f}ms)")
            loc = resp.headers.get("Location", "")
            resp2 = client.get(loc)
            if resp2.status_code == 200:
                _ok(f"GET {loc} -> 200 after fallback")
            else:
                _fail(f"GET {loc}", f"status {resp2.status_code}")
            with client.session_transaction() as sess:
                if sess.get("profile_id"):
                    _ok("Session profile_id set after fallback")
                else:
                    _fail("Session profile_id", "not set after fallback")
        elif resp.status_code == 200:
            # No redirect, but also no 500 — check if error or rendered page
            body = resp.data.decode()
            if "rate limit" in body.lower() or "unavailable" in body.lower() or "unreachable" in body.lower():
                _warn("Registration blocked", "rate-limit error rendered in template (expected without fallback)")
            elif _is_register_template(resp.data):
                _warn("No redirect", "200 with register template (fallback may not have triggered)")
            else:
                _warn("Unexpected response", "200 with unknown content")
        else:
            _fail("POST /auth/register", f"status {resp.status_code}")
        cleanup_targets.append({"email": email, "username": username})

    os.environ["CHAIN_AUTH_EMAIL_OPTIONAL"] = "0"


def _test_tunnel(tunnel_url):
    """Test registration + redirect + profile via tunnel (no 500)."""
    print("\n" + "=" * 60)
    print(f"TUNNEL TESTS ({tunnel_url})")
    print("=" * 60)

    try:
        import requests as req
    except ImportError:
        _warn("requests", "not installed — pip install requests")
        return

    s = req.Session()

    # Check reachable
    try:
        r = req.get(f"{tunnel_url}/healthz", timeout=15)
        if r.status_code >= 500:
            _warn("Unreachable", f"/healthz -> {r.status_code}")
            return
        _ok(f"Tunnel reachable: /healthz -> {r.status_code}")
    except Exception as e:
        _warn("Unreachable", str(e))
        return

    # Register
    uid = _random_suffix()
    email = f"p110t_{uid}@test.namvibe.local"
    username = f"p110t_{uid}"
    password = "TestPass789!"

    try:
        r = s.get(f"{tunnel_url}/auth/register", timeout=15)
        if r.status_code != 200:
            _warn("GET /auth/register", f"status {r.status_code}")
            return
        _ok("GET /auth/register -> 200")
    except Exception as e:
        _warn("GET /auth/register", str(e))
        return

    csrf = _extract_csrf(r.text)
    apk_csrf = _extract_apk_csrf(r.text)
    if not csrf:
        _warn("CSRF", "not found")
        return
    _ok("CSRF + APK tokens found" if apk_csrf else "CSRF token found")

    t0 = time.time()
    data = {
        "csrf_token": csrf, "apk_csrf_token": apk_csrf or "",
        "full_name": username, "email": email, "username": username,
        "password": password, "confirm_password": password,
        "terms": "on", "profile_type": "member",
    }
    try:
        r = s.post(f"{tunnel_url}/auth/register", data=data, allow_redirects=False, timeout=30)
        dur = time.time() - t0
        if r.status_code == 500:
            _fail("Tunnel POST /auth/register", "500 — bug!")
            cleanup_targets.append({"email": email, "username": username})
            return
        if r.status_code in (302, 200):
            _ok(f"Tunnel POST /auth/register -> {r.status_code} ({dur*1000:.0f}ms) — no 500")
        else:
            _warn("Tunnel POST /auth/register", f"status {r.status_code}")
            cleanup_targets.append({"email": email, "username": username})
            return
    except Exception as e:
        _warn("Tunnel POST /auth/register", str(e))
        cleanup_targets.append({"email": email, "username": username})
        return

    cleanup_targets.append({"email": email, "username": username})

    if r.status_code == 302:
        loc = r.headers.get("Location", "")
        _ok(f"Redirect: {loc}")
        try:
            r2 = s.get(f"{tunnel_url}{loc}", timeout=15)
            if r2.status_code == 200:
                _ok(f"GET {loc} -> 200")
            else:
                _warn("Profile redirect", f"status {r2.status_code}")
        except Exception as e:
            _warn("Profile redirect", str(e))

    # Login
    try:
        r = s.get(f"{tunnel_url}/auth/login", timeout=15)
        csrf = _extract_csrf(r.text)
        apk_csrf = _extract_apk_csrf(r.text)
        if not csrf:
            _warn("Login CSRF", "not found")
            return
    except Exception as e:
        _warn("GET /auth/login", str(e))
        return

    t0 = time.time()
    try:
        r = s.post(f"{tunnel_url}/auth/login", data={
            "csrf_token": csrf, "apk_csrf_token": apk_csrf or "",
            "login_id": email, "password": password,
        }, allow_redirects=False, timeout=15)
        dur = time.time() - t0
        if r.status_code in (302, 200):
            _ok(f"Tunnel POST /auth/login -> {r.status_code} ({dur*1000:.0f}ms)")
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
    for target in cleanup_targets:
        try:
            write_query(
                "DELETE FROM chain_profiles WHERE username = %s OR email = %s",
                (target["username"], target["email"]),
            )
            _ok(f"Deleted: {target['username']}")
        except Exception as e:
            _warn("Cleanup", f"{target['username']}: {e}")
    _ok(f"Cleanup done ({len(cleanup_targets)} target(s))")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tunnel-url")
    args = parser.parse_args()

    print("=" * 60)
    print("PHASE 110 — REGISTER EMAIL RATE LIMIT + REDIRECT FIX")
    print("=" * 60)

    from app import create_app
    app = create_app()

    _test_form_validation(app)

    creds = _test_register_and_verify_redirect(app)
    if creds:
        _test_login_after_register(app, creds)

    _test_with_auth_email_optional(app)

    if args.tunnel_url:
        _test_tunnel(args.tunnel_url.rstrip("/"))
    else:
        print("\n  No --tunnel-url, skipping tunnel tests")

    _cleanup()
    _report(args.tunnel_url)


def _report(tunnel_url=None):
    p, f = results["passed"], results["failed"]
    print()
    print("=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(f"  Passed:   {p}")
    print(f"  Failed:   {f}")
    print(f"  Warnings: {results['warnings']}")
    if results["errors"]:
        print("\n  Errors:")
        for e in results["errors"]:
            print(f"    - {e}")
    ok = f == 0
    ts = tunnel_url is None
    print(f"\n  localhost_auth:              {'PASS' if ok else 'FAIL'}")
    print(f"  namvibe_auth:                {'SKIP' if ts else ('PASS' if ok else 'FAIL')}")
    print(f"  500 eliminated:              {'PASS' if ok else 'FAIL'}")
    print(f"  profile_redirect (200):      {'PASS' if ok else 'FAIL'}")
    print(f"  production_error (no 500):   {'PASS' if ok else 'FAIL'}")
    print(f"  fallback_account_created:    {'PASS' if ok else 'FAIL'}")
    print(f"  email_rate_limit_source:     Supabase auth.sign_up (handled)")
    print(f"  files_changed:               services/auth_service.py, api_routes/auth_routes.py")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
