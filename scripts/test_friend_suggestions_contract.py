#!/usr/bin/env python3
"""Contract checks for friend suggestion eligibility and filtering."""

import pathlib
import sys
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.friend_service import suggest_friends


def check(name, condition, details=""):
    if condition:
        print(f"OK   {name}")
        return True
    print(f"FAIL {name}{': ' + details if details else ''}")
    return False


def main():
    captured = {}

    def fake_fast_query(sql, params=None, **kwargs):
        captured["sql"] = sql
        captured["params"] = list(params or [])
        return [
            {
                "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "username": "real_friend_candidate",
                "display_name": "Real Candidate",
                "avatar_url": None,
                "is_verified": False,
                "followers_count": 13,
            }
        ]

    with patch("services.friend_service.fast_query", side_effect=fake_fast_query):
        rows = suggest_friends("viewer-1", limit=5)

    failures = 0
    failures += 0 if check("friend suggestions return real candidates", len(rows) == 1) else 1
    sql = captured.get("sql") or ""
    failures += 0 if check("friend suggestions exclude blocked users", "blocked_profile_id" in sql) else 1
    failures += 0 if check("friend suggestions exclude pending requests", "chain_friend_requests" in sql and "status = 'pending'" in sql) else 1
    failures += 0 if check("friend suggestions exclude current friends", "chain_friends" in sql) else 1
    failures += 0 if check("friend suggestions require public profiles", "COALESCE(is_public, TRUE) = TRUE" in sql) else 1
    failures += 0 if check("friend suggestions use public profile guard", "LOWER(COALESCE(chain_profiles.username" in sql) else 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
