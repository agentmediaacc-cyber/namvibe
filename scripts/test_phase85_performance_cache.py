#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
notifications = (ROOT / "services/notification_engine.py").read_text()
home_service = (ROOT / "services/homepage_service.py").read_text()
clear_cache = (ROOT / "scripts/phase85_clear_all_fake_caches.py").read_text()
suggestions = (ROOT / "services/smart_suggestion_service.py").read_text()
video = (ROOT / "services/video_interest_service.py").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("notification unread cache exists", "notif:unread:" in notifications and "cache_set" in notifications)
check("homepage timeouts exist", "future.result(timeout=" in home_service and "timeout_ms=" in home_service)
check("homepage limits exist", "_HOMEPAGE_LIMITS" in home_service and "LIMIT" in home_service)
check("smart suggestions cache", "_SUGGESTION_TTL_SECONDS = 60" in suggestions)
check("for you cache", "VIDEO_EVENT_TTL_SECONDS = 30" in video)
for pattern in ["home:*", "homepage:*", "feed:*", "reels:*", "stories:*", "discover:*", "profile_bundle:*", "suggestions:*", "smart_suggestions:*", "video_interest:*"]:
    check(f"cache clear includes {pattern}", pattern in clear_cache)
