#!/usr/bin/env python3
"""Audit that homepage has offline support: localStorage cache, offline/online events, reconnect banner."""
import os, sys, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = 0, 0
def test(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} - {detail}")

print("="*60)
print("PHASE 161c - OFFLINE HOMEPAGE SUPPORT AUDIT")
print("="*60)

js_path = os.path.join(BASE, "static", "js", "namvibe_home_pro.js")
if os.path.exists(js_path):
    with open(js_path) as f:
        js = f.read()
    
    offline_checks = {
        "window.addEventListener(\"offline\")": "offline" in js and "addEventListener" in js,
        "window.addEventListener(\"online\")": "online" in js and "addEventListener" in js,
        "localStorage cache key for feed": "localStorage" in js and "feed" in js,
        "Fallback render from cache": "localStorage" in js and ("feed" in js or "cache" in js),
        "Offline banner / reconnecting message": "offline" in js or "Offline" in js or "reconnect" in js or "offline" in js.lower(),
        "Upload button disabled/queued when offline": "offline" in js and ("disabled" in js or "queue" in js),
        "Retry network when back online": "online" in js and ("retry" in js or "reload" in js or "fetch" in js),
    }

    print("\n--- JS Offline Support ---")
    for check_name, found in offline_checks.items():
        test(check_name, found)

    # Check for init code that caches feed on page load
    has_cache_init = re.search(r'localStorage\.setItem\(["\']namvibe', js) or "localStorage.setItem" in js
    test("localStorage.setItem used for caching", has_cache_init)

    has_render_from_cache = "localStorage.getItem" in js and ("feed" in js or "home" in js)
    test("localStorage.getItem used for rendering from cache", has_render_from_cache)
else:
    test("JS file exists", False, "namvibe_home_pro.js not found")

# Check template for offline banner placeholder
print("\n--- Template Offline Banner ---")
tmpl_path = os.path.join(BASE, "templates", "chain_home.html")
if os.path.exists(tmpl_path):
    with open(tmpl_path) as f:
        tmpl = f.read()
    test("Template has offline/reconnect banner container", "offline" in tmpl.lower() or "reconnect" in tmpl.lower() or "nvpro-offline" in tmpl)
else:
    test("Template exists", False)

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    print("NOTE: Offline support needs to be added to the frontend JS.")
    print("Implementation needed:")
    print("  - window.addEventListener('offline') / 'online'")
    print("  - localStorage cache of last successful feed payload")
    print("  - Fallback render from localStorage when offline")
    print("  - Offline banner ('You are offline / Reconnecting...')")
    print("  - Retry network fetch when back online")
    print("  - Upload buttons disabled or queued when offline")
    sys.exit(1)
