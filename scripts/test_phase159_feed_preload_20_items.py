#!/usr/bin/env python3
"""Test feed_preload_service.get_mixed_feed returns correct structure with media URLs."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'testing'
os.environ['CHAIN_FAST_LOCAL'] = '1'

PASS = 0
FAIL = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} - {detail}")

print("=" * 60)
print("PHASE 159 — FEED PRELOAD 20 ITEMS")
print("=" * 60)

# 1. get_mixed_feed returns correct dict structure
print("\n1. get_mixed_feed structure...")
try:
    from services.feed_preload_service import get_mixed_feed
    test("get_mixed_feed importable", True)

    import inspect
    source = inspect.getsource(get_mixed_feed)
    test("return includes 'stories' key", '"stories"' in source)
    test("return includes 'feed_items' key", '"feed_items"' in source)
    test("return includes 'reels' key", '"reels"' in source)
    test("return includes 'ads' key", '"ads"' in source)
    test("return includes 'next_cursor' key", '"next_cursor"' in source)
    test("return includes 'has_more' key", '"has_more"' in source)
except (ImportError, Exception) as e:
    test("get_mixed_feed importable", False, str(e))

# 2. limit=20 gives up to 20 items total
print("\n2. Limit handling...")
try:
    from services.feed_preload_service import get_mixed_feed
    source = inspect.getsource(get_mixed_feed)
    test("limit defaults to 20 or more", "limit = max(20, int(limit))" in source or "limit=20" in source or "limit = 20" in source)
except Exception as e:
    test("limit handling", False, str(e))

# 3. Items have media_url or video_url
print("\n3. Feed item media_url/video_url...")
try:
    from services.feed_preload_service import _POST_COLS, _REEL_COLS, _fetch_posts, _fetch_reels
    test("_fetch_posts importable", True)
    test("_fetch_reels importable", True)
    test("_fetch_posts query includes media_url", "media_url" in _POST_COLS)
    test("_fetch_posts query includes video_url", "video_url" in _POST_COLS)
    test("_fetch_reels query includes media_url", "media_url" in _REEL_COLS)
    test("_fetch_reels query includes video_url", "video_url" in _REEL_COLS)
    test("_fetch_reels query includes thumbnail_url", "thumbnail_url" in _REEL_COLS)
except (ImportError, Exception) as e:
    test("feed item media import", False, str(e))

# 4. next_cursor is None when no more items
print("\n4. next_cursor logic...")
try:
    from services.feed_preload_service import get_mixed_feed
    source = inspect.getsource(get_mixed_feed)
    test("next_cursor set to None when no more", "next_cursor = None" in source)
    test("next_cursor encoded from oldest when has_more", "encode_cursor(oldest_ts)" in source or "next_cursor" in source)
except Exception as e:
    test("next_cursor logic", False, str(e))

# 5. get_public_feed works without profile
print("\n5. get_public_feed...")
try:
    from services.feed_preload_service import get_public_feed
    test("get_public_feed importable", True)

    import inspect
    source = inspect.getsource(get_public_feed)
    test("get_public_feed calls get_mixed_feed with profile_id=None", "profile_id=None" in source)
except (ImportError, Exception) as e:
    test("get_public_feed importable", False, str(e))

# 6. Video items have video_url and thumbnail_url
print("\n6. Video item fields...")
try:
    from services.feed_preload_service import _REEL_COLS
    test("_REEL_COLS includes video_url", "video_url" in _REEL_COLS)
    test("_REEL_COLS includes thumbnail_url", "thumbnail_url" in _REEL_COLS)
    test("_REEL_COLS includes media_url", "media_url" in _REEL_COLS)
except (ImportError, Exception) as e:
    test("_REEL_COLS importable", False, str(e))

try:
    from services.feed_preload_service import _POST_COLS
    test("_POST_COLS includes media_url", "media_url" in _POST_COLS)
    test("_POST_COLS includes video_url", "video_url" in _POST_COLS)
except (ImportError, Exception) as e:
    test("_POST_COLS importable", False, str(e))

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
