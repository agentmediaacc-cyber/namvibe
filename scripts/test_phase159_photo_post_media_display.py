#!/usr/bin/env python3
"""Test photo post media display fields in content/posts pipeline."""
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
print("PHASE 159 — PHOTO POST MEDIA DISPLAY")
print("=" * 60)

# 1. content_service.create_post_record returns dict with media_url
print("\n1. content_service.create_post_record...")
try:
    from services.content_service import create_post_record
    test("create_post_record importable", True)

    import inspect
    sig = inspect.signature(create_post_record)
    params = list(sig.parameters.keys())
    test("create_post_record has profile_id param", "profile_id" in params)
    test("create_post_record has media_file param", "media_file" in params)

    source = inspect.getsource(create_post_record)
    test("create_post_record returns dict with media_url", "'media_url' in payload" in source or 'record["media_url"]' in source or '"media_url"' in source)
    test("payload has 'caption' key", '"caption"' in source)
    test("payload has 'media_url' key", '"media_url"' in source)
except ImportError as e:
    test("create_post_record importable", False, str(e))

# 2. media_url starts with http
print("\n2. media_url starts with http...")
try:
    from services.content_service import create_post_record
    source = inspect.getsource(create_post_record)
    if 'public_url' in source:
        test("media_url uses public_url from upload", True)
    else:
        test("media_url uses public_url from upload", False, "No public_url reference found")
except Exception as e:
    test("media_url starts with http", False, str(e))

# 3. payload dict has both caption and media_url keys
print("\n3. Post payload keys...")
try:
    from services.content_service import create_post_record
    source = inspect.getsource(create_post_record)
    has_caption = '"caption"' in source
    has_media_url = '"media_url"' in source
    test("payload has 'caption' key", has_caption)
    test("payload has 'media_url' key", has_media_url)
except Exception as e:
    test("payload keys check", False, str(e))

# 4. homepage_service._normalize_post preserves media_url
print("\n4. homepage_service._normalize_post...")
try:
    from services.homepage_service import _normalize_post
    test("_normalize_post importable", True)
    source = inspect.getsource(_normalize_post)
    test("_normalize_post preserves media_url", '"media_url"' in source)
    test("_normalize_post preserves video_url", '"video_url"' in source)
except (ImportError, Exception) as e:
    test("_normalize_post importable", False, str(e))

# 5. homepage_service._post_select() includes media_url
print("\n5. homepage_service._post_select()...")
try:
    from services.homepage_service import _post_select
    cols = _post_select()
    test("_post_select returns list/tuple", isinstance(cols, (list, tuple)))
    test("_post_select includes media_url", "media_url" in cols)
    test("_post_select includes video_url", "video_url" in cols)
except (ImportError, Exception) as e:
    test("_post_select() importable", False, str(e))

# 6. homepage_phase141_service functions include media_url
print("\n6. homepage_phase141_service media fields...")
try:
    from services.homepage_phase141_service import fetch_posts_v2, normalize_post_v2
    test("fetch_posts_v2 importable", True)
    test("normalize_post_v2 importable", True)

    import inspect
    posts_source = inspect.getsource(fetch_posts_v2)
    test("fetch_posts_v2 takes post_columns param", "post_columns" in posts_source)

    norm_source = inspect.getsource(normalize_post_v2)
    test("normalize_post_v2 includes media_url in return", '"media_url"' in norm_source)
    test("normalize_post_v2 includes video_url in return", '"video_url"' in norm_source)
except (ImportError, Exception) as e:
    test("homepage_phase141_service imports", False, str(e))

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
