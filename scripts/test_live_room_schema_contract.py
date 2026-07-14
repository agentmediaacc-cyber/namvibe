#!/usr/bin/env python3
import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

from services import profile_service


def check(name, condition, detail=""):
    print(("PASS" if condition else "FAIL"), name)
    if not condition:
        raise AssertionError(detail or name)


def main():
    profile = {"id": "11111111-1111-1111-1111-111111111111", "username": "hosty"}
    queries = []

    def fake_fast_query(sql, params=None, timeout_ms=None, default=None):
        text = str(sql)
        queries.append(text)
        if "FROM chain_live_rooms" in text:
            return [{
                "id": "room-1",
                "owner_profile_id": profile["id"],
                "title": "Live Now",
                "category": "music",
                "is_live": True,
                "status": "live",
                "viewer_count": 7,
                "cover_url": "",
                "thumbnail_url": "",
                "created_at": "2026-07-14T00:00:00Z",
            }]
        return []

    with patch.object(profile_service, "get_profile_by_id", return_value=profile), \
         patch.object(profile_service, "get_profile_by_username", return_value=profile), \
         patch.object(profile_service, "get_profile_stats", return_value={"posts": 1, "reels": 1}), \
         patch.object(profile_service, "get_cached_table_columns", return_value=["id", "profile_id", "title", "category", "is_live", "status", "viewer_count", "cover_url", "thumbnail_url", "created_at"]), \
         patch.object(profile_service, "neon_table_exists", return_value=True), \
         patch.object(profile_service, "fast_query", side_effect=fake_fast_query), \
         patch("services.presence_service.get_presence", return_value={"state": "online"}), \
         patch("services.friend_service.get_mutual_friends", return_value={"count": 0, "items": []}), \
         patch("services.stories_engine.get_stories_by_creator", return_value=[]), \
         patch("services.stories_engine.get_highlights", return_value=[]), \
         patch.object(profile_service, "get_recently_active_friends", return_value=[]), \
         patch.object(profile_service, "get_wallet_snapshot", return_value={}), \
         patch.object(profile_service, "get_creator_tools", return_value={}), \
         patch("services.relationship_cache_service.get_relationship_state", return_value={}), \
         patch("services.relationship_gate_service.can_message", return_value=False):
        bundle = profile_service.get_profile_bundle(profile_id=profile["id"], viewer_id="22222222-2222-2222-2222-222222222222")

    check("bundle returned", bool(bundle), str(bundle))
    live_room_sql = "\n".join(queries)
    check("no host_profile_id in live room SQL", "host_profile_id" not in live_room_sql.lower(), live_room_sql)
    check("uses production column", "profile_id" in live_room_sql.lower(), live_room_sql)
    check("live room payload returned", bundle.get("content", {}).get("rooms"), bundle)
    print("OK")


if __name__ == "__main__":
    main()
