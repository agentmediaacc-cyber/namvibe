#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
suggestions = (ROOT / "services/smart_suggestion_service.py").read_text()
video = (ROOT / "services/video_interest_service.py").read_text()
schema = (ROOT / "scripts/phase84_video_events_schema.py").read_text()
home_service = (ROOT / "services/homepage_service.py").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("suggestions cache 60 seconds", "_SUGGESTION_TTL_SECONDS = 60" in suggestions and "set_cache" in suggestions)
check("for you reels cache 30 seconds", "VIDEO_EVENT_TTL_SECONDS = 30" in video and "set_cache" in video)
check("suggestions limit queries", "LIMIT %s" in suggestions and "limit * 8" in suggestions)
check("video events insert has timeout", "timeout_ms=700" in video)
check("homepage uses rank service", "rank_reels_for_viewer" in home_service)
check("homepage uses smart suggestions", "get_smart_suggestions" in home_service)
check("viewer index exists", "viewer_profile_id, created_at DESC" in schema)
check("video event index exists", "video_id, event_type, created_at DESC" in schema)
check("creator index exists", "creator_profile_id, created_at DESC" in schema)
