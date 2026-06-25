#!/usr/bin/env python3
"""Audit media preload, autoplay, and video play/pause contracts."""
import os, sys, json, subprocess

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

LOCAL = "http://127.0.0.1:8080"

print("="*60)
print("PHASE 161c - MEDIA PRELOAD & AUTOPLAY CONTRACT")
print("="*60)

# 1. JS features
print("\n--- JS Autoplay Features ---")
js_path = os.path.join(BASE, "static", "js", "namvibe_home_pro.js")
if os.path.exists(js_path):
    with open(js_path) as f:
        js = f.read()
    test("JS file exists", bool(js))
    test("IntersectionObserver", "IntersectionObserver" in js)
    test("vid.play()", "vid.play()" in js)
    test("vid.pause()", "vid.pause()" in js)
    test("preload attribute", "preload" in js)
    test("lazy loading", "loading=\"lazy\"" in js)
    test("eager loading for first items", "loadMode" in js or "index < 3" in js)
    test("preloadNearbyVideos function", "preloadNearbyVideos" in js)
    test("fetchNextPage infinite scroll", "fetchNextPage" in js)
    test("offscreen pause", "entry.intersectionRatio" in js or "isIntersecting" in js)
    test("<link rel=\"preload\">", "link.rel = \"preload\"" in js)
else:
    test("JS file exists", False)

# 2. Template
print("\n--- Template Media ---")
tmpl_path = os.path.join(BASE, "templates", "chain_home.html")
if os.path.exists(tmpl_path):
    with open(tmpl_path) as f:
        tmpl = f.read()
    test("First 3 eager, rest lazy", ("loading=\"eager\"" in tmpl and "loading=\"lazy\"" in tmpl) or ("loading=\"{% if loop.index0 < 3" in tmpl and "loading=\"lazy\"" in tmpl))
    test("Video fallback chain", "video_url" in tmpl)
    test("Media URL fallback chain", "media_url" in tmpl and "thumbnail_url" in tmpl)
    test("onerror handler for broken images", "onerror" in tmpl)
else:
    test("Template exists", False)

# 3. Public media URL accessibility
print("\n--- Media URL accessibility ---")
r = subprocess.run(["curl", "-s", f"{LOCAL}/api/homepage/feed"], capture_output=True, text=True, timeout=30)
try:
    data = json.loads(r.stdout)
    items = data.get("payload", {}).get("feed_items", [])
    checked = 0
    for item in items[:3]:
        url = item.get("media_url") or item.get("video_url") or ""
        if url:
            r2 = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url], capture_output=True, text=True, timeout=10)
            code = r2.stdout.strip()
            test(f"Media URL {url[:50]}...", code == "200", f"HTTP {code}")
            checked += 1
    if checked == 0:
        test("Media URLs to verify", True, "no media items to check")
except Exception as e:
    test("Fetch feed for media URL check", False, str(e)[:100])

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
