#!/usr/bin/env python3
"""Tests story engagement: tray, views, reactions, replies, delete."""

import os, sys, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.neon_service import fast_query, write_query
from services.story_engagement_service import (
    get_tray, record_view, get_viewers, set_reaction,
    send_reply, delete_story, get_tray_for_story_page,
)

def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {label}" + (f" - {detail}" if detail and not condition else ""))
    return condition

def main():
    fast_query("SELECT 1", default=[])

    checks = []

    # 1. Tray with no profile returns empty
    try:
        tray = get_tray(None, limit=10)
        checks.append(check("Tray empty for anonymous", len(tray) == 0))
    except Exception as e:
        checks.append(check("Tray empty for anonymous", False, detail=str(e)))

    # 2. Tray with profile returns list (may be empty)
    try:
        rows = fast_query("SELECT id FROM chain_profiles WHERE deleted_at IS NULL LIMIT 1", default=[])
        if rows:
            pid = str(rows[0]["id"])
            tray = get_tray(pid, limit=10)
            checks.append(check("Tray returns list for user", isinstance(tray, list)))
        else:
            checks.append(check("Tray returns list for user", True, detail="skip: no profiles"))
    except Exception as e:
        checks.append(check("Tray returns list for user", False, detail=str(e)))

    # 3. Delete story with invalid id returns error
    result = delete_story("00000000-0000-0000-0000-000000000000", "00000000-0000-0000-0000-000000000000")
    checks.append(check("Delete invalid story returns error", not result.get("ok")))

    # 4. Delete story with valid id but wrong owner returns error
    try:
        rows = fast_query("SELECT id, profile_id FROM chain_status_posts WHERE deleted_at IS NULL AND expires_at > now() LIMIT 1", default=[])
        if rows:
            story_id = str(rows[0]["id"])
            wrong_owner = "00000000-0000-0000-0000-000000000000"
            result = delete_story(story_id, wrong_owner)
            checks.append(check("Non-owner cannot delete story", not result.get("ok")))
        else:
            checks.append(check("Non-owner cannot delete story", True, detail="skip: no active stories"))
    except Exception as e:
        checks.append(check("Non-owner cannot delete story", False, detail=str(e)))

    # 5. Record view on non-existent story doesn't crash
    try:
        record_view("00000000-0000-0000-0000-000000000000", "00000000-0000-0000-0000-000000000000")
        checks.append(check("Record view no crash", True))
    except Exception as e:
        checks.append(check("Record view no crash", False, detail=str(e)))

    # 6. Set reaction on non-existent story
    try:
        set_reaction("00000000-0000-0000-0000-000000000000", "00000000-0000-0000-0000-000000000000", "❤️")
        checks.append(check("Reaction no crash", True))
    except Exception as e:
        checks.append(check("Reaction no crash", False, detail=str(e)))

    # 7. Send reply to non-existent story
    try:
        result = send_reply("00000000-0000-0000-0000-000000000000", "00000000-0000-0000-0000-000000000000", "Hello")
        checks.append(check("Reply no crash", True))
    except Exception as e:
        checks.append(check("Reply no crash", False, detail=str(e)))

    # 8. Get viewers for non-existent story
    try:
        viewers = get_viewers("00000000-0000-0000-0000-000000000000")
        checks.append(check("Viewers returns list", isinstance(viewers, list)))
    except Exception as e:
        checks.append(check("Viewers returns list", False, detail=str(e)))

    if not all(checks):
        raise SystemExit(1)
    print("test_story_engagement_ok")

if __name__ == "__main__":
    main()
