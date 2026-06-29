#!/usr/bin/env python3
"""Phase 5 Stories 2.0 Tests — 20 test cases"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["CHAIN_TEST_MODE"] = "1"

tests_passed = 0
tests_failed = 0

def test(desc, fn):
    global tests_passed, tests_failed
    try:
        fn()
        tests_passed += 1
        print(f"  PASS  {desc}")
    except AssertionError as e:
        tests_failed += 1
        print(f"  FAIL  {desc}: {e}")
    except Exception as e:
        tests_failed += 1
        print(f"  FAIL  {desc}: {type(e).__name__}: {e}")

print("=" * 60)
print("Phase 5 Stories 2.0 Tests")
print("=" * 60)

# Setup — mock neon_service
import unittest.mock as mock
import services.neon_service as neon

neon.fast_query = mock.MagicMock(return_value=[])
neon.write_query = mock.MagicMock(return_value=True)

from services.stories_engine import (
    get_story_feed, get_grouped_stories, get_story_detail,
    record_story_view_v2, react_to_story_v2, reply_to_story_v2,
    record_story_analytics_event, can_view_story_v2,
    get_story_viewers, get_story_analytics, get_creator_story_stats,
    create_story_v2, delete_story_v2, get_close_friends,
    get_hidden_users, get_highlights, create_highlight,
    delete_highlight, add_stories_to_highlight,
)

# 1.
def test_feed_list():
    result = get_story_feed(None)
    assert isinstance(result, list)
test("get_story_feed returns list", test_feed_list)

# 2.
def test_grouped_list():
    result = get_grouped_stories(None)
    assert isinstance(result, list)
test("get_grouped_stories returns list", test_grouped_list)

# 3.
def test_detail_none():
    neon.fast_query.return_value = None
    assert get_story_detail(1, None) is None
test("get_story_detail missing returns None", test_detail_none)

# 4.
def test_view_bool():
    assert record_story_view_v2(1, 1) in (True, False)
test("record_story_view_v2 returns bool", test_view_bool)

# 5.
def test_react_bool():
    assert react_to_story_v2(1, 1, "❤️") in (True, False)
test("react_to_story_v2 returns bool", test_react_bool)

# 6.
def test_reply_bool():
    assert reply_to_story_v2(1, 1, "Nice!") in (True, False)
test("reply_to_story_v2 returns bool", test_reply_bool)

# 7.
def test_analytics_event():
    record_story_analytics_event(1, 1, "forward")
    assert True
test("record_story_analytics_event no error", test_analytics_event)

# 8.
def test_can_view_public():
    neon.fast_query.return_value = [{"id": 1, "profile_id": 100, "visibility": "public", "expires_at": "2099-01-01T00:00:00Z"}]
    allowed, reason = can_view_story_v2(1, None)
    assert allowed == True
test("can_view_story_v2 public allows anon", test_can_view_public)

# 9.
def test_can_view_private():
    neon.fast_query.return_value = [{"id": 1, "profile_id": 100, "visibility": "private", "expires_at": "2099-01-01T00:00:00Z"}]
    allowed, reason = can_view_story_v2(1, 200)
    assert allowed == False
test("can_view_story_v2 private denies others", test_can_view_private)

# 10.
def test_can_view_owner():
    neon.fast_query.return_value = [{"id": 1, "profile_id": 100, "visibility": "private", "expires_at": "2099-01-01T00:00:00Z"}]
    allowed, reason = can_view_story_v2(1, 100)
    assert allowed == True
test("can_view_story_v2 owner can view private", test_can_view_owner)

# 11.
def test_viewers_dict():
    result = get_story_viewers(1)
    assert isinstance(result, dict)
    assert "viewers" in result and "count" in result
test("get_story_viewers returns dict", test_viewers_dict)

# 12.
def test_analytics_none():
    neon.fast_query.return_value = []
    assert get_story_analytics(1, 100) is None
test("get_story_analytics unauthorized returns None", test_analytics_none)

# 13.
def test_creator_stats_dict():
    result = get_creator_story_stats(100, requesting_profile_id=200)
    assert isinstance(result, dict)
test("get_creator_story_stats returns dict for others", test_creator_stats_dict)

# 14.
def test_creator_stats_own():
    result = get_creator_story_stats(100, requesting_profile_id=100)
    assert isinstance(result, dict)
test("get_creator_story_stats returns dict for owner", test_creator_stats_own)

# 15.
def test_create_story():
    result, error = create_story_v2(100, media_type="image", media_url="https://example.com/img.jpg")
    assert result is not None and error is None
test("create_story_v2 success", test_create_story)

# 16.
def test_create_story_no_media():
    result, error = create_story_v2(100)
    assert result is None and error is not None
test("create_story_v2 without media returns error", test_create_story_no_media)

# 17.
def test_delete_story():
    assert delete_story_v2("1", 100) in (True, False)
test("delete_story_v2 returns bool", test_delete_story)

# 18.
def test_highlights_list():
    result = get_highlights(100)
    assert isinstance(result, list)
test("get_highlights returns list", test_highlights_list)

# 19.
def test_create_highlight():
    result = create_highlight(100, "Test Highlight")
    assert result is None or isinstance(result, dict)
test("create_highlight returns dict or None", test_create_highlight)

# 20.
def test_close_friends():
    result = get_close_friends(100)
    assert isinstance(result, list)
    result2 = get_hidden_users(100)
    assert isinstance(result2, list)
test("get_close_friends and get_hidden_users return list", test_close_friends)

print()
print(f"Results: {tests_passed} passed, {tests_failed} failed")
if tests_failed:
    sys.exit(1)
