#!/usr/bin/env python3
"""Contracts for lightweight public-profile negative caching and invalidation."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

import services.profile_service as profile_service


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("PASS" if condition else "FAIL"), name)
    if not condition:
        raise AssertionError(detail or name)


def reset_state() -> None:
    profile_service._PUBLIC_PROFILE_REF_MISS_CACHE.clear()


def main() -> None:
    reset_state()

    calls = []
    store = {}
    cached_rows = [{
        "id": "11111111-1111-1111-1111-111111111111",
        "username": "namvibe",
        "display_name": "NamVibe",
        "full_name": "NamVibe",
        "avatar_url": "https://cdn.example.com/a.jpg",
        "cover_url": None,
        "bio": "Public profile",
        "is_verified": True,
        "verified": True,
        "is_public": True,
        "visibility": "public",
        "deleted_at": None,
    }]

    def fake_fetch(sql_text, params, timeout_ms=1200):
        calls.append((sql_text, tuple(params), timeout_ms))
        return cached_rows[0]

    with patch.object(profile_service, "_fetch_public_profile_reference", side_effect=fake_fetch), \
         patch.object(profile_service, "get_cache", side_effect=lambda key, default=None: store.get(key, default)), \
         patch.object(profile_service, "set_cache", side_effect=lambda key, value, ttl=60: store.__setitem__(key, value) or value):
        first = profile_service.get_public_profile_reference(username="@NamVibe")
        second = profile_service.get_public_profile_reference(username="namvibe")

    check("canonical username lookup returns profile", first["id"] == cached_rows[0]["id"], first)
    check("canonical username shares cache key", second["id"] == cached_rows[0]["id"], second)
    check("canonical username executes one database lookup", len(calls) == 1, calls)

    reset_state()
    sql_calls = []

    with patch.object(profile_service, "_fetch_public_profile_reference", side_effect=AssertionError("SQL should not run")), \
         patch.object(profile_service, "set_cache", side_effect=lambda key, value, ttl=60: sql_calls.append((key, value, ttl)) or value):
        check("malformed identifier returns None", profile_service.get_public_profile_reference(username="!!!") is None)
        check("empty identifier returns None", profile_service.get_public_profile_reference(username="   ") is None)
        check("invalid UUID profile_id returns None", profile_service.get_public_profile_reference(profile_id="not-a-uuid") is None)

    check("malformed identifiers do not write cache", len(sql_calls) == 0, sql_calls)

    reset_state()
    miss_calls = []
    miss_store = {}

    def missing_fetch(sql_text, params, timeout_ms=1200):
        miss_calls.append((sql_text, tuple(params), timeout_ms))
        return None

    with patch.object(profile_service, "_fetch_public_profile_reference", side_effect=missing_fetch), \
         patch.object(profile_service, "get_cache", side_effect=lambda key, default=None: miss_store.get(key, default)), \
         patch.object(profile_service, "set_cache", side_effect=lambda key, value, ttl=60: miss_store.__setitem__(key, value) or value):
        miss_1 = profile_service.get_public_profile_reference(username="missing-handle")
        miss_2 = profile_service.get_public_profile_reference(username="@missing-handle")

    check("missing lookup returns None", miss_1 is None and miss_2 is None)
    check("repeated identical miss runs one lookup", len(miss_calls) == 1, miss_calls)

    reset_state()
    cache_writes = []

    with patch.object(profile_service, "_fetch_public_profile_reference", side_effect=RuntimeError("db down")), \
         patch.object(profile_service, "get_cache", return_value=None), \
         patch.object(profile_service, "set_cache", side_effect=lambda key, value, ttl=60: cache_writes.append((key, value, ttl)) or value):
        try:
            profile_service.get_public_profile_reference(username="down-handle")
        except RuntimeError:
            pass
        else:
            raise AssertionError("database exception should surface")

    check("database exception is not cached as a miss", len(cache_writes) == 0, cache_writes)

    reset_state()
    invalidations = []
    with patch.object(profile_service, "delete_cache", side_effect=lambda key: invalidations.append(key)), \
         patch.object(profile_service, "get_cache", return_value=None):
        profile_service.invalidate_public_profile_reference_cache(
            profile={
                "id": "22222222-2222-2222-2222-222222222222",
                "username": "NamVibe",
                "previous_username": "OldNamVibe",
            }
        )

    check("invalidation removes id key", any(":id:22222222-2222-2222-2222-222222222222" in key for key in invalidations), invalidations)
    check("invalidation removes current username key", any(":username:namvibe" in key for key in invalidations), invalidations)
    check("invalidation removes previous username key", any(":username:oldnamvibe" in key for key in invalidations), invalidations)

    reset_state()
    update_invalidations = []
    with patch.object(profile_service, "get_profile_by_id", return_value={"id": "33333333-3333-3333-3333-333333333333", "username": "OldName"}), \
         patch.object(profile_service, "_neon_update_profile", return_value={"id": "33333333-3333-3333-3333-333333333333", "username": "NewName"}), \
         patch.object(profile_service, "delete_cache", side_effect=lambda key: update_invalidations.append(key)):
        updated = profile_service.update_profile("33333333-3333-3333-3333-333333333333", {"username": "NewName"})

    check("update_profile returns updated row", updated and updated.get("username") == "NewName", updated)
    check("update_profile invalidates old username", any(":username:oldname" in key for key in update_invalidations), update_invalidations)
    check("update_profile invalidates new username", any(":username:newname" in key for key in update_invalidations), update_invalidations)

    print("TEST_OK profile negative cache contract")


if __name__ == "__main__":
    main()
