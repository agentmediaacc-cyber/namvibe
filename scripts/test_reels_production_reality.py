#!/usr/bin/env python3
"""Reels production reality checks for serializer + compatibility."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.reels_serialization_service import serialize_reel, serialize_reels

VIEWER_ID = "11111111-1111-1111-1111-111111111111"

def check(name, cond, detail=""):
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}: {detail}")
        raise SystemExit(1)


row = {
    "id": "reel-1",
    "profile_id": "11111111-1111-1111-1111-111111111111",
    "caption": "Hello",
    "video_url": "https://cdn.example/video.mp4",
    "thumbnail_url": "https://cdn.example/thumb.jpg",
    "duration_seconds": "12.5",
    "width": "720",
    "height": "1280",
    "visibility": "public",
    "created_at": "2026-07-14T00:00:00Z",
    "likes_count": "3",
    "comments_count": "2",
    "shares_count": "1",
    "saves_count": "4",
    "views_count": "5",
    "is_liked": "false",
    "is_saved": "1",
}

item = serialize_reel(row, creator={"username": "maya", "display_name": "Maya", "avatar_url": "/a.png", "is_verified": "true"})
check("canonical username", item["creator_username"] == "maya", item)
check("safe bool false", item["is_liked"] is False, item)
check("safe bool true", item["is_saved"] is True, item)
check("aspect ratio", round(item["aspect_ratio"], 3) == round(720 / 1280, 3), item)
check("profile url canonical", item["creator_url"].startswith("/profile/@maya"), item)

items = serialize_reels((r for r in [row]), viewer_id=VIEWER_ID)
check("generator input", len(items) == 1, items)
check("same payload", items[0]["id"] == "reel-1", items)

mixed = serialize_reels(
    (
        {
            "id": "reel-2",
            "profile_id": "22222222-2222-2222-2222-222222222222",
            "caption": "Hello 2",
            "video_url": "https://cdn.example/video2.mp4",
            "thumbnail_url": "https://cdn.example/thumb2.jpg",
            "created_at": "2026-07-14T00:00:00Z",
        },
    ),
    viewer_id=VIEWER_ID,
)
check("mixed valid uuid input", len(mixed) == 1, mixed)

print("OK")
