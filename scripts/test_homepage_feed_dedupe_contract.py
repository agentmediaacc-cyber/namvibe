#!/usr/bin/env python3
"""Homepage feed dedupe contract for ranked feed items."""

import os
import sys
from copy import deepcopy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("FLASK_ENV", "development")

from services.homepage_service import rank_homepage_sections


def assert_true(expr, msg):
    if not expr:
        raise AssertionError(msg)


def main():
    payload = {
        "reels": [
            {"id": "reel-1", "profile_id": "creator-1", "caption": "A", "created_at": "2026-07-14T00:00:00+00:00"},
            {"id": "reel-1", "profile_id": "creator-1", "caption": "A dup", "created_at": "2026-07-14T00:00:00+00:00"},
            {"id": "uuid-2", "profile_id": "creator-2", "caption": "B", "created_at": "2026-07-13T00:00:00+00:00"},
        ],
        "trending_posts": [
            {"id": "post-1", "profile_id": "creator-3", "caption": "P", "created_at": "2026-07-12T00:00:00+00:00"},
            {"id": "post-1", "profile_id": "creator-3", "caption": "P dup", "created_at": "2026-07-12T00:00:00+00:00"},
        ],
        "live_rooms": [
            {"id": "live-1", "profile_id": "creator-4", "viewer_count": 9, "is_live": True, "created_at": "2026-07-14T00:00:00+00:00"},
            {"id": "live-1", "profile_id": "creator-4", "viewer_count": 9, "is_live": True, "created_at": "2026-07-14T00:00:00+00:00"},
        ],
        "recommended_profiles": [
            {"id": "creator-1", "display_name": "Creator 1", "verified": False},
            {"id": "creator-1", "display_name": "Creator 1 dup", "verified": False},
        ],
    }
    before = deepcopy(payload)
    ranked = rank_homepage_sections(payload, viewer_id="viewer-1", feed_limit=12)

    feed_items = ranked.get("feed_items", [])
    feed_ids = [item.get("id") for item in feed_items]
    feed_types = [item.get("type") or item.get("_section") for item in feed_items]

    assert_true(payload == before, "input payload should not be mutated")
    assert_true(feed_ids.count("reel-1") == 1, "duplicate reel IDs should be removed")
    assert_true(feed_ids.count("post-1") == 1, "duplicate post IDs should be removed")
    assert_true(feed_ids.count("live-1") == 1, "duplicate live IDs should be removed")
    assert_true(feed_ids.count("creator-1") == 1, "duplicate creator IDs should be removed")
    assert_true(feed_ids.index("reel-1") < len(feed_items), "preferred instance should remain")
    assert_true(len(feed_items) == len(set(feed_ids)), "final feed IDs should be unique")
    assert_true(any(kind in {"post", "trending_posts", "friend_posts"} for kind in feed_types), "expected posts in ranked feed")

    print("TEST_OK homepage feed dedupe contract")


if __name__ == "__main__":
    main()
