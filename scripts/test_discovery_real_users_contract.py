#!/usr/bin/env python3
"""Contract checks for discovery/suggestion filtering on real users."""

import pathlib
import sys
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.homepage_real_data_guard import filter_profiles, is_test_profile, public_profile_sql
from services.homepage_phase141_service import fetch_suggested_people_v2


def check(name, condition, details=""):
    if condition:
        print(f"OK   {name}")
        return True
    print(f"FAIL {name}{': ' + details if details else ''}")
    return False


def main():
    failures = 0

    real_like = {"username": "alice_seedling", "display_name": "Alice Seedling", "email": "alice@example.com"}
    seeded = {"username": "seed_user", "display_name": "Seed User", "email": "seed_user@chain.local"}
    tester = {"username": "testuser_foo", "display_name": "Test User", "email": "testuser_foo@chain.local"}

    failures += 0 if check("real-like username survives guard", not is_test_profile(real_like)) else 1
    failures += 0 if check("seed user still filtered", is_test_profile(seeded)) else 1
    failures += 0 if check("testuser still filtered", is_test_profile(tester)) else 1
    failures += 0 if check("filter_profiles keeps real-like user", filter_profiles([real_like]) == [real_like]) else 1
    failures += 0 if check("public_profile_sql uses broad fake prefixes only", "seed_%%" in public_profile_sql("chain_profiles")) else 1

    captured = {}

    def fake_fast_query(sql, *args, **kwargs):
        captured["sql"] = sql
        return [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "username": "real_user",
                "display_name": "Real User",
                "avatar_url": None,
                "is_verified": False,
                "followers_count": 7,
                "is_public": True,
            },
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "username": "another_user",
                "display_name": "Another User",
                "avatar_url": "https://example.com/avatar.jpg",
                "is_verified": True,
                "followers_count": 11,
                "is_public": True,
            },
        ]

    with patch("services.homepage_phase141_service.fast_query", side_effect=fake_fast_query):
        rows, cached = fetch_suggested_people_v2(
            ["id", "username", "display_name", "avatar_url", "is_verified", "followers_count", "is_public"],
            timeout_ms=50,
            limit=2,
        )

    failures += 0 if check("suggested people returns real public users", len(rows) == 2) else 1
    failures += 0 if check("suggested people is not creator-only", "is_creator = TRUE" not in (captured.get("sql") or "")) else 1
    failures += 0 if check("suggested people query preserves public visibility", "COALESCE(is_public, TRUE) = TRUE" in (captured.get("sql") or "")) else 1
    failures += 0 if check("suggested people query still uses public profile guard", "public_profile_sql" not in (captured.get("sql") or "") and "LOWER(COALESCE(chain_profiles.username" in (captured.get("sql") or "")) else 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
