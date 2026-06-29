#!/usr/bin/env python3
"""Phase 4 Reels Engine Tests — 15 test cases"""

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
print("Phase 4 Reels Engine Tests")
print("=" * 60)

# Setup — mock neon_service
import unittest.mock as mock
import services.neon_service as neon

# Mock fast_query to return empty lists
neon.fast_query = mock.MagicMock(return_value=[])
neon.write_query = mock.MagicMock(return_value=True)
neon.fast_query_one = mock.MagicMock(return_value=None)

from services.reels_engine import (
    rank_reels_for_viewer, get_reels_feed, get_reel_detail,
    track_reel_watch, get_creator_reel_stats, get_next_reels,
    get_reel_comments_summary, like_reel_v2, unlike_reel,
    save_reel, unsave_reel, share_reel_v2,
)


# 1.
def test_rank_empty():
    assert rank_reels_for_viewer(None, []) == []
test("rank_reels_for_viewer empty list", test_rank_empty)


# 2.
def test_rank_all():
    reels = [
        {"id": 1, "likes_count": 10, "comments_count": 2, "shares_count": 1,
         "saves_count": 1, "views_count": 50, "watch_time": 10, "completion_rate": 0.5,
         "profile_id": 100, "created_at": "2026-01-01T00:00:00Z"},
        {"id": 2, "likes_count": 5, "comments_count": 1, "shares_count": 0,
         "saves_count": 0, "views_count": 20, "watch_time": 5, "completion_rate": 0.3,
         "profile_id": 200, "created_at": "2026-06-01T00:00:00Z"},
    ]
    assert len(rank_reels_for_viewer(None, reels)) == 2
test("rank_reels_for_viewer returns all", test_rank_all)


# 3.
def test_feed_tuple():
    result = get_reels_feed(None, "for_you")
    assert isinstance(result, tuple) and len(result) == 2
test("get_reels_feed returns tuple", test_feed_tuple)


# 4.
def test_detail_missing():
    neon.fast_query.return_value = []
    assert get_reel_detail(None, 999) is None
test("get_reel_detail returns None for missing", test_detail_missing)


# 5.
def test_detail_dict():
    neon.fast_query.return_value = [{
        "id": 1, "profile_id": 100, "display_name": "Test", "avatar_url": "",
        "caption": "hi", "video_url": "", "likes_count": 5, "comments_count": 2,
        "views_count": 10, "shares_count": 1, "saves_count": 0, "duration_seconds": 15,
    }]
    assert isinstance(get_reel_detail(1, 1), dict)
test("get_reel_detail returns dict", test_detail_dict)


# 6.
def test_watch_bool():
    assert track_reel_watch(1, 1, 5000, completed=False) in (True, False)
test("track_reel_watch with viewer", test_watch_bool)


# 7.
def test_watch_completed():
    assert track_reel_watch(1, 1, 15000, completed=True) in (True, False)
test("track_reel_watch completed", test_watch_completed)


# 8.
def test_stats_dict():
    neon.fast_query.return_value = [(0, 0, 0, 0, 0, 0)]
    result = get_creator_reel_stats(100)
    assert isinstance(result, dict)
test("get_creator_reel_stats returns dict", test_stats_dict)


# 9.
def test_stats_unauthorized():
    neon.fast_query.return_value = [(5, 100, 50, 10, 5, 2)]
    result = get_creator_reel_stats(100, requesting_profile_id=200)
    assert result == {
        "total_reels": 0, "total_views": 0, "total_likes": 0,
        "total_comments": 0, "total_shares": 0, "total_saves": 0,
        "avg_watch_ms": 0, "completion_rate": 0,
    }
test("get_creator_reel_stats unauthorized empty", test_stats_unauthorized)


# 10.
def test_next_list():
    neon.fast_query.return_value = []
    assert isinstance(get_next_reels(None, 1), list)
test("get_next_reels returns list", test_next_list)


# 11.
def test_comments_summary():
    neon.fast_query.side_effect = [[(0,)], []]
    result = get_reel_comments_summary(1)
    assert isinstance(result, dict)
    neon.fast_query.side_effect = None
test("get_reel_comments_summary returns dict", test_comments_summary)


# 12.
def test_like_tuple():
    with mock.patch("services.reels_engine._emit_reel_activity", return_value=None):
        with mock.patch("services.reels_engine._notify_creator", return_value=None):
            result = like_reel_v2(1, 1)
            assert isinstance(result, tuple) and len(result) == 2
test("like_reel_v2 returns (success, liked)", test_like_tuple)


# 13.
def test_unlike_tuple():
    result = unlike_reel(1, 1)
    assert isinstance(result, tuple) and len(result) == 2
test("unlike_reel returns (success, liked)", test_unlike_tuple)


# 14.
def test_save_tuple():
    result = save_reel(1, 1)
    assert isinstance(result, tuple) and len(result) == 2
    result2 = unsave_reel(1, 1)
    assert isinstance(result2, tuple) and len(result2) == 2
test("save/unsave_reel return (success, saved)", test_save_tuple)


# 15.
def test_share_bool():
    with mock.patch("services.reels_engine._emit_reel_activity", return_value=None):
        with mock.patch("services.reels_engine._notify_creator", return_value=None):
            assert share_reel_v2(1, 1) == True
test("share_reel_v2 returns True", test_share_bool)


print()
print(f"Results: {tests_passed} passed, {tests_failed} failed")
if tests_failed:
    sys.exit(1)
