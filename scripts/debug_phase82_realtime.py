#!/usr/bin/env python3
"""
Phase 82 — Real HTTP Debug Script.
Hits the running Flask server at http://127.0.0.1:5000
Tests all 10 bug-hunt items.
"""
import re
import sys
import time
import requests

BASE = "http://127.0.0.1:5000"
sess = requests.Session()
sess.headers.update({"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36"})

errors = []
passes = 0
fails = 0

def check(name, cond, detail=""):
    global passes, fails
    if cond:
        passes += 1
        print(f"  PASS  {name}")
    else:
        fails += 1
        msg = f"  FAIL  {name}"
        if detail:
            msg += f"  \u2014  {detail}"
        print(msg)
        errors.append(f"{name}: {detail}")

def extract_csrf(html):
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else None

def follow_redirect(resp, max_depth=5):
    chain = [resp]
    for _ in range(max_depth):
        if chain[-1].status_code in (301, 302, 303, 307, 308):
            loc = chain[-1].headers.get("Location", "")
            if loc.startswith("/"):
                loc = BASE + loc
            chain.append(sess.get(loc, allow_redirects=False))
        else:
            break
    return chain

# ═══════════════════════════════════════════════════
# LOGIN PAGE
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("ITEM 8 — Login page shows Register/Create Account")
print("=" * 60)
t0 = time.perf_counter()
r = sess.get(f"{BASE}/auth/login", allow_redirects=False)
login_time = (time.perf_counter() - t0) * 1000
check("GET /auth/login status", r.status_code == 200, f"got {r.status_code}")
html = r.text.lower()
check("Create account link",
      'href="/auth/register"' in html and "create account" in html,
      "Missing link to /auth/register labeled Create account")
check("No account prompt", "no account?" in html,
      "Missing 'No account?' prompt")
check("Forgot password link", "forgot password" in html,
      "Missing Forgot password link")
print(f"  TIMING: {login_time:.0f}ms")

# ═══════════════════════════════════════════════════
# REGISTER PAGE
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("ITEM 5 — Register page load & timing")
print("=" * 60)
t0 = time.perf_counter()
r = sess.get(f"{BASE}/auth/register", allow_redirects=False)
reg_time = (time.perf_counter() - t0) * 1000
check("GET /auth/register status", r.status_code == 200, f"got {r.status_code}")
html = r.text
check("csrf_token input", 'name="csrf_token"' in html, "Missing csrf_token")
check("date_of_birth field", 'name="date_of_birth"' in html)
check("country_origin field", 'name="country_origin"' in html)
check("Create Account button", "Create Account" in html)
check("OAuth Google", "Continue with Google" in html or "/auth/google" in html)
check("OAuth Facebook", "Continue with Facebook" in html or "/auth/facebook" in html)
check("Back button", "data-go-back" in html or "js-go-back" in html)
csrf_token = extract_csrf(html)
check("CSRF token extracted", bool(csrf_token))
print(f"  TIMING: {reg_time:.0f}ms")

# ═══════════════════════════════════════════════════
# ITEM 3 — Reel view API
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("ITEM 3 — Reels view API (should not 400)")
print("=" * 60)
# Test without CSRF token (should be exempt)
t0 = time.perf_counter()
r = sess.post(f"{BASE}/reels/api/reels/test-reel-id/view",
              data={}, allow_redirects=False)
reels_time = (time.perf_counter() - t0) * 1000
check("POST /reels/api/reels/.../view status",
      r.status_code != 400,
      f"Got 400! Status: {r.status_code}")
check("No CSRF error",
      "csrf" not in r.text.lower() and "session expired" not in r.text.lower(),
      f"Body looks like CSRF error: {r.text[:200]}")
print(f"  TIMING: {reels_time:.0f}ms")
if r.status_code == 400:
    print(f"  RESPONSE BODY: {r.text[:300]}")

# Test Like endpoint (now CSRF-exempt)
print("\n  — Like endpoint —")
r = sess.post(f"{BASE}/reels/api/reels/test-reel-id/like",
              data={}, allow_redirects=False)
check("POST /reels/api/reels/.../like not 400",
      r.status_code != 400,
      f"Got 400! Status: {r.status_code}")
if r.status_code == 400:
    print(f"  RESPONSE BODY: {r.text[:300]}")

# Test Comment endpoint
print("\n  — Comment endpoint —")
r = sess.post(f"{BASE}/reels/api/reels/test-reel-id/comment",
              data={"text": "test"}, allow_redirects=False)
check("POST /reels/api/reels/.../comment not 400",
      r.status_code != 400,
      f"Got 400! Status: {r.status_code}")
if r.status_code == 400:
    print(f"  RESPONSE BODY: {r.text[:300]}")

# ═══════════════════════════════════════════════════
# ITEM 10 — Reel upload page
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("ITEM 10 — Reel upload page")
print("=" * 60)
t0 = time.perf_counter()
r = sess.get(f"{BASE}/reels/upload", allow_redirects=False)
upload_time = (time.perf_counter() - t0) * 1000
check("GET /reels/upload status",
      r.status_code in (200, 302),
      f"Unexpected {r.status_code}")
if r.status_code == 302:
    target = r.headers.get("Location", "")
    check("redirects to login (no auth)", "login" in target,
          f"Redirect target: {target}")
    check("next=/reels/upload preserved",
          "next=%2Freels%2Fupload" in target or "next=/reels/upload" in target,
          "Missing 'next' parameter in redirect")
print(f"  TIMING: {upload_time:.0f}ms")

# ═══════════════════════════════════════════════════
# ITEM 1 & 2 — Registration flow (will fail at Supabase)
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("ITEM 1 & 2 — Registration flow analysis")
print("=" * 60)

