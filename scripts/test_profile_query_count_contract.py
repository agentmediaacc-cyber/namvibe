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
    profile = {"id": "44444444-4444-4444-4444-444444444444", "username": "viewer"}
    counter = {"count": 0}

    def fake_fast_query(sql, params=None, timeout_ms=None, default=None):
        counter["count"] += 1
        text = str(sql).lower()
        if "count(*)" in text and "chain_follows" in text:
            return [{"count": 3}]
        if "chain_live_rooms" in text:
            return []
        return []

    with patch.object(profile_service, "get_profile_by_id", return_value=profile), \
         patch.object(profile_service, "get_profile_by_username", return_value=profile), \
         patch.object(profile_service, "get_profile_stats", return_value={"posts": 1, "reels": 1}), \
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
        bundle = profile_service.get_profile_bundle(profile_id=profile["id"], viewer_id="55555555-5555-5555-5555-555555555555")

    check("bundle returned", bool(bundle), str(bundle))
    check("bounded query count", counter["count"] <= 2, counter)
    check("live room query did not use unsupported column", "host_profile_id" not in str(bundle).lower(), bundle)
    print("OK")


if __name__ == "__main__":
    main()
