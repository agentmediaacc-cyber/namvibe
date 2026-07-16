#!/usr/bin/env python3
"""Homepage query-shape contract.

This contract keeps the public homepage builder on bounded SQL:
- no profile JOIN reappears in the section fetchers
- posts and reels keep explicit ORDER BY + LIMIT clauses
- the cold anonymous refresh can share one creator/profile batch
"""

from __future__ import annotations

import contextlib
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api_routes import homepage_api
from services import homepage_phase141_service as phase141


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _contains_all(text: str, *parts: str) -> bool:
    return all(part.lower() in text.lower() for part in parts)


def test_fetcher_sql_shapes() -> None:
    posts_cols = ["id", "profile_id", "caption", "media_url", "video_url", "likes_count", "comments_count", "created_at"]
    reels_cols = ["id", "profile_id", "caption", "thumbnail_url", "media_url", "video_url", "likes_count", "comments_count", "created_at"]

    sql_capture = []

    def fake_fast_query(sql_text, params=None, timeout_ms=0, default=None):
        sql_capture.append(" ".join(str(sql_text).split()))
        sql_norm = str(sql_text).lower()
        if "from chain_posts" in sql_norm:
            return [
                {
                    "id": "post-1",
                    "profile_id": "profile-a",
                    "caption": "A",
                    "media_url": "https://example.invalid/p.jpg",
                    "video_url": "",
                    "likes_count": 1,
                    "comments_count": 2,
                    "created_at": "2026-07-16T00:00:00Z",
                }
            ]
        if "from chain_reels" in sql_norm:
            return [
                {
                    "id": "reel-1",
                    "profile_id": "profile-a",
                    "caption": "B",
                    "thumbnail_url": "https://example.invalid/r.jpg",
                    "media_url": "https://example.invalid/r.mp4",
                    "video_url": "https://example.invalid/r.mp4",
                    "likes_count": 2,
                    "comments_count": 3,
                    "created_at": "2026-07-16T00:00:00Z",
                }
            ]
        if "from chain_profiles" in sql_norm:
            return [
                {"id": "profile-a", "username": "alpha", "display_name": "Alpha", "avatar_url": "/a.png"},
            ]
        return []

    with (
        patch.object(phase141, "fast_query", side_effect=fake_fast_query),
        patch.object(phase141, "get_cache", return_value=None),
        patch.object(phase141, "set_cache", return_value=None),
    ):
        posts, cache_hit, issue = phase141.fetch_posts_v2(posts_cols, timeout_ms=1200, limit=2, viewer_id=None, include_ads=False)
        reels, reel_cache_hit, reel_issue = phase141.fetch_reels_v2(reels_cols, timeout_ms=1000, limit=1, viewer_id=None)

    _assert(not cache_hit and not reel_cache_hit, "Expected raw DB fetches, not cache hits")
    _assert(len(sql_capture) >= 2, "Expected both fetcher SQL statements to execute")
    _assert(_contains_all(sql_capture[0], "from chain_posts", "where deleted_at is null", "order by created_at desc", "limit"), "Posts SQL shape regressed")
    _assert(_contains_all(sql_capture[1], "from chain_reels", "where deleted_at is null", "order by created_at desc", "limit"), "Reels SQL shape regressed")
    _assert("join chain_profiles" not in sql_capture[0].lower(), "Posts fetcher must not join profiles")
    _assert("join chain_profiles" not in sql_capture[1].lower(), "Reels fetcher must not join profiles")


def test_cold_refresh_shares_profile_batch() -> None:
    calls = []

    raw_posts = [
        {
            "id": "post-1",
            "profile_id": "profile-a",
            "caption": "A",
            "content": "A",
            "body": "A",
            "thumbnail_url": "",
            "media_url": "https://example.invalid/p.jpg",
            "video_url": "",
            "likes_count": 1,
            "comments_count": 1,
            "views_count": 2,
            "shares_count": 0,
            "created_at": "2026-07-16T00:00:00Z",
        }
    ]
    raw_reels = [
        {
            "id": "reel-1",
            "profile_id": "profile-b",
            "caption": "B",
            "thumbnail_url": "https://example.invalid/r.jpg",
            "media_url": "https://example.invalid/r.mp4",
            "video_url": "https://example.invalid/r.mp4",
            "likes_count": 2,
            "comments_count": 3,
            "views_count": 4,
            "shares_count": 1,
            "music_title": "Track",
            "created_at": "2026-07-16T00:00:00Z",
        }
    ]

    def fake_fetch_posts_v2(*args, **kwargs):
        _assert(kwargs.get("return_raw") is True, "Cold refresh should request raw posts")
        return raw_posts, False, None

    def fake_fetch_reels_v2(*args, **kwargs):
        _assert(kwargs.get("return_raw") is True, "Cold refresh should request raw reels")
        return raw_reels, False, None

    def fake_fetch_profiles_batch(profile_ids, timeout_ms=5000):
        calls.append(tuple(sorted(profile_ids)))
        return {
            "profile-a": {"id": "profile-a", "username": "alpha", "display_name": "Alpha", "avatar_url": "/a.png"},
            "profile-b": {"id": "profile-b", "username": "beta", "display_name": "Beta", "avatar_url": "/b.png"},
        }

    def fake_rank_homepage_sections(payload, viewer_id=None, feed_limit=20):
        return payload

    with (
        patch.object(homepage_api, "fetch_posts_v2", side_effect=fake_fetch_posts_v2),
        patch.object(homepage_api, "fetch_reels_v2", side_effect=fake_fetch_reels_v2),
        patch.object(homepage_api, "fetch_profiles_batch", side_effect=fake_fetch_profiles_batch),
        patch.object(homepage_api, "rank_homepage_sections", side_effect=fake_rank_homepage_sections),
    ):
        payload = homepage_api._fast_homepage_feed_payload(limit=20, viewer_id=None, cold_start=True)

    _assert(len(calls) == 1, f"Expected one shared profile batch, got {len(calls)}")
    _assert(calls[0] == ("profile-a", "profile-b"), f"Unexpected shared creator ids: {calls[0]}")
    _assert(payload.get("feed_items"), "Expected cold payload feed items")
    _assert(payload.get("reels"), "Expected cold payload reels")
    _assert(payload["feed_items"][0].get("display_name") == "Alpha", "Post creator hydration failed")
    _assert(payload["reels"][0].get("display_name") == "Beta", "Reel creator hydration failed")
    _assert(payload.get("homepage_degraded") is False, "Cold payload should remain non-degraded with real content")


def main() -> int:
    test_fetcher_sql_shapes()
    test_cold_refresh_shares_profile_batch()
    print("OK: homepage query shape and shared batch contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
