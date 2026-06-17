#!/usr/bin/env python3
"""
PHASE 87 — REAL APK REGISTER HTTP DEBUG.

Makes real HTTP requests against the running Flask server
to diagnose registration flow issues.

Usage:
    python3 scripts/debug_phase87_real_apk_register.py
"""

import os
import sys
import json
import uuid
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

BASE_URL = os.environ.get("DEBUG_BASE_URL", "http://127.0.0.1:5000")
TIMEOUT = 30


def debug(msg):
    print(f"[DEBUG] {msg}")


def fail(msg):
    print(f"[FAIL] {msg}")


def ok(msg):
    print(f"[OK]   {msg}")


def extract_csrf(html, name="csrf_token"):
    import re
    m = re.search(r'name="' + name + r'"\s+value="([^"]+)"', html)
    return m.group(1) if m else None


def extract_apk_csrf(html):
    import re
    m = re.search(r'name="apk_csrf_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else None


def extract_form_action(html):
    import re
    m = re.search(r'<form[^>]*action="([^"]*)"', html)
    return m.group(1) if m else "/auth/register"


def extract_title(html):
    import re
    m = re.search(r'<title>([^<]+)</title>', html)
    return m.group(1) if m else "(no title)"


def extract_js_urls(html):
    import re
    return re.findall(r'<script[^>]*src="([^"]+)"', html)


def extract_error(html):
    import re
    m = re.search(r'class="chain-auth-alert chain-auth-alert--error">\s*(.*?)</div>', html, re.DOTALL)
    if m:
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        return text[:200]
    return None


def main():
    print("=" * 65)
    print("  PHASE 87 — REAL APK REGISTER DEBUG")
    print(f"  Target: {BASE_URL}")
    print("=" * 65)

    session = requests.Session()
    unique_suffix = str(uuid.uuid4())[:8]

    # Step 1: GET register page
    print("\n── Step 1: GET /auth/register ──")
    try:
        resp = session.get(f"{BASE_URL}/auth/register", timeout=TIMEOUT)
        print(f"  status: {resp.status_code}")
        print(f"  url:    {resp.url}")
        print(f"  title:  {extract_title(resp.text)}")

        # Cookies
        cookies = dict(session.cookies)
        print(f"  cookies: {json.dumps({k: v[:30] + '...' if len(v) > 30 else v for k, v in cookies.items()})}")

        # CSRF tokens
        csrf = extract_csrf(resp.text)
        apk_csrf = extract_apk_csrf(resp.text)
        print(f"  csrf_token:     {'EXISTS' if csrf else 'MISSING'}")
        print(f"  apk_csrf_token: {'EXISTS' if apk_csrf else 'MISSING'}")

        if not csrf:
            fail("csrf_token missing!")
        if not apk_csrf:
            fail("apk_csrf_token missing!")

        # form action
        action = extract_form_action(resp.text)
        print(f"  form action: {action}")

        # JS URLs
        js_urls = extract_js_urls(resp.text)
        print(f"  JS loaded ({len(js_urls)}):")
        for j in js_urls:
            blocker_terms = ["keydown", "keyup", "beforeinput", "touchstart", "touchmove",
                             "touchend", "pointerdown", "preventDefault", "stopPropagation",
                             "input.value =", "check-email", "country_suggestions", "availability_email"]
            flagged = any(t in j.lower() for t in blocker_terms)
            flag = "  <-- CHECK" if flagged else ""
            print(f"    {j}{flag}")

        # Check for forbidden JS terms
        forbidden = ["preventDefault", "keydown", "keyup", "beforeinput",
                     "touchstart", "touchmove", "touchend", "pointerdown"]
        has_blocker = False
        for j in js_urls:
            if j.endswith(".js"):
                try:
                    js_resp = session.get(f"{BASE_URL}{j}", timeout=5)
                    js_text = js_resp.text
                    for term in forbidden:
                        if term in js_text:
                            fail(f"'{term}' found in {j}")
                            has_blocker = True
                except Exception:
                    pass
        if not has_blocker:
            ok("No forbidden JS terms in loaded scripts")

    except requests.ConnectionError:
        fail(f"Cannot connect to {BASE_URL}. Is the Flask server running?")
        sys.exit(1)
    except Exception as e:
        fail(f"GET failed: {e}")
        sys.exit(1)

    # Step 2: POST registration with unique user
    print("\n── Step 2: POST /auth/register (unique user) ──")
    ts = int(time.time())
    test_email = f"test{ts}_{unique_suffix}@example.com"
    test_username = f"testuser_{unique_suffix}"
    test_full_name = f"Test User {unique_suffix}"
    test_phone = f"+26481{ts % 10000000:07d}"
    test_password = "TestPass123!"

    form_data = {
        "csrf_token": csrf,
        "apk_csrf_token": apk_csrf,
        "full_name": test_full_name,
        "email": test_email,
        "username": test_username,
        "phone": test_phone,
        "country_origin": "Namibia",
        "date_of_birth": "2000-01-01",
        "gender": "male",
        "password": test_password,
        "confirm_password": test_password,
        "terms": "on",
        "human_confirmed": "on",
        "profile_type": "member",
        "signup_method": "email",
    }

    debug(f"email:    {test_email}")
    debug(f"username: {test_username}")
    debug(f"phone:    {test_phone}")

    try:
        resp = session.post(
            f"{BASE_URL}/auth/register",
            data=form_data,
            allow_redirects=False,
            timeout=TIMEOUT,
        )
        print(f"  POST status: {resp.status_code}")
        print(f"  Location:    {resp.headers.get('Location', '(none)')}")
        print(f"  Set-Cookie:  {resp.headers.get('Set-Cookie', '(none)')[:80] if resp.headers.get('Set-Cookie') else '(none)'}")

        cookies_after = dict(session.cookies)
        session_cookie = cookies_after.get("session")
        print(f"  session cookie present: {'YES' if session_cookie else 'NO'}")

        if resp.status_code in (302, 303, 307, 308):
            location = resp.headers.get("Location", "")
            ok(f"Redirect: {location}")

            # Follow redirect
            print(f"\n── Step 3: Follow redirect to {location} ──")
            follow = session.get(f"{BASE_URL}{location}", allow_redirects=True, timeout=TIMEOUT)
            print(f"  final status: {follow.status_code}")
            print(f"  final url:    {follow.url}")
            print(f"  final title:  {extract_title(follow.text)}")

            # Save HTML
            with open("/tmp/phase87_register_post.html", "w") as f:
                f.write(resp.text)
            with open("/tmp/phase87_final_page.html", "w") as f:
                f.write(follow.text)
            ok("HTML saved to /tmp/phase87_register_post.html and /tmp/phase87_final_page.html")

            # Check if redirected to login
            if "/auth/login" in follow.url:
                fail("REDIRECTED TO LOGIN!")
                fail("Possible causes:")
                # Check session
                final_cookies = dict(session.cookies)
                if not final_cookies.get("session"):
                    fail("  - No session cookie after registration")
                if "auth_user_id" not in follow.text and "Log In" in follow.text:
                    fail("  - Login page shown, profile not found")
                fail("  - Check server logs for login_required rejection")
                fail("  - Check CSRF fallback")
            elif "/profile/" in follow.url:
                ok(f"SUCCESS: Final page is {follow.url}")

                # Check for profile existence (by looking for profile elements)
                if "Welcome" in follow.text:
                    ok("Welcome message found")
                if "Finish setting up" in follow.text or "verify email" in follow.text.lower():
                    ok("Onboarding/verify hint found")

        elif resp.status_code == 200:
            print(f"  Server returned same page (likely error)")
            error_msg = extract_error(resp.text)
            if error_msg:
                fail(f"  Error on page: {error_msg}")
            else:
                fail("  No error message found, but page re-rendered")

            with open("/tmp/phase87_register_post.html", "w") as f:
                f.write(resp.text)
            debug("HTML saved to /tmp/phase87_register_post.html")
        else:
            fail(f"Unexpected status: {resp.status_code}")

    except Exception as e:
        fail(f"POST failed: {e}")

    # Step 4: Print summary
    print("\n" + "=" * 65)
    print("  SUMMARY")
    print("=" * 65)
    print(f"  Register page GET:  {'OK' if csrf else 'FAIL'}")
    print(f"  CSRF tokens:        {'OK' if csrf and apk_csrf else 'FAIL'}")
    print(f"  Session cookie:     {'OK' if dict(session.cookies).get('session') else 'FAIL'}")
    print(f"  JS blockers:        {'NONE' if not has_blocker else 'FOUND'}")
    print(f"  Countries in datalist: {resp.text.count('<option value=') if resp.status_code == 200 else 'N/A'}")
    print(f"  Auth JS:            {[j for j in (extract_js_urls(resp.text) if resp.status_code == 200 else []) if 'auth' in j.lower()]}")
    print("=" * 65)


if __name__ == "__main__":
    main()
