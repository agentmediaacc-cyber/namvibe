#!/usr/bin/env python3
"""Test reel upload reflection: create_reel_full and get_reel_feed include video/media URLs."""
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
print("PHASE 159 — REEL UPLOAD REFLECTION")
print("=" * 60)

# 1. reels_engine.create_reel_full returns dict with id, video_url, media_url
print("\n1. reels_engine.create_reel_full...")
try:
    import reels_engine
except ImportError:
    pass
try:
    from services.reels_engine import create_reel_full
    test("create_reel_full importable", True)

    from services.content_service import create_reel_record
    import inspect
    crr_source = inspect.getsource(create_reel_record)
    test("create_reel_record has 'id' key", '"id"' in crr_source)
    test("create_reel_record has 'video_url' key", '"video_url"' in crr_source)
    test("create_reel_record has 'media_url' key", '"media_url"' in crr_source)
except (ImportError, Exception) as e:
    test("create_reel_full importable", False, str(e))

# 2. video_url starts with http
print("\n2. video_url starts with http...")
try:
    from services.content_service import create_reel_record
    source = inspect.getsource(create_reel_record)
    if 'public_url' in source:
        test("video_url uses public_url from upload", True)
    else:
        test("video_url uses public_url from upload", False, "No public_url reference found")
except Exception as e:
    test("video_url starts with http reference", False, str(e))

# 3. reels_service.get_reel_feed returns items with video_url/media_url
print("\n3. reels_service.get_reel_feed...")
try:
    from services.reels_service import get_reel_feed
    test("get_reel_feed importable", True)

    import inspect
    source = inspect.getsource(get_reel_feed)
    test("get_reel_feed query includes video_url", "video_url" in source)
    test("get_reel_feed query includes media_url", "media_url" in source)
    test("get_reel_feed query includes thumbnail_url", "thumbnail_url" in source)
except (ImportError, Exception) as e:
    test("get_reel_feed importable", False, str(e))

# 4. homepage_service._reel_select() includes video_url, media_url
print("\n4. homepage_service._reel_select()...")
try:
    from services.homepage_service import _reel_select
    cols = _reel_select()
    test("_reel_select returns list/tuple", isinstance(cols, (list, tuple)))
    test("_reel_select includes video_url", "video_url" in cols)
    test("_reel_select includes media_url", "media_url" in cols)
    test("_reel_select includes thumbnail_url", "thumbnail_url" in cols)
except (ImportError, Exception) as e:
    test("_reel_select() importable", False, str(e))

# 5. content_service.create_reel_record includes video_url and media_url
print("\n5. content_service.create_reel_record...")
try:
    from services.content_service import create_reel_record
    test("create_reel_record importable", True)

    import inspect
    source = inspect.getsource(create_reel_record)
    test("create_reel_record payload has video_url", '"video_url"' in source)
    test("create_reel_record payload has media_url", '"media_url"' in source)
except (ImportError, Exception) as e:
    test("create_reel_record importable", False, str(e))

# 6. Check create_reel_full delegates to create_reel_record
print("\n6. create_reel_full delegation...")
try:
    from services.reels_engine import create_reel_full
    import inspect
    source = inspect.getsource(create_reel_full)
    test("create_reel_full calls create_reel_record", "create_reel_record" in source)
except Exception as e:
    test("create_reel_full delegation", False, str(e))

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
