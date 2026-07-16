#!/usr/bin/env python3
"""Contract checks for Reel visibility inside homepage/discovery payloads."""

import pathlib
import sys
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.homepage_service import build_tiktok_home_payload


def check(name, condition, details=""):
    if condition:
        print(f"OK   {name}")
        return True
    print(f"FAIL {name}{': ' + details if details else ''}")
    return False


def main():
    reel_rows = {
        "items": [
            {
                "id": "reel-1",
                "profile_id": "creator-1",
                "username": "real_creator",
                "display_name": "Real Creator",
                "avatar_url": None,
                "is_verified": False,
                "caption": "Windhoek sunset",
                "video_url": "https://example.com/reel.mp4",
                "thumbnail_url": "https://example.com/reel.jpg",
                "likes_count": 12,
                "comments_count": 3,
                "views_count": 88,
                "created_at": "2099-01-01T00:00:00+00:00",
            }
        ]
    }

    def fake_get_reel_feed(limit=30):
        return reel_rows

    def fake_rank_reels_for_viewer(profile_id, reels=None, limit=30):
        return reels or []

    def fake_smart_suggestions(profile_id, limit=5):
        raise RuntimeError("force fallback")

    def fake_fallback_people(current_user=None, limit=5):
        return [
            {
                "id": "creator-2",
                "username": "real_user",
                "display_name": "Real User",
                "avatar_url": "",
                "is_verified": False,
            }
        ]

    with patch("services.reels_service.get_reel_feed", side_effect=fake_get_reel_feed), \
         patch("services.video_interest_service.rank_reels_for_viewer", side_effect=fake_rank_reels_for_viewer), \
         patch("services.smart_suggestion_service.get_smart_suggestions", side_effect=fake_smart_suggestions), \
         patch("services.homepage_service._suggested_people", side_effect=fake_fallback_people), \
         patch("services.homepage_service.fetch_popular_towns", return_value=[]):
        payload = build_tiktok_home_payload(exclude_test_content=True)

    failures = 0
    failures += 0 if check("homepage payload includes reel feed", len(payload.get("reels_feed") or []) == 1) else 1
    failures += 0 if check("homepage payload includes real reel video", payload.get("reels_feed", [])[0].get("video_url") == "https://example.com/reel.mp4") else 1
    failures += 0 if check("homepage payload includes fallback people", len(payload.get("suggested_creators") or []) == 1) else 1
    failures += 0 if check("homepage payload preserves non-creator suggestions", payload.get("suggested_creators", [])[0].get("username") == "real_user") else 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
