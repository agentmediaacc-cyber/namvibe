#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.reels_serialization_service import encode_feed_cursor, decode_feed_cursor


def check(name, cond, detail=""):
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}: {detail}")
        raise SystemExit(1)


cursor = encode_feed_cursor("2026-07-14T00:00:00Z", "reel-1")
check("cursor encoded", isinstance(cursor, str) and cursor, cursor)
decoded = decode_feed_cursor(cursor)
check("cursor decoded", decoded == {"created_at": "2026-07-14T00:00:00Z", "id": "reel-1"}, decoded)
check("malformed cursor", decode_feed_cursor("nope") is None, "should reject")
check("missing cursor", decode_feed_cursor("") is None, "should reject")
print("OK")
