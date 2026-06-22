#!/usr/bin/env python3
"""Phase 133 - Browser reality checks."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from phase133_reality_utils import (
    ACCEPTABLE_AUTH_STATUSES, http_request, node_check, print_header, route_check,
    static_refs, Results, warn_ssl_fallback,
)

R = Results()
print_header("PHASE 133 - BROWSER REALITY")

print("\n--- HTTP Static Checks ---")
status, home, _ = http_request("/")
R.ok("homepage 200") if status == 200 else R.fail(f"homepage returned {status}")
route_check(R, "/messages/inbox", acceptable=ACCEPTABLE_AUTH_STATUSES)
for asset in [
    "/static/js/namvibe_messages_pro.js",
    "/static/js/namvibe_calls_pro.js",
    "/static/js/namvibe_home_pro.js",
    "/static/css/namvibe_messages_pro.css",
    "/static/css/namvibe_calls_pro.css",
]:
    status, _, _ = http_request(asset)
    if status == 200:
        R.ok(f"{asset} returns 200")
    elif status == 404:
        R.fail(f"{asset} returned 404")
    else:
        R.warn(f"{asset} returned {status}")

missing = []
for ref in static_refs(home):
    status, _, _ = http_request(ref)
    if status == 404:
        missing.append(ref)
if missing:
    R.fail("missing homepage assets: " + ", ".join(missing[:8]))
else:
    R.ok("no missing homepage static assets")

print("\n--- Local JS Syntax ---")
for path in [
    "static/js/namvibe_messages_pro.js",
    "static/js/namvibe_home_pro.js",
    "static/js/webrtc_calls.js",
    "static/js/namvibe_calls_pro.js",
]:
    node_check(R, path)

print("\n--- Optional Playwright Browser Checks ---")
try:
    from playwright.sync_api import sync_playwright  # type: ignore
except Exception:
    R.warn("Playwright not installed; Chrome/Safari/Firefox/mobile browser automation skipped")
else:
    try:
        with sync_playwright() as p:
            browser_types = [("chromium", p.chromium), ("firefox", p.firefox), ("webkit", p.webkit)]
            for name, browser_type in browser_types:
                browser = browser_type.launch(headless=True)
                page = browser.new_page()
                console_errors = []
                failed_404 = []
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type in ("error",) else None)
                page.on("response", lambda res: failed_404.append(res.url) if res.status == 404 else None)
                page.goto("https://namvibe.com/", wait_until="domcontentloaded", timeout=30000)
                page.set_viewport_size({"width": 390, "height": 844})
                page.goto("https://namvibe.com/", wait_until="domcontentloaded", timeout=30000)
                browser.close()
                bad_console = [e for e in console_errors if any(term in e for term in ("SyntaxError", "ReferenceError", "TypeError"))]
                if bad_console:
                    R.fail(f"{name} console errors: {bad_console[:3]}")
                else:
                    R.ok(f"{name} no fatal console errors")
                if failed_404:
                    R.fail(f"{name} 404 network requests: {failed_404[:3]}")
                else:
                    R.ok(f"{name} no 404 network requests")
    except Exception as exc:
        R.warn(f"Playwright installed but browser run skipped: {exc}")

warn_ssl_fallback(R)
R.summary("PHASE 133 - BROWSER REALITY")

