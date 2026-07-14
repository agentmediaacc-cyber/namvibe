from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.content_service import get_reels_content_version
from services.redis_service import redis_manager
from services.reels_service import get_reel_feed, build_public_reels_feed_cache_key


def main() -> int:
    version = get_reels_content_version("public")
    key = build_public_reels_feed_cache_key(content_version=version, limit=5, cursor="first", feed_type="public")
    payload = {"items": [{"id": str(uuid.uuid4()), "profile_id": str(uuid.uuid4())}], "next_cursor": None, "has_more": False}
    result = redis_manager.set_json_result(key, payload, ttl=30, require_shared=True)
    if result["shared"] is not True:
        print("SKIP shared Redis unavailable for zero-Neon proof")
        return 0
    assert redis_manager.get_json_result(key).get("value") == payload

    with patch("services.reels_service.fast_query", side_effect=AssertionError("Neon should not be queried on shared cache hit")):
        feed = get_reel_feed(limit=5, cursor=None, viewer_id=None)
    assert feed == payload
    redis_manager.delete(key)
    print("TEST_OK reels zero neon cache hit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
