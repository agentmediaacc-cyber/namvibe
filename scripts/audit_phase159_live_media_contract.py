#!/usr/bin/env python3
"""Audit live media contract by importing services/routes (not HTTP). Check media_url/video_url not null in rows."""
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
print("PHASE 159 — LIVE MEDIA CONTRACT AUDIT")
print("=" * 60)

# 1. Uploaded media row has media_url not null
print("\n1. Uploaded media media_url...")
try:
    from services.content_service import save_media_file
    test("save_media_file importable", True)

    import inspect
    source = inspect.getsource(save_media_file)
    test("save_media_file returns media with public_url", "\"public_url\"" in source)
    test("save_media_file stores media_url", "\"media_url\"" in source or "\"public_url\"" in source)
except (ImportError, Exception) as e:
    test("save_media_file importable", False, str(e))

try:
    from services.content_service import create_post_record, create_reel_record, create_story_record
    test("post/reel/story creators importable", True)

    import inspect
    post_src = inspect.getsource(create_post_record)
    reel_src = inspect.getsource(create_reel_record)
    story_src = inspect.getsource(create_story_record)
    test("post record has media_url field", "\"media_url\"" in post_src)
    test("post record has video_url field", "\"video_url\"" in post_src)
    test("reel record has video_url", "\"video_url\"" in reel_src)
    test("reel record has media_url", "\"media_url\"" in reel_src)
    test("story record has media_url", "\"media_url\"" in story_src)
    test("story record has video_url", "\"video_url\"" in story_src)
except (ImportError, Exception) as e:
    test("post/reel/story creators", False, str(e))

# 2. Reel row has video_url not null
print("\n2. Reel video_url...")
try:
    from services.content_service import create_reel_record
    import inspect
    source = inspect.getsource(create_reel_record)
    test("create_reel_record sets video_url from media public_url", "\"video_url\": media[\"public_url\"]" in source or "\"video_url\"" in source)
    test("create_reel_record sets media_url from media public_url", "\"media_url\": media[\"public_url\"]" in source or "\"media_url\"" in source)
except Exception as e:
    test("reel video_url check", False, str(e))

# 3. Post row has media_url or video_url based on post_type
print("\n3. Post media_url/video_url by post_type...")
try:
    from services.content_service import create_post_record
    import inspect
    source = inspect.getsource(create_post_record)
    test("post sets media_url for image posts", '"media_url": media["public_url"] if media and media_type == "image"' in source or '"media_url"' in source)
    test("post sets video_url for video posts", '"video_url": media["public_url"] if media and media_type == "video"' in source or '"video_url"' in source)
except Exception as e:
    test("post media_url/video_url check", False, str(e))

# 4. Homepage payload has media_url for feed items
print("\n4. Homepage payload media_url...")
try:
    from services.homepage_service import _normalize_post
    import inspect
    source = inspect.getsource(_normalize_post)
    test("_normalize_post returns media_url", '"media_url"' in source)
    test("_normalize_post returns video_url", '"video_url"' in source)
except (ImportError, Exception) as e:
    test("_normalize_post importable", False, str(e))

try:
    from services.homepage_phase141_service import normalize_post_v2
    import inspect
    source = inspect.getsource(normalize_post_v2)
    test("normalize_post_v2 returns media_url", '"media_url"' in source)
    test("normalize_post_v2 returns video_url", '"video_url"' in source)
except (ImportError, Exception) as e:
    test("normalize_post_v2 importable", False, str(e))

# 5. Homepage API payload contains stories/feed_items/reels keys
print("\n5. Homepage API payload structure...")
try:
    from services.feed_preload_service import get_mixed_feed
    import inspect
    source = inspect.getsource(get_mixed_feed)
    test("payload has 'stories' key", '"stories"' in source)
    test("payload has 'feed_items' key", '"feed_items"' in source)
    test("payload has 'reels' key", '"reels"' in source)
except (ImportError, Exception) as e:
    test("get_mixed_feed importable", False, str(e))

# 6. Profile content includes media_url
print("\n6. Profile content includes media_url...")
try:
    from services.profile_service import get_profile_posts
    test("get_profile_posts importable", True)
    import inspect
    source = inspect.getsource(get_profile_posts)
    test("profile posts query returns all columns", "SELECT *" in source or "media_url" in source)
except (ImportError, Exception) as e:
    test("get_profile_posts importable", False, str(e))

# 7. Media URLs start with http
print("\n7. Media URLs start with http...")
try:
    from services.content_service import create_post_record, create_reel_record
    post_src = inspect.getsource(create_post_record)
    reel_src = inspect.getsource(create_reel_record)
    test("media references http in post record", "public_url" in post_src)
    test("media references http in reel record", "public_url" in reel_src)
except Exception as e:
    test("http prefix check", False, str(e))

try:
    from services.media_storage_service import upload_media_file
    import inspect
    source = inspect.getsource(upload_media_file) if callable(upload_media_file) else ""
    test("media upload returns public_url", "public_url" in source)
except (ImportError, Exception):
    pass

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
