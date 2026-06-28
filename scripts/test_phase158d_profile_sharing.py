#!/usr/bin/env python3
"""Test profile/page sharing functionality."""
import sys
import os
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
print("PHASE 158D - PROFILE SHARING")
print("=" * 60)

try:
    from services.profile_sharing_service import get_share_data, SHARE_TYPES
    test("profile_sharing_service imports", True)
except ImportError as e:
    test("profile_sharing_service imports", False, str(e))

# Test share types
test("SHARE_TYPES defined", isinstance(SHARE_TYPES, set))
for t in ["profile", "post", "reel", "album", "business_page", "creator_page"]:
    test(f"share type '{t}' in SHARE_TYPES", t in SHARE_TYPES)

# Test get_share_data returns None for unknown
result = get_share_data("unknown_type", "123")
test("unknown type returns None", result is None)

# Test get_share_data for profile doesn't exist
result2 = get_share_data("profile", "nonexistent-id")
test("nonexistent profile returns None", result2 is None)

# Test get_share_data for post doesn't exist
result3 = get_share_data("post", "nonexistent-id")
test("nonexistent post returns None", result3 is None)

# Test get_share_data for album returns structure
result4 = get_share_data("album", "some-id")
test("album returns dict", isinstance(result4, dict))
test("album has type", result4.get("type") == "album")
test("album has title", "title" in result4)
test("album has url", "url" in result4)

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
