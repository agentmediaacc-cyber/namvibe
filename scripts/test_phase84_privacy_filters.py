#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
suggestions = (ROOT / "services/smart_suggestion_service.py").read_text()
video = (ROOT / "services/video_interest_service.py").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("suggestions use production content guard", "is_fake_content" in suggestions)
check("suggestions exclude self", "excluded = {str(viewer_profile_id)}" in suggestions)
check("suggestions exclude friends/follows/requests", "chain_friend_requests" in suggestions and "chain_follows" in suggestions)
check("suggestions use blocked filter", "is_blocked_any" in suggestions)
check("suggestions use social action policy", "get_primary_action" in suggestions)
check("suggestions hide disabled discovery", "allow_profile_discovery" in suggestions)
check("video ranking uses fake filter", "is_fake_content" in video and "filter_content" in video)
check("video ranking uses blocked filter", "is_blocked_any" in video)
check("video ranking uses privacy can_view_reels", "can_view_reels" in video)
check("video ranking excludes own content", "str(owner_id) == str(viewer_profile_id)" in video)
