#!/usr/bin/env python3
"""Clear homepage/discovery caches that may hold old fake rows."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PATTERNS = [
    "home:*",
    "homepage:*",
    "feed:*",
    "reels:*",
    "stories:*",
    "discover:*",
    "profile_bundle:*",
    "suggestions:*",
    "smart_suggestions:*",
    "smart_suggestions_v1:*",
    "video_interest:*",
    "for_you_reels_v1:*",
]


def main():
    try:
        from services.redis_service import get_redis
    except Exception as error:
        print(f"SKIP redis unavailable: {error}")
        return 0
    client = get_redis()
    if not client:
        print("SKIP redis unavailable")
        return 0
    total = 0
    for pattern in PATTERNS:
        count = 0
        for key in client.scan_iter(match=pattern):
            client.delete(key)
            count += 1
        total += count
        print(f"{pattern}: deleted {count}")
    print(f"phase85_clear_all_fake_caches: total_deleted={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
