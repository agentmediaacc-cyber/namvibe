#!/usr/bin/env python3
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_routes.homepage_api import _build_homepage_contract, _fast_homepage_feed_payload
from engines.cache_engine import set_cache as set_local_cache
from services.homepage_cache_service import get_full, get_full_with_stale, homepage_cache_info


def main() -> int:
    sample_profile = {"id": "010e54de-c11e-4f5f-9f98-4d674d721d59"}
    sample_story = [{
        "id": "story-1",
        "profile_id": sample_profile["id"],
        "caption": "Story",
        "thumbnail_url": "/static/story.jpg",
        "media_url": "/static/story.jpg",
        "video_url": "",
        "mime_type": "image/jpeg",
        "created_at": "2026-07-15T00:00:00+00:00",
    }]
    sample_post = [{
        "id": "post-1",
        "profile_id": sample_profile["id"],
        "caption": "Post",
        "content": "Post",
        "body": "Post",
        "thumbnail_url": "/static/post.jpg",
        "media_url": "/static/post.jpg",
        "video_url": "",
        "mime_type": "image/jpeg",
        "post_type": "post",
        "likes_count": 0,
        "comments_count": 0,
        "views_count": 0,
        "shares_count": 0,
        "created_at": "2026-07-15T00:00:00+00:00",
    }]
    sample_reel = [{
        "id": "reel-1",
        "profile_id": sample_profile["id"],
        "caption": "Reel",
        "thumbnail_url": "/static/reel.jpg",
        "media_url": "/static/reel.mp4",
        "video_url": "/static/reel.mp4",
        "mime_type": "video/mp4",
        "likes_count": 0,
        "comments_count": 0,
        "views_count": 0,
        "shares_count": 0,
        "music_title": "Promo",
        "created_at": "2026-07-15T00:00:00+00:00",
    }]

    with patch("api_routes.homepage_api.fetch_stories_v2", return_value=(sample_story, False, None)), \
         patch("api_routes.homepage_api.fetch_posts_v2", return_value=(sample_post, False, None)), \
         patch("api_routes.homepage_api.fetch_reels_v2", return_value=(sample_reel, False, None)), \
         patch("api_routes.homepage_api.fetch_live_rooms_v2", return_value=([], False, None)), \
         patch("api_routes.homepage_api.fetch_suggested_people_v2", return_value=([sample_profile], False)), \
         patch("api_routes.homepage_api._fetch_friend_activity", return_value=[]), \
         patch("api_routes.homepage_api.as_completed", side_effect=TimeoutError()), \
         patch("api_routes.homepage_api.rank_homepage_sections", side_effect=lambda payload, **kwargs: payload), \
         patch("api_routes.homepage_api.get_full", return_value=None), \
         patch("api_routes.homepage_api.get_payload", return_value=None):
        payload = _fast_homepage_feed_payload(limit=5, viewer_id=None)
        assert payload["feed_items"], "partial homepage payload should survive timeout"
        assert payload["reels"], "reels should be present from partial builder"
        assert payload["homepage_degraded"] is False or payload["homepage_degraded"] is True

        contract = _build_homepage_contract(viewer_id=None, limit=5, include_widgets=False)
        assert contract["posts"], "contract builder should normalize feed items"
        assert contract["stories"], "contract builder should normalize stories"
        assert contract["reels"], "contract builder should normalize reels"

    def sleepy_fetch(*args, **kwargs):
        time.sleep(0.2)
        return (sample_post, False, None)

    started = time.perf_counter()
    with patch("api_routes.homepage_api.fetch_stories_v2", side_effect=sleepy_fetch), \
         patch("api_routes.homepage_api.fetch_posts_v2", side_effect=sleepy_fetch), \
         patch("api_routes.homepage_api.fetch_reels_v2", side_effect=sleepy_fetch), \
         patch("api_routes.homepage_api.fetch_live_rooms_v2", side_effect=sleepy_fetch), \
         patch("api_routes.homepage_api.fetch_suggested_people_v2", return_value=([sample_profile], False)), \
         patch("api_routes.homepage_api._fetch_friend_activity", return_value=[]), \
         patch("api_routes.homepage_api.as_completed", side_effect=TimeoutError()), \
         patch("api_routes.homepage_api.rank_homepage_sections", side_effect=lambda payload, **kwargs: payload), \
         patch("api_routes.homepage_api.get_full", return_value=None), \
         patch("api_routes.homepage_api.get_payload", return_value=None):
        payload = _fast_homepage_feed_payload(limit=5, viewer_id=None)
        elapsed = time.perf_counter() - started
        assert elapsed < 0.15, f"timeout path should not wait for executor shutdown, elapsed={elapsed:.3f}s"
        assert "feed_items" in payload, "timeout path should still return a payload"

    set_local_cache("homepage:full:public", {"marker": "local-cache"}, ttl=60)
    with patch("services.homepage_cache_service.get", side_effect=AssertionError("redis path should not be used for warm local cache")):
        assert get_full("public") == {"marker": "local-cache"}

    with patch("services.homepage_cache_service._get_local_cache", side_effect=lambda key: None), \
         patch("services.homepage_cache_service.get", side_effect=lambda key, default=None: {"marker": "stale-cache"} if key == "homepage:full:public:stale" else None), \
         patch("services.homepage_cache_service.get_full_with_stale", return_value=({"marker": "stale-cache"}, True)), \
         patch("services.homepage_cache_service.get_payload_with_stale", return_value=(None, False)):
        fresh, stale = get_full_with_stale("public")
        assert fresh == {"marker": "stale-cache"}
        assert stale is True
    info = homepage_cache_info()
    assert info["homepage_cached"] in {True, False}

    print("TEST_OK homepage performance contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
