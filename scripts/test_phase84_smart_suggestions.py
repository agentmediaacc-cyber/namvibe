#!/usr/bin/env python3
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.smart_suggestion_service import get_smart_suggestions


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


def fake_query(sql, params=None, timeout_ms=0, default=None):
    if "WHERE id = %s" in sql:
        return [{"id": "viewer", "town": "Windhoek", "region": "Khomas", "country": "Namibia"}]
    if "chain_friends" in sql or "chain_friend_requests" in sql or "chain_follow_requests" in sql or "chain_follows" in sql:
        return []
    if "FROM chain_profiles" in sql:
        return [
            {"id": "creator1", "username": "real_creator", "display_name": "Real Creator", "town": "Windhoek", "region": "Khomas", "country": "Namibia", "is_creator": True, "profile_type": "creator", "profile_visibility": "public", "base_score": 42},
            {"id": "fake1", "username": "phase8_fake", "display_name": "Phase 8", "profile_visibility": "public", "base_score": 99},
            {"id": "person1", "username": "nearby_person", "display_name": "Nearby Person", "town": "Windhoek", "region": "Khomas", "country": "Namibia", "profile_visibility": "public", "base_score": 31},
        ]
    return []


with patch("services.smart_suggestion_service.get_cache", return_value=None), \
     patch("services.smart_suggestion_service.set_cache", return_value=True), \
     patch("services.smart_suggestion_service.fast_query", side_effect=fake_query), \
     patch("services.smart_suggestion_service.is_blocked_any", return_value=False), \
     patch("services.smart_suggestion_service.get_primary_action", side_effect=lambda viewer, row: "follow" if row.get("is_creator") else "friend_request"):
    suggestions = get_smart_suggestions("viewer", limit=5)

check("returns suggestions", bool(suggestions))
check("filters fake phase users", all("phase8" not in s["username"] for s in suggestions))
check("has profile id", all(s.get("profile_id") for s in suggestions))
check("has reason", all(s.get("reason") for s in suggestions))
check("has action type", all(s.get("action_type") in {"add_friend", "follow", "request_follow"} for s in suggestions))
check("has score", all("score" in s for s in suggestions))
check("same town reason present", any(s.get("reason") in {"Lives near you", "Creator you may like", "Same region"} for s in suggestions))
