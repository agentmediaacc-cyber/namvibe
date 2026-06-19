#!/usr/bin/env python3
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.video_interest_service import POSITIVE_WEIGHTS, NEGATIVE_WEIGHTS, rank_reels_for_viewer, record_video_event


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("positive weights include engagement", POSITIVE_WEIGHTS["like"] > 0 and POSITIVE_WEIGHTS["save"] > POSITIVE_WEIGHTS["view"])
check("skip is negative", NEGATIVE_WEIGHTS["skip"] < 0)

with patch("services.video_interest_service.write_query", return_value=[]):
    res = record_video_event("viewer", "reel", "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "watch_3s", 3500)
check("record event ok", res["ok"])

events = [{"video_id": "reel1", "creator_profile_id": "creator1", "event_type": "like", "watch_ms": 12000}]
reels = [
    {"id": "reel1", "profile_id": "creator1", "username": "real", "caption": "real", "likes_count": 1, "views_count": 1},
    {"id": "reel2", "profile_id": "creator2", "username": "real2", "caption": "real", "likes_count": 0, "views_count": 1},
    {"id": "fake", "profile_id": "creator3", "username": "phase8_x", "caption": "Phase 8 production reel"},
]

with patch("services.video_interest_service.get_cache", return_value=None), \
     patch("services.video_interest_service.set_cache", return_value=True), \
     patch("services.video_interest_service.fast_query", return_value=events), \
     patch("services.video_interest_service.is_blocked_any", return_value=False), \
     patch("services.video_interest_service.can_view_reels", return_value=True):
    ranked = rank_reels_for_viewer("viewer", reels=reels, limit=5)

check("ranked reels returned", bool(ranked))
check("liked creator ranked first", ranked[0]["id"] == "reel1")
check("fake reels filtered", all(r["id"] != "fake" for r in ranked))
