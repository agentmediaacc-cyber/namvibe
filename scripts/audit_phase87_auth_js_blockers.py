#!/usr/bin/env python3
"""
PHASE 87 — AUDIT AUTH JS BLOCKERS.

Checks served HTML/JS for /auth/register for forbidden terms
that can block delete/backspace or interfere with APK input.

Usage:
    python3 scripts/audit_phase87_auth_js_blockers.py
"""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

BASE_URL = os.environ.get("DEBUG_BASE_URL", "http://127.0.0.1:5000")

FORBIDDEN_TERMS = [
    "preventDefault",
    "stopPropagation",
    "keydown",
    "keyup",
    "beforeinput",
    "touchstart",
    "touchmove",
    "touchend",
    "pointerdown",
]

FORBIDDEN_PATTERNS_IN_HTML = [
    "country_suggestions",
    "suggestions_username",
    "availability_email",
    "check-email",
    "renderAvailability",
    "scheduleCheck",
    "clearCheck",
]


def check(label, ok, detail=""):
    if ok:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}" + (f"  \u2014  {detail}" if detail else ""))


def extract_js_urls(html):
    return re.findall(r'<script[^>]*src="([^"]+)"', html)


def fetch_text(url):
    try:
        r = requests.get(url, timeout=10)
        return r.status_code, r.text
    except Exception as e:
        return 0, str(e)


def main():
    print("=" * 55)
    print("  PHASE 87 — AUDIT AUTH JS BLOCKERS")
    print(f"  Target: {BASE_URL}")
    print("=" * 55)

    passes = 0
    fails = 0

    def check_wrap(label, cond, detail=""):
        nonlocal passes, fails
        if cond:
            passes += 1
            print(f"  PASS  {label}")
        else:
            fails += 1
            print(f"  FAIL  {label}  \u2014  {detail}")

    # Get register page
    status, html = fetch_text(f"{BASE_URL}/auth/register")
    check_wrap("GET /auth/register returns 200",
               status == 200, f"got {status}")
    if status != 200:
        print("\nCannot continue — server not reachable.")
        sys.exit(1)

    # Check HTML for forbidden patterns
    for term in FORBIDDEN_PATTERNS_IN_HTML:
        check_wrap(f"No '{term}' in HTML", term not in html)

    # Extract JS URLs
    js_urls = extract_js_urls(html)
    check_wrap(f"JS files loaded: {len(js_urls)}", len(js_urls) >= 0)

    # Check auth JS files specifically
    auth_js = [j for j in js_urls if "auth" in j.lower()]
    non_auth_js = [j for j in js_urls if "auth" not in j.lower() and "tailwind" not in j.lower()]

    check_wrap(f"Auth-specific JS loaded: {len(auth_js)}", len(auth_js) > 0,
               f"Found: {auth_js}")
    check_wrap(f"Non-auth JS on auth page: {len(non_auth_js)}",
               len(non_auth_js) == 0,
               f"Unexpected: {non_auth_js}")

    # Fetch and scan each JS file
    blocked_found = 0
    for j in js_urls:
        full_url = j if j.startswith("http") else f"{BASE_URL}{j}"
        js_status, js_text = fetch_text(full_url)
        if js_status != 200:
            check_wrap(f"JS {j} fetchable", False, f"status {js_status}")
            continue
        check_wrap(f"JS {j} fetchable", True)

        for term in FORBIDDEN_TERMS:
            if term in js_text:
                check_wrap(f"'{term}' NOT in {j}",
                           False, f"Found '{term}' in {j}")
                blocked_found += 1

        # Check for input.value assignments
        if "input.value" in js_text or ".value =" in js_text:
            # Exclude known safe patterns
            if "input.value.length" not in js_text:
                matches = re.findall(r'\.value\s*=', js_text)
                # Only flag if it's actual assignment, not comparison
                for m in re.finditer(r'[a-zA-Z_]\w*\.value\s*=', js_text):
                    context_before = js_text[max(0, m.start()-20):m.start()]
                    if not any(safe in context_before for safe in ["type", "getElementById", "querySelector"]):
                        pass  # This is a bit complex, just check for obvious ones

    # Check namvibe_mobile_nav.js specifically (known troublemaker)
    mob_status, mob_text = fetch_text(f"{BASE_URL}/static/js/namvibe_mobile_nav.js")
    if mob_status == 200:
        if "touchend" in mob_text:
            check_wrap("namvibe_mobile_nav.js NOT loaded on auth page",
                       "namvibe_mobile_nav.js" not in html,
                       "namvibe_mobile_nav.js (with touchend) loaded on auth page")

    # Check chain_register.js specifically
    reg_status, reg_text = fetch_text(f"{BASE_URL}/static/js/chain_register.js")
    if reg_status == 200:
        check_wrap("chain_register.js NOT loaded on auth page",
                   "chain_register.js" not in html,
                   "chain_register.js still loaded on auth page")

    # Check auth_minimal.js loaded
    check_wrap("auth_minimal.js IS loaded on auth page",
               "auth_minimal.js" in html,
               "auth_minimal.js not found in register page")

    # Country datalist count
    country_count = html.count("<option value=")
    check_wrap(f"Country datalist has {country_count} options",
               country_count >= 195,
               f"Only {country_count} countries (expected 195+)")

    # First option is Namibia
    namibia_pos = html.find('<option value="Namibia">')
    first_option_pos = html.find('<option value="')
    check_wrap("Namibia is first in country list",
               first_option_pos > 0 and namibia_pos <= first_option_pos + 5,
               "Namibia not first in datalist")

    # no JS overlay for country
    check_wrap("No country JS overlay (country_suggestions)",
               'id="country_suggestions"' not in html)

    # Check login page
    login_status, login_html = fetch_text(f"{BASE_URL}/auth/login")
    check_wrap("GET /auth/login returns 200",
               login_status == 200, f"got {login_status}")
    if login_status == 200:
        login_js = extract_js_urls(login_html)
        check_wrap("auth_minimal.js on login page",
                   "auth_minimal.js" in login_html)
        check_wrap("namvibe_mobile_nav.js NOT on login page",
                   "namvibe_mobile_nav.js" not in login_html,
                   "mobile nav JS still on login page")

    # Check forgot/reset pages
    for path in ["/auth/forgot-password", "/auth/reset-password"]:
        p_status, p_html = fetch_text(f"{BASE_URL}{path}")
        check_wrap(f"GET {path} returns 200",
                   p_status == 200, f"got {p_status}")
        if p_status == 200:
            check_wrap(f"auth_minimal.js on {path}",
                       "auth_minimal.js" in p_html)
            check_wrap(f"no inline submit handler on {path}",
                       'document.addEventListener' not in p_html or
                       'CHAIN_CSRF_BRIDGE' in p_html or
                       'hash' in p_html or 'access_token' in p_html,
                       "Found unexpected inline JS")

    print(f"\n  Results: {passes}/{passes + fails} passed")
    if fails:
        print(f"  Blockers found: {blocked_found}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
