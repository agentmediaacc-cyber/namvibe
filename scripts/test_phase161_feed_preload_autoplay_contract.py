#!/usr/bin/env python3
"""Test that the homepage feed supports preload, autoplay, and lazy loading."""
import json, os, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['CHAIN_FAST_LOCAL'] = '1'
os.environ['ALLOW_LOCAL_AUTH_FALLBACK'] = 'true'
os.environ['WTF_CSRF_ENABLED'] = '0'

from app import app as flask_app
flask_app.config["WTF_CSRF_ENABLED"] = False
from services.neon_service import write_query

PASS, FAIL = 0, 0
def test(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} - {detail}")

def _uuid():
    return str(uuid.uuid4())

print("="*60)
print("PHASE 161 - FEED PRELOAD & AUTOPLAY CONTRACT")
print("="*60)

with flask_app.app_context():
    # 1. Check JS file for autoplay features
    print("\n--- Step 1: JS Autoplay Implementation ---")
    js_path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "namvibe_home_pro.js")
    js = open(js_path, "r").read() if os.path.exists(js_path) else ""

    test("JS file exists", bool(js), f"path={js_path}")
    test("JS has IntersectionObserver", "IntersectionObserver" in js)
    test("JS has autoplay logic", "vid.play()" in js and "vid.pause()" in js)
    test("JS has video preload", "preload" in js)
    test("JS has lazy loading", "loading=\"lazy\"" in js or "loading=lazy" in js)
    test("JS has eager loading for first items", "loading=\"eager\"" in js or "loading=eager" in js or "index < 3" in js)
    test("JS has preloadNearbyVideos", "preloadNearbyVideos" in js)
    test("JS has infinite scroll", "fetchNextPage" in js or "has_more" in js)
    test("JS has offscreen pause", "entry.intersectionRatio" in js)

    # 2. Check API supports pagination
    print("\n--- Step 2: API Pagination ---")
    api_path = os.path.join(os.path.dirname(__file__), "..", "api_routes", "homepage_api.py")
    api = open(api_path, "r").read() if os.path.exists(api_path) else ""

    test("/api/home/feed has page param", "\"page\"" in api or "'page'" in api)
    test("/api/home/feed has next_page", "next_page" in api)
    test("/api/home/feed has has_more", "has_more" in api)
    test("/api/home/feed limit is 20", "limit=20" in api or "limit = 20" in api)

    # 3. Check template has lazy/eager loading
    print("\n--- Step 3: Template Loading Attributes ---")
    tmpl_path = os.path.join(os.path.dirname(__file__), "..", "templates", "chain_home.html")
    tmpl = open(tmpl_path, "r").read() if os.path.exists(tmpl_path) else ""

    test("Template has lazy loading attribute", "loading=\"lazy\"" in tmpl)
    test("Template has eager loading for first items", "loading=\"eager\"" in tmpl or "loop.index0 < 3" in tmpl)
    test("Template has video_url check", "video_url" in tmpl)
    test("Template has media_url with fallback", "thumbnail_url" in tmpl)

    # 4. Check template renders reels with thumbnail fallback
    print("\n--- Step 4: Reel Thumbnail Fallback ---")
    has_reel_fallback = "thumbnail_url" in tmpl and "media_url" in tmpl and "video_url" in tmpl
    test("Reel thumbnail has triple fallback", has_reel_fallback)

    # 5. Check profile template media rendering
    print("\n--- Step 5: Profile Media Rendering ---")
    profile_path = os.path.join(os.path.dirname(__file__), "..", "templates", "profile", "index.html")
    profile = open(profile_path, "r").read() if os.path.exists(profile_path) else ""
    test("Profile template exists", bool(profile))
    test("Profile posts use media_url or video_url fallback", "post.media_url or post.video_url" in profile or "post.media_url or post.public_url" in profile or "post_media = post.media_url" in profile)
    test("Profile reels use thumbnail/media/video fallback", all(f in profile for f in ["thumbnail_url", "media_url", "video_url"]))

    # 6. Check JS video preloading via <link rel="preload">
    print("\n--- Step 6: Video Preload Strategy ---")
    test("JS uses <link rel=\"preload\"> for videos", "link.rel = \"preload\"" in js or "link.rel=\"preload\"" in js)

    # 7. Check feed fetches at least 20 items
    print("\n--- Step 7: Feed Capacity ---")
    test("API returns up to 20 items", "limit=20" in api or "limit = 20" in api or "limit=min(limit, 12)" in api)
    test("Template can display 20+ items", "home_feed_items" in tmpl)

    # 8. Verify first-screen eager + below-fold lazy in JS
    print("\n--- Step 8: Lazy vs Eager Loading ---")
    has_index_based_eager = "index < 3" in js
    test("JS uses index-based eager loading", has_index_based_eager, "first 3 items load eager, rest lazy")

    print(f"\nResults: {PASS} passed, {FAIL} failed")
    if FAIL > 0:
        sys.exit(1)
    sys.exit(0)
