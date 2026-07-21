#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.discovery_service import get_discovery_data, search_profiles


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"{status}: {label}" + (f" -- {detail}" if detail and not ok else ""))
    return ok


def main() -> int:
    viewer_id = "11111111-1111-1111-1111-111111111111"
    blocked_id = "44444444-4444-4444-4444-444444444444"
    blocked_by_id = "55555555-5555-5555-5555-555555555555"
    friend_id = "22222222-2222-2222-2222-222222222222"
    follower_id = "33333333-3333-3333-3333-333333333333"
    eligible_ids = [
        friend_id,
        follower_id,
        "66666666-6666-6666-6666-666666666666",
        "77777777-7777-7777-7777-777777777777",
        "88888888-8888-8888-8888-888888888888",
        "99999999-9999-9999-9999-999999999999",
    ]

    candidates = [
        {"id": viewer_id, "username": "viewer", "display_name": "Viewer", "created_at": "2026-07-01T00:00:00+00:00", "is_public": True},
        {"id": blocked_id, "username": "blocked", "display_name": "Blocked", "created_at": "2026-07-02T00:00:00+00:00", "is_public": True},
        {"id": friend_id, "username": "friend", "display_name": "Friend", "created_at": "2026-07-03T00:00:00+00:00", "is_public": True},
        {"id": follower_id, "username": "follower", "display_name": "Follower", "created_at": "2026-07-04T00:00:00+00:00", "is_public": True},
        {"id": "66666666-6666-6666-6666-666666666666", "username": "cand6", "display_name": "Cand 6", "created_at": "2026-07-05T00:00:00+00:00", "is_public": True},
        {"id": blocked_by_id, "username": "blocked-by", "display_name": "Blocked By", "created_at": "2026-07-06T00:00:00+00:00", "is_public": True},
        {"id": "77777777-7777-7777-7777-777777777777", "username": "cand7", "display_name": "Cand 7", "created_at": "2026-07-07T00:00:00+00:00", "is_public": True},
        {"id": "88888888-8888-8888-8888-888888888888", "username": "cand8", "display_name": "Cand 8", "created_at": "2026-07-08T00:00:00+00:00", "is_public": True},
        {"id": "99999999-9999-9999-9999-999999999999", "username": "cand9", "display_name": "Cand 9", "created_at": "2026-07-09T00:00:00+00:00", "is_public": True},
    ]
    search_candidates = [
        {"id": "aaaaaaa1-aaaa-aaaa-aaaa-aaaaaaaaaaa1", "username": "alpha", "display_name": "Alpha", "created_at": "2026-07-10T00:00:00+00:00", "is_public": True},
        {"id": "aaaaaaa2-aaaa-aaaa-aaaa-aaaaaaaaaaa2", "username": "alpha2", "display_name": "Alpha 2", "created_at": "2026-07-11T00:00:00+00:00", "is_public": True},
        {"id": viewer_id, "username": "viewer", "display_name": "Viewer", "created_at": "2026-07-12T00:00:00+00:00", "is_public": True},
    ]

    counts = {
        "candidate_queries": 0,
        "viewer_queries": 0,
        "relationship_calls": 0,
    }
    relationship_payloads = {
        friend_id: {"is_friend": True, "relationship": "friend", "can_view_full_profile": True},
        follower_id: {"is_following": True, "relationship": "follower", "can_view_full_profile": True},
        "66666666-6666-6666-6666-666666666666": {"relationship": "none", "can_view_full_profile": True},
        "77777777-7777-7777-7777-777777777777": {"relationship": "none", "can_view_full_profile": True},
        "88888888-8888-8888-8888-888888888888": {"relationship": "none", "can_view_full_profile": True},
        "99999999-9999-9999-9999-999999999999": {"relationship": "none", "can_view_full_profile": True},
        blocked_id: {"blocked": True, "relationship": "blocked", "can_view_full_profile": False},
        blocked_by_id: {"blocked": True, "relationship": "blocked", "can_view_full_profile": False},
    }

    def fake_fast_query(sql, params=None, timeout_ms=None, default=None):
        sql_text = str(sql)
        params = list(params or [])
        if "FROM chain_profiles WHERE id = %s AND deleted_at IS NULL LIMIT 1" in sql_text:
            counts["viewer_queries"] += 1
            return [candidates[0]]
        if "FROM chain_profiles" in sql_text and "ORDER BY COALESCE(is_premium, FALSE) DESC, created_at DESC, chain_profiles.id DESC" in sql_text:
            if "LOWER(username) LIKE LOWER(%s)" in sql_text:
                pool = search_candidates
            else:
                pool = candidates
            if "LIMIT 1 OFFSET %s" in sql_text:
                offset = int(params[-1])
                return pool[offset:offset + 1]
            counts["candidate_queries"] += 1
            limit = int(params[-2])
            offset = int(params[-1])
            return pool[offset:offset + limit]
        if "FROM chain_presence" in sql_text:
            return []
        if "FROM chain_friends" in sql_text or "FROM chain_follows" in sql_text or "FROM chain_friend_requests" in sql_text:
            return []
        return default or []

    def fake_relationships(viewer_id_arg, target_ids):
        counts["relationship_calls"] += 1
        result = {}
        for tid in target_ids:
            payload = relationship_payloads.get(str(tid), {"relationship": "none", "can_view_full_profile": True})
            result[str(tid)] = {
                "is_self": str(tid) == viewer_id_arg,
                "is_friend": bool(payload.get("is_friend")),
                "friend_request_sent": False,
                "friend_request_received": False,
                "is_following": bool(payload.get("is_following")),
                "follow_request_sent": False,
                "follow_request_received": False,
                "blocked": bool(payload.get("blocked")),
                "relationship": payload.get("relationship", "none"),
            }
        return result

    with patch("services.discovery_service.fast_query", side_effect=fake_fast_query), \
         patch("services.discovery_service.get_many_relationship_states", side_effect=fake_relationships):
        page1 = get_discovery_data("members", viewer_id=viewer_id, limit=3, offset=0)
        page2 = get_discovery_data("members", viewer_id=viewer_id, limit=3, offset=3)
        page3 = get_discovery_data("members", viewer_id=viewer_id, limit=3, offset=6)
        search1 = search_profiles("alpha", viewer_id=viewer_id, limit=2, offset=0)

    ids = [item["id"] for item in page1["items"] + page2["items"] + page3["items"]]
    search_ids = [item["id"] for item in search1["items"]]

    ok = True
    ok &= check("viewer excluded", viewer_id not in ids, str(ids))
    ok &= check("blocked excluded", blocked_id not in ids and blocked_by_id not in ids, str(ids))
    ok &= check("three pages return each eligible user once", ids == eligible_ids, str(ids))
    ok &= check("stable ordering across pages", ids == eligible_ids, str(ids))
    ok &= check("no duplicates", len(ids) == len(set(ids)), str(ids))
    ok &= check("candidate query bounded", counts["candidate_queries"] == 4, str(counts))
    ok &= check("relationship states batched", counts["relationship_calls"] == 4, str(counts))
    ok &= check("viewer profile fetched once per call", counts["viewer_queries"] == 4, str(counts))
    ok &= check("search uses same batch-safe policy", viewer_id not in search_ids and len(search_ids) == 2, str(search_ids))
    ok &= check("search and discovery share batch policy", counts["relationship_calls"] == 4 and counts["candidate_queries"] == 4, str(counts))

    print("TEST_OK user discovery pagination contract" if ok else "TEST_FAIL user discovery pagination contract")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
