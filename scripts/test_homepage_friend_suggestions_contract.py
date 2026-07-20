#!/usr/bin/env python3
"""Homepage friend-suggestion contract checks."""

from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.homepage_service import get_homepage_suggested_users_section
from services.smart_suggestion_service import get_smart_suggestions, invalidate_suggestion_caches


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


def test_smart_suggestions_states():
    captured = {}

    def fake_fast_query(sql, params=None, timeout_ms=0, default=None):
        sql_text = str(sql)
        captured.setdefault("queries", []).append(sql_text)
        if "WHERE id = %s" in sql_text:
            return [{
                "id": "viewer-uuid",
                "town": "Windhoek",
                "region": "Khomas",
                "country": "Namibia",
            }]
        if "FROM chain_profiles" in sql_text:
            return [
                {"id": "friend-uuid", "username": "friend_one", "display_name": "Friend One", "followers_count": 11, "town": "Windhoek", "region": "Khomas", "country": "Namibia"},
                {"id": "requested-uuid", "username": "requested_one", "display_name": "Requested One", "followers_count": 7, "town": "Windhoek", "region": "Khomas", "country": "Namibia"},
                {"id": "following-uuid", "username": "following_one", "display_name": "Following One", "followers_count": 9, "town": "Windhoek", "region": "Khomas", "country": "Namibia"},
                {"id": "followback-uuid", "username": "followback_one", "display_name": "Follow Back", "followers_count": 6, "town": "Windhoek", "region": "Khomas", "country": "Namibia"},
                {"id": "accept-uuid", "username": "accept_one", "display_name": "Accept One", "followers_count": 8, "town": "Windhoek", "region": "Khomas", "country": "Namibia"},
                {"id": "friend-skip-uuid", "username": "friend_skip", "display_name": "Friend Skip", "followers_count": 4, "town": "Windhoek", "region": "Khomas", "country": "Namibia"},
            ]
        if "COUNT(*)" in sql_text or "mutual_count" in sql_text:
            return [
                {"candidate_id": "requested-uuid", "mutual_count": 2},
                {"candidate_id": "followback-uuid", "mutual_count": 1},
            ]
        if "chain_friends" in sql_text or "chain_friend_requests" in sql_text or "chain_follow_requests" in sql_text or "chain_follows" in sql_text:
            return []
        return default or []

    def fake_primary_action(viewer_id, row):
        mapping = {
            "requested-uuid": "requested",
            "following-uuid": "following",
            "followback-uuid": "approve_follow",
            "accept-uuid": "accept_request",
            "friend-skip-uuid": "friend_request",
        }
        return mapping.get(row.get("id"), "friend_request")

    def fake_rel_states(viewer_id, target_ids):
        return {
            "friend-skip-uuid": {"relationship": "friend", "is_friend": True},
            "requested-uuid": {"relationship": "none", "is_friend": False},
            "following-uuid": {"relationship": "none", "is_friend": False},
            "followback-uuid": {"relationship": "none", "is_friend": False},
            "accept-uuid": {"relationship": "none", "is_friend": False},
        }

    with patch("services.smart_suggestion_service.get_cache", return_value=None), \
         patch("services.smart_suggestion_service.set_cache", return_value=True), \
         patch("services.smart_suggestion_service.fast_query", side_effect=fake_fast_query), \
         patch("services.smart_suggestion_service.is_blocked_any", return_value=False), \
         patch("services.smart_suggestion_service.is_fake_content", return_value=False), \
         patch("services.smart_suggestion_service.get_primary_action", side_effect=fake_primary_action), \
         patch("services.smart_suggestion_service.get_many_relationship_states", side_effect=fake_rel_states):
        rows = get_smart_suggestions("viewer-uuid", limit=6)

    labels = {row["action_label"] for row in rows}
    check("smart suggestions include actionable labels", {"Add Friend", "Requested", "Following", "Follow Back", "Accept"}.issubset(labels))
    check("smart suggestions exclude accepted friends", all(row["primary_action"] != "friend" for row in rows))
    check("smart suggestions keep real profile ids", len({row["profile_id"] for row in rows}) == len(rows))
    check("smart suggestions keep reasons", all(row.get("reason") for row in rows))


def test_homepage_section_uses_smart_suggestions():
    with patch("services.smart_suggestion_service.get_smart_suggestions", return_value=[
        {
            "id": "candidate-1",
            "profile_id": "candidate-1",
            "username": "candidate_1",
            "display_name": "Candidate One",
            "avatar_url": "",
            "reason": "Followed by your friends",
            "mutual_count": 3,
            "primary_action": "friend_request",
            "action_kind": "friend",
            "action_label": "Add Friend",
            "action_disabled": False,
            "relationship_state": "none",
        }
    ]), patch("services.homepage_real_data_guard.filter_profiles", side_effect=lambda rows: rows):
        rows = get_homepage_suggested_users_section({"id": "viewer-uuid"}, limit=5)
    check("homepage suggestion section returns smart suggestions", rows and rows[0]["action_label"] == "Add Friend")


def test_invalidation_helper():
    calls = []
    with patch("services.smart_suggestion_service.invalidate_pattern", side_effect=lambda *parts: calls.append(parts) or 1):
        deleted = invalidate_suggestion_caches("viewer-uuid", "target-uuid")
    check("suggestion invalidation calls cache patterns", len(calls) >= 4)
    check("suggestion invalidation returns count", deleted == len(calls))


def main():
    test_smart_suggestions_states()
    test_homepage_section_uses_smart_suggestions()
    test_invalidation_helper()


if __name__ == "__main__":
    raise SystemExit(main())
