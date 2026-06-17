"""
Phase 75 — Debug CSRF Session Cookie Issue.

Proves that CSRF + session cookie works correctly when the client
sends back the session cookie on POST.

Usage:
  python3 scripts/debug_phase75_csrf_cookie.py

Also prints a curl command for manual APK testing.
"""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["FLASK_ENV"] = "development"
os.environ["ENV"] = "development"
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["SECRET_KEY"] = "test-debug-secret-key"

from app import create_app


def extract_csrf(html):
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else None


def main():
    app = create_app()
    client = app.test_client()

    print("=" * 70)
    print("Phase 75 — Debug CSRF Session Cookie Issue")
    print("=" * 70)

    # Step 1: GET /auth/register
    print("\n[Step 1] GET /auth/register")
    resp = client.get("/auth/register")
    print(f"  Status: {resp.status_code}")

    # Show all Set-Cookie headers
    set_cookies = resp.headers.getlist("Set-Cookie")
    print(f"  Set-Cookie headers ({len(set_cookies)}):")
    for i, c in enumerate(set_cookies):
        print(f"    [{i}] {c}")

    # Show session cookie specifically
    session_cookie = resp.headers.get("Set-Cookie")
    if session_cookie:
        print(f"  Session cookie present: {'session' in session_cookie.lower()}")
    else:
        print("  WARNING: No Set-Cookie header found!")

    # Extract CSRF token
    html = resp.data.decode("utf-8")
    csrf_token = extract_csrf(html)
    if csrf_token:
        print(f"  CSRF token extracted: {csrf_token[:30]}...")
    else:
        print("  FAIL: Could not extract CSRF token!")
        return False

    # Step 2: POST with same client (cookie is auto-sent)
    print("\n[Step 2] POST /auth/register with same client + CSRF token")
    print("  (Session cookie automatically sent by test_client)")

    # Use minimal valid-looking data (DOB included to pass validation)
    # We don't want to actually register, so use invalid email to trigger
    # validation error instead of CSRF error
    post_resp = client.post("/auth/register", data={
        "csrf_token": csrf_token,
        "full_name": "Debug User",
        "email": "debug-",
        "username": "debuguser",
        "phone": "+264811234999",
        "country_origin": "Namibia",
        "date_of_birth": "2000-01-15",
        "gender": "male",
        "password": "DebugPass123!",
        "confirm_password": "DebugPass123!",
        "terms": "on",
    })
    body = post_resp.data.decode("utf-8").lower()
    is_csrf_error = (
        "the csrf token is missing" in body
        or "the csrf token has expired" in body
        or "csrf session token" in body
        or "session token missing" in body
    )
    if is_csrf_error:
        print(f"  FAIL: Got CSRF error despite sending session cookie!")
        print(f"  Status: {post_resp.status_code}")

        # Check client cookie jar
        cookies = {c.name: c.value for c in client.cookie_jar}
        print(f"  Cookies in jar: {list(cookies.keys())}")
        return False
    else:
        print(f"  PASS: No CSRF error. Status: {post_resp.status_code}")
        print(f"  Response indicates validation or registration flow (not CSRF issue)")

    # Step 3: Show curl command for manual APK testing
    print("\n[Step 3] curl command for manual APK / browser test:")
    print()
    print("  # 1. GET register page + save cookies")
    print("  curl -v -c /tmp/nv_cookies.txt -b /tmp/nv_cookies.txt \\")
    print("    http://127.0.0.1:5000/auth/register 2>&1 | grep -i 'set-cookie\\|csrf_token'")
    print()
    print("  # 2. Extract CSRF token (copy from HTML)")
    print("  # Then POST:")
    print('  CSRF="<token from step 1>"')
    print("  curl -v -c /tmp/nv_cookies.txt -b /tmp/nv_cookies.txt \\")
    print('    -d "csrf_token=$CSRF&full_name=Test&email=t@t.com&username=tuser&phone=%2B264811234999&country_origin=Namibia&date_of_birth=2000-01-15&gender=male&password=Pass1234%21&confirm_password=Pass1234%21&terms=on" \\')
    print("    http://127.0.0.1:5000/auth/register")
    print()
    print("=" * 70)
    print("CONCLUSION: CSRF + session cookies work with same client.")
    print("If APK gets 'CSRF session token missing', the Android WebView")
    print("is NOT sending the session cookie back on POST.")
    print("Check: SESSION_COOKIE_SECURE=False (must be False for HTTP)")
    print("Check: SESSION_COOKIE_SAMESITE='Lax'")
    print("Check: SESSION_COOKIE_HTTPONLY=True")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
