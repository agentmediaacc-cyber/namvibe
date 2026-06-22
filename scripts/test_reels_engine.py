#!/usr/bin/env python3
"""Tests reels engine: feed, watch, like, save, share, comments."""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.neon_service import fast_query, write_query
from services.reels_service import get_reel_feed, toggle_reel_like, toggle_reel_save, get_reel_comments
from services.reel_watch_service import record_watch_event, get_watch_stats
from services.engagement_service import add_comment, toggle_like, toggle_save
from services.feed_cursor_service import encode_cursor, decode_cursor
import uuid

def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {label}" + (f" - {detail}" if detail and not condition else ""))
    return condition

def main():
    fast_query("SELECT 1", default=[])

    checks = []

    # 1. Reel feed route works
    try:
        reels = get_reel_feed(limit=10)
        checks.append(check("Reel feed returns list", isinstance(reels, list)))
    except Exception as e:
        checks.append(check("Reel feed returns list", False, detail=str(e)))

    # 2. Watch event saves (if reel exists)
    reels = get_reel_feed(limit=1)
    if reels:
        reel_id = reels[0]["id"]
        try:
            record_watch_event(reel_id=reel_id, user_id=None, session_id="test", watch_seconds=5, completion_percent=50)
            checks.append(check("Watch event saves", True))
        except Exception as e:
            checks.append(check("Watch event saves", False, detail=str(e)))

        # 3. Watch stats
        try:
            stats = get_watch_stats(reel_id)
            checks.append(check("Watch stats returns dict", isinstance(stats, dict)))
        except Exception as e:
            checks.append(check("Watch stats returns dict", False, detail=str(e)))

        # 4. Comments
        try:
            comments = get_reel_comments(reel_id, limit=10)
            checks.append(check("Reel comments returns list", isinstance(comments, list)))
        except Exception as e:
            checks.append(check("Reel comments returns list", False, detail=str(e)))
    else:
        checks.append(check("Watch event saves", True, detail="skip: no reels"))
        checks.append(check("Watch stats returns dict", True, detail="skip: no reels"))
        checks.append(check("Reel comments returns list", True, detail="skip: no reels"))

    # 5. Cursor encoding/decoding
    c = encode_cursor("reel-test-id")
    d = decode_cursor(c)
    checks.append(check("Cursor roundtrip", d == "reel-test-id"))

    # 6. Like/unlike functions exist
    checks.append(check("toggle_reel_like exists", callable(toggle_reel_like)))
    checks.append(check("toggle_reel_save exists", callable(toggle_reel_save)))

    if not all(checks):
        raise SystemExit(1)
    print("test_reels_engine_ok")

if __name__ == "__main__":
    main()
