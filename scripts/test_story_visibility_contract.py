#!/usr/bin/env python3
"""Contract checks for story visibility and expiry handling."""

import pathlib
import sys
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.stories_engine import get_story_feed


def check(name, condition, details=""):
    if condition:
        print(f"OK   {name}")
        return True
    print(f"FAIL {name}{': ' + details if details else ''}")
    return False


def main():
    active_story = {
        "id": "story-1",
        "profile_id": "creator-1",
        "caption": "Sunset over Windhoek",
        "media_url": "https://example.com/story.mp4",
        "thumbnail_url": "https://example.com/story.jpg",
        "media_type": "video",
        "visibility": "public",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "created_at": "2098-12-31T23:00:00+00:00",
        "updated_at": "2098-12-31T23:00:00+00:00",
        "background_color": None,
        "text_content": None,
        "music_title": None,
        "music_url": None,
        "location_name": None,
        "mentions": None,
        "hashtags": None,
        "link_url": None,
        "views_count": 0,
        "likes_count": 0,
        "reaction_count": 0,
        "reply_count": 0,
        "forward_count": 0,
        "back_count": 0,
        "exit_count": 0,
        "completion_rate": 100,
        "duration_seconds": 15,
        "display_name": "Creator One",
        "username": "creator_one",
        "avatar_url": None,
        "is_verified": False,
    }

    expired_story = dict(active_story, id="story-expired", expires_at="2000-01-01T00:00:00+00:00")

    def fake_fast_query(sql, params=None, **kwargs):
        sql = str(sql)
        if "FROM chain_follows" in sql:
            return []
        if "chain_story_close_friends" in sql or "chain_story_hidden_from" in sql or "chain_story_views" in sql:
            return []
        if "FROM chain_status_posts s" in sql and "s.expires_at >" in sql:
            return [active_story]
        if "FROM chain_status_posts s" in sql:
            return [expired_story]
        return []

    with patch("services.stories_engine.fast_query", side_effect=fake_fast_query):
        rows = get_story_feed(None, limit=10)

    failures = 0
    failures += 0 if check("active public story is returned", len(rows) == 1) else 1
    failures += 0 if check("story keeps media without avatar", rows and rows[0].get("media_url")) else 1
    failures += 0 if check("story keeps creator username", rows and rows[0].get("username") == "creator_one") else 1
    failures += 0 if check("expired story is not returned", all(r.get("id") != "story-expired" for r in rows)) else 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