# Try submitting registration
import uuid
suffix = str(uuid.uuid4())[:8]
test_email = f"debug82_{suffix}@test.namvibe.local"
test_user = f"debug82_{suffix}"

print(f"  Trying registration for: {test_email} / {test_user}")

# Get fresh session + CSRF
sess2 = requests.Session()
sess2.headers.update({"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36"})
r_get = sess2.get(f"{BASE}/auth/register", allow_redirects=False)
csrf = extract_csrf(r_get.text)

import time as time_module
t0 = time_module.perf_counter()
r_post = sess2.post(f"{BASE}/auth/register", data={
    "csrf_token": csrf,
    "full_name": f"Debug {suffix}",
    "email": test_email,
    "username": test_user,
    "phone": f"+26481123{suffix[:4]}",
    "country_origin": "Testland",
    "date_of_birth": "2000-06-15",
    "gender": "female",
    "password": "DebugPass123!",
    "confirm_password": "DebugPass123!",
    "terms": "on",
}, allow_redirects=False)
reg_submit_time = (time_module.perf_counter() - t0) * 1000

check("Registration POST acceptable status",
      r_post.status_code in (200, 302),
      f"Unexpected {r_post.status_code}")

body = r_post.text.lower()
is_csrf_error = ("csrf" in body and "token" in body)
check("No CSRF error on POST", not is_csrf_error,
      f"CSRF error: {r_post.text[:200]}")

print(f"  POST status: {r_post.status_code}")
print(f"  Location: {r_post.headers.get('Location', 'N/A')}")
print(f"  TIMING: {reg_submit_time:.0f}ms")

if r_post.status_code == 302:
    target = r_post.headers.get("Location", "")
    check("Registration redirects to /profile/",
          "/profile/" in target,
          f"Redirection target: {target}")

    # Follow the redirect
    chain = follow_redirect(r_post)
    print(f"  Redirect chain ({len(chain)} hops):")
    for i, hop in enumerate(chain):
        print(f"    [{i}] {hop.status_code} {hop.url[:80]}")

    final = chain[-1]
    check("Final page is not /auth/login",
          "login" not in final.url.lower(),
          f"Ended up at login page: {final.url}")
    check("Final page is profile or profile-related",
          "profile" in final.url.lower() or final.status_code == 200,
          f"Unexpected destination: {final.url}")

    # Inspect session cookie
    session_cookie = sess2.cookies.get("session", domain="127.0.0.1")
    check("Session cookie set after registration",
          bool(session_cookie),
          "No session cookie found")

# ═══════════════════════════════════════════════════
# ITEM 7 — Profile page (without auth)
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("ITEM 7 — Profile page access")
print("=" * 60)
r = sess.get(f"{BASE}/profile/", allow_redirects=False)
check("GET /profile/ without auth redirects",
      r.status_code == 302,
      f"Unexpected {r.status_code}")
target = r.headers.get("Location", "")
check("redirects to /auth/login",
      "login" in target,
      f"Redirect target: {target}")
check("next=/profile/ preserved",
      "next=%2Fprofile%2F" in target or "next=/profile/" in target,
      "Missing 'next' parameter")

# ═══════════════════════════════════════════════════
# ITEM 9 — Profile save (GET /profile/edit)
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("ITEM 9 — Profile save/edit page")
print("=" * 60)
r = sess.get(f"{BASE}/profile/edit", allow_redirects=False)
check("GET /profile/edit redirects to login",
      r.status_code == 302,
      f"Unexpected {r.status_code}")
target = r.headers.get("Location", "")
check("redirects to /auth/login with next",
      "login" in target and "next" in target,
      f"Redirect: {target}")

# ═══════════════════════════════════════════════════
# ITEM 4 — JS file analysis for delete/backspace
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("ITEM 4 — JS file analysis for key/input blocking")
print("=" * 60)

import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
js_files = [
    "static/js/reels.js",
    "static/js/namvibe_2026_home.js",
    "static/js/tiktok_home.js",
    "static/js/chain_register.js",
    "static/js/chain_home.js",
    "static/js/message_composer.js",
    "static/js/namvibe_mobile_nav.js",
]

for js_rel in js_files:
    js_path = os.path.join(BASE_DIR, js_rel)
    if not os.path.exists(js_path):
        continue
    with open(js_path) as f:
        js = f.read()
    issues = []
    if "keydown" in js and ("preventDefault" in js or "e.preventDefault" in js):
        # Find exact lines with keydown + preventDefault
        lines = js.split("\n")
        for i, line in enumerate(lines, 1):
            if "keydown" in line.lower() or "keyup" in line.lower():
                # Check if there's a guard for input elements
                has_guard = any(g in js for g in ["tagName", "INPUT", "TEXTAREA"])
                if not has_guard and "preventDefault" in line:
                    issues.append(f"  L{i}: {line.strip()[:80]}")
            if "preventDefault" in line and ("Arrow" in line or "' '" in line or "Space" in line):
                issues.append(f"  L{i}: {line.strip()[:80]}")

    if issues:
        print(f"\n  {js_rel}: {len(issues)} potential blocking lines")
        for issue in issues:
            print(issue)
    else:
        print(f"  {js_rel}: OK (no input-blocking code)")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
total = passes + fails
print(f"  {passes} passed  /  {fails} failed  /  {total} total")
if errors:
    print("\nFAILURES:")
    for e in errors:
        print(f"  \u2022 {e}")

print(f"\n  Login page load: {login_time:.0f}ms")
print(f"  Register page load: {reg_time:.0f}ms")
print(f"  Registration submit: {reg_submit_time:.0f}ms")
print(f"  Reels API: {reels_time:.0f}ms")
print(f"  Reels upload page: {upload_time:.0f}ms")
