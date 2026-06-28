#!/usr/bin/env python3
"""Test locked gallery: blocks non-subscribers, allows subscribers."""
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
print("PHASE 158D - LOCKED GALLERY ACCESS")
print("=" * 60)

try:
    from services.subscriber_content_service import (
        can_access_content, check_media_access, get_media_access_level,
        set_media_access_level, get_locked_content
    )
    test("subscriber_content_service imports", True)
except ImportError as e:
    test("subscriber_content_service imports", False, str(e))

# Test can_access_content with different access levels
test("public content accessible to None", can_access_content(None, "owner1", "public"))
test("public content accessible to anyone", can_access_content("viewer1", "owner1", "public"))
test("owner can access own private", can_access_content("owner1", "owner1", "private"))
test("owner can access own subscribers", can_access_content("owner1", "owner1", "subscribers"))
test("stranger cannot access private", not can_access_content("stranger", "owner1", "private"))
test("stranger cannot access subscribers", not can_access_content("stranger", "owner1", "subscribers"))

# Test get_media_access_level returns something
level = get_media_access_level("nonexistent", "owner1")
test("get_media_access_level returns string for bad id", isinstance(level, str))

# Test check_media_access returns dict
try:
    result = check_media_access("viewer1", "media1", "owner1")
    test("check_media_access returns dict", isinstance(result, dict))
    test("check_media_access has can_view", "can_view" in result)
    test("check_media_access has access_level", "access_level" in result)
    test("check_media_access has needs_subscription", "needs_subscription" in result)
    test("check_media_access has needs_follow", "needs_follow" in result)
except Exception as e:
    test("check_media_access returns dict", False, str(e))

# Test set_media_access_level
try:
    result2 = set_media_access_level("media1", "owner1", "public")
    test("set_media_access_level returns dict", isinstance(result2, dict))
except Exception as e:
    test("set_media_access_level returns dict", False, str(e))

test("set_media_access_level invalid level", not set_media_access_level("m", "o", "invalid").get("ok"))

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
