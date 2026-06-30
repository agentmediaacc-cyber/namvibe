#!/usr/bin/env python3
"""Verify homepage feed ranking priorities and pagination stability."""

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("FLASK_ENV", "development")

from services.homepage_service import get_feed_tab, rank_homepage_sections


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"{status}: {label}{suffix}")
    return condition


def iso(hours_ago):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def test_rank_priorities():
    payload = {
        "live_rooms": [
            {
                "id": "live-1",
                "profile_id": "creator-live",
                "creator_name": "Host",
                "viewer_count": 180,
                "is_live": True,
                "watch_url": "/live/live-1",
                "created_at": iso(0.1),
            }
        ],
        "reels": [
            {
                "id": "reel-friend-new",
                "profile_id": "friend-1",
                "caption": "Fresh friend reel",
                "likes_count": 8,
                "comments_count": 2,
                "shares_count": 1,
                "views_count": 150,
                "created_at": iso(1),
            },
            {
                "id": "reel-public-old",
                "profile_id": "public-1",
                "caption": "Old unrelated reel",
                "likes_count": 120,
                "comments_count": 18,
                "shares_count": 9,
                "views_count": 3000,
                "created_at": iso(72),
            },
            {
                "id": "reel-friend-new",
                "profile_id": "friend-1",
                "caption": "Duplicate reel row",
                "likes_count": 8,
                "comments_count": 2,
                "shares_count": 1,
                "views_count": 150,
                "created_at": iso(1),
            },
        ],
        "stories": [
            {"id": "story-friend-1", "profile_id": "friend-1", "created_at": iso(2)},
            {"id": "story-public-1", "profile_id": "public-1", "created_at": iso(1)},
        ],
        "trending_posts": [
            {
                "id": "post-friend-1",
                "profile_id": "friend-1",
                "caption": "Friend post",
                "likes_count": 5,
                "comments_count": 1,
                "created_at": iso(3),
            },
            {
                "id": "post-public-1",
                "profile_id": "public-2",
                "caption": "Trending public post",
                "likes_count": 70,
                "comments_count": 14,
                "shares_count": 5,
                "created_at": iso(10),
            },
        ],
        "recommended_profiles": [
            {"id": "creator-verified", "display_name": "Verified Creator", "verified": True, "followers_count": 50000},
            {"id": "creator-plain", "display_name": "Plain Creator", "verified": False, "followers_count": 1200},
        ],
        "suggested_users": [
            {"id": "suggested-1", "display_name": "Suggested One", "followers_count": 400},
        ],
    }
    relationship_context = {
        "following_ids": {"friend-1"},
        "friend_ids": {"friend-1"},
        "creator_history": {"friend-1": 16.0},
        "video_history": {"reel-friend-new": 8.0},
    }

    with patch("services.homepage_service._homepage_relationship_context", return_value=relationship_context):
        ranked = rank_homepage_sections(payload, viewer_id="viewer-1", feed_limit=12)

    feed_ids = [item.get("id") for item in ranked.get("feed_items", [])]
    friend_reels = [item.get("id") for item in ranked.get("reels", [])]

    checks = [
        check("live appears first when active", feed_ids[:1] == ["live-1"], str(feed_ids[:3])),
        check(
            "new friend reel ranks above unrelated old reel",
            friend_reels.index("reel-friend-new") < friend_reels.index("reel-public-old"),
            str(friend_reels),
        ),
        check(
            "duplicates removed",
            len(feed_ids) == len(set(feed_ids)),
            str(feed_ids),
        ),
    ]
    return all(checks)


def test_pagination_still_works():
    page_rows = [{"id": f"post-{index}", "profile_id": f"creator-{index}", "caption": f"Post {index}"} for index in range(1, 7)]

    def fake_feed_for_you(profile_id=None, limit=20, offset=0):
        return page_rows[offset: offset + limit + 1]

    with patch("services.homepage_service._feed_for_you", side_effect=fake_feed_for_you), \
         patch("services.homepage_service.get_cache", return_value=None), \
         patch("services.homepage_service.set_cache"), \
         patch("services.homepage_real_data_guard.filter_feed_posts", side_effect=lambda items, *args, **kwargs: items):
        page1, has_more1 = get_feed_tab(profile_id="viewer-1", tab="for_you", page=1, limit=3)
        page2, has_more2 = get_feed_tab(profile_id="viewer-1", tab="for_you", page=2, limit=3)

    ids1 = [item.get("id") for item in page1]
    ids2 = [item.get("id") for item in page2]
    checks = [
        check("pagination first page size", len(ids1) == 3, str(ids1)),
        check("pagination second page size", len(ids2) == 3, str(ids2)),
        check("pagination pages do not duplicate", not set(ids1).intersection(ids2), f"{ids1} vs {ids2}"),
        check("pagination has_more page1", has_more1 is True, str(has_more1)),
        check("pagination has_more page2", has_more2 is True, str(has_more2)),
    ]
    return all(checks)


def main():
    ok = True
    ok = test_rank_priorities() and ok
    ok = test_pagination_still_works() and ok
    if not ok:
        raise SystemExit(1)
    print("test_homepage_feed_ranking_ok")


if __name__ == "__main__":
    main()
