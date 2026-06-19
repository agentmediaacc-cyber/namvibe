#!/usr/bin/env python3
"""Clear cache namespaces that may contain fake homepage/discover data."""

import argparse
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
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-notifications", action="store_true")
    args = parser.parse_args()

    patterns = list(PATTERNS)
    if args.include_notifications:
        patterns.append("notif:unread:*")

    try:
        from services.redis_service import get_redis
    except Exception as error:
        print(f"SKIP redis unavailable: {error}")
        return 0

    client = get_redis()
    if not client:
        print("SKIP redis unavailable")
        return 0

    deleted = 0
    for pattern in patterns:
        count = 0
        for key in client.scan_iter(match=pattern):
            client.delete(key)
            count += 1
        deleted += count
        print(f"{pattern}: deleted {count}")

    print(f"total_deleted={deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
