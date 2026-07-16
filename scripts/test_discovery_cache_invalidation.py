#!/usr/bin/env python3
"""Contract checks for discovery suggestion cache reuse and invalidation."""

import pathlib
import sys
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.homepage_phase141_service import fetch_suggested_people_v2


def check(name, condition, details=""):
    if condition:
        print(f"OK   {name}")
        return True
    print(f"FAIL {name}{': ' + details if details else ''}")
    return False


def main():
    cache = {}
    query_calls = {"count": 0}

    def fake_get_cache(key):
        return cache.get(key)

    def fake_set_cache(key, value, ttl=0):
        cache[key] = value

    def fake_fast_query(sql, *args, **kwargs):
        query_calls["count"] += 1
        return [
            {
                "id": f"real-{query_calls['count']}",
                "username": f"real_user_{query_calls['count']}",
                "display_name": "Real User",
                "avatar_url": "",
                "is_verified": False,
                "followers_count": 5,
                "is_public": True,
            }
        ]

    with patch("services.homepage_phase141_service.get_cache", side_effect=fake_get_cache), \
         patch("services.homepage_phase141_service.set_cache", side_effect=fake_set_cache), \
         patch("services.homepage_phase141_service.fast_query", side_effect=fake_fast_query):
        first, cached_first = fetch_suggested_people_v2(
            ["id", "username", "display_name", "avatar_url", "is_verified", "followers_count", "is_public"],
            timeout_ms=50,
            limit=1,
        )
        second, cached_second = fetch_suggested_people_v2(
            ["id", "username", "display_name", "avatar_url", "is_verified", "followers_count", "is_public"],
            timeout_ms=50,
            limit=1,
        )
        cache.clear()
        third, cached_third = fetch_suggested_people_v2(
            ["id", "username", "display_name", "avatar_url", "is_verified", "followers_count", "is_public"],
            timeout_ms=50,
            limit=1,
        )

    failures = 0
    failures += 0 if check("first call populates cache", len(first) == 1 and not cached_first) else 1
    failures += 0 if check("second call uses cache", len(second) == 1 and cached_second) else 1
    failures += 0 if check("cache invalidation triggers reload", len(third) == 1 and not cached_third and query_calls["count"] >= 2) else 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
