#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ["CHAIN_REDIS_ALLOW_LOCAL_FALLBACK"] = "1"
os.environ["REQUIRE_SHARED_CACHE"] = "1"


def main():
    from services.content_service import get_reels_content_version
    from services.reels_service import build_public_reels_feed_cache_key, get_reel_feed
    from services.redis_service import redis_manager

    version = get_reels_content_version("public")
    key = build_public_reels_feed_cache_key(content_version=version, limit=5, cursor=None, feed_type="public")
    cached = redis_manager.get_json_result(key)
    if not (cached.get("shared") and cached.get("value") is not None):
        raise SystemExit("shared cache not seeded")

    with patch("services.neon_service.fast_query", side_effect=AssertionError("fast_query should not run")), \
         patch("services.neon_service.fetch_one", side_effect=AssertionError("fetch_one should not run")), \
         patch("services.neon_service.fetch_all", side_effect=AssertionError("fetch_all should not run")), \
         patch("services.neon_service.write_query", side_effect=AssertionError("write_query should not run")):
        payload = get_reel_feed(limit=5, cursor=None, viewer_id=None)
        assert payload.get("items") is not None
        assert len(payload.get("items") or []) == len(cached["value"].get("items") or [])

    print("TEST_OK reels cached request zero db")


if __name__ == "__main__":
    main()
