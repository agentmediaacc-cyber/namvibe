#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.cache_engine import cache_key, delete_cache
from services.content_service import get_reels_content_version
from services.reels_service import get_reel_comments_page


def main() -> int:
    reel_id = "9f2f6b59-70ec-5870-9595-eaab42c354c1"
    page = {
        "items": [
            {"id": "c1", "body": "hello", "username": "alice", "avatar_url": "/a.jpg", "is_verified": True, "created_at": "2026-07-15T00:00:00+00:00"}
        ],
        "comments": [
            {"id": "c1", "body": "hello", "username": "alice", "avatar_url": "/a.jpg", "is_verified": True, "created_at": "2026-07-15T00:00:00+00:00"}
        ],
        "next_cursor": None,
        "has_more": False,
    }
    cache_key_str = cache_key("reels", "comments", reel_id, f"v{get_reels_content_version('public')}", "limit:20", "first")
    delete_cache(f"local:{cache_key_str}")

    with patch("services.reels_service.redis_manager") as redis_manager, \
         patch("services.reels_service.fast_query", side_effect=AssertionError("cache hit should skip DB")):
        redis_manager.get_json_result.return_value = {"shared": True, "value": page, "backend": "redis"}
        payload = get_reel_comments_page(reel_id, limit=20, cursor=None)
        assert payload == page

    delete_cache(f"local:{cache_key_str}")
    db_rows = [{"id": "c1", "body": "hello", "username": "alice", "avatar_url": "/a.jpg", "is_verified": True, "created_at": "2026-07-15T00:00:00+00:00"}]
    with patch("services.reels_service.redis_manager") as redis_manager, \
         patch("services.reels_service.fast_query", return_value=db_rows) as fast_query_mock:
        redis_manager.get_json_result.return_value = {"shared": False, "value": None, "backend": "redis"}
        payload = get_reel_comments_page(reel_id, limit=20, cursor=None)
        assert payload["comments"] == db_rows
        assert fast_query_mock.call_count == 1
        assert "JOIN chain_profiles" in str(fast_query_mock.call_args.args[0])

    with patch("services.reels_service.fast_query", side_effect=AssertionError("local cache hit should skip DB")):
        cached = get_reel_comments_page(reel_id, limit=20, cursor=None)
        assert cached == payload

    print("TEST_OK reel comments performance contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
