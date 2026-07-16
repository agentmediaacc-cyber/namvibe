#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.id_validation import normalize_uuid
import services.interest_engine as interest_engine
import services.recommendation_service as recommendation_service
import services.profile_service as profile_service


def main() -> int:
    calls = {"interest": 0, "recommend": 0, "profiles": 0}

    def fail_fast(*args, **kwargs):
        raise AssertionError("invalid uuid reached SQL")

    def capture_profile(sql, params=None, timeout_ms=None, default=None):
        calls["profiles"] += 1
        values = list(params or [])
        assert all(normalize_uuid(v) for v in values), values
        return [{"id": values[0], "username": "valid"}] if values else []

    original_interest = interest_engine.fast_query
    original_recommend = recommendation_service.fast_query
    original_profile = profile_service.fast_query
    original_following = recommendation_service._following_ids
    original_blocked = recommendation_service._blocked_ids
    original_hidden = recommendation_service._hidden_ids
    original_friend = recommendation_service._friend_ids
    original_viewer_location = recommendation_service._viewer_location
    original_interest_profile = recommendation_service.build_interest_profile

    try:
        interest_engine.fast_query = fail_fast
        recommendation_service.fast_query = fail_fast
        profile_service.fast_query = capture_profile
        recommendation_service._following_ids = lambda profile_id: (_ for _ in ()).throw(AssertionError("following query should be skipped"))
        recommendation_service._blocked_ids = lambda profile_id: (_ for _ in ()).throw(AssertionError("blocked query should be skipped"))
        recommendation_service._hidden_ids = lambda profile_id: (_ for _ in ()).throw(AssertionError("hidden query should be skipped"))
        recommendation_service._friend_ids = lambda profile_id: (_ for _ in ()).throw(AssertionError("friend query should be skipped"))
        recommendation_service._viewer_location = lambda profile_id: (_ for _ in ()).throw(AssertionError("viewer location query should be skipped"))
        recommendation_service.build_interest_profile = lambda profile_id: (_ for _ in ()).throw(AssertionError("interest build should be skipped"))

        assert interest_engine.build_interest_profile("viewer-1") == {}, "invalid viewer should be ignored"
        assert recommendation_service.score_feed_items("viewer-1", [{"id": "1", "profile_id": "2", "created_at": None}], feed_type="for_you"), "anonymous scoring should still succeed"

        valid_id = "11111111-1111-1111-1111-111111111111"
        result = profile_service.batch_get_profiles(["prof-1", valid_id, "", None, valid_id])
        assert calls["profiles"] == 1, calls
        assert valid_id in result, result
        assert "prof-1" not in result, result
    finally:
        interest_engine.fast_query = original_interest
        recommendation_service.fast_query = original_recommend
        profile_service.fast_query = original_profile
        recommendation_service._following_ids = original_following
        recommendation_service._blocked_ids = original_blocked
        recommendation_service._hidden_ids = original_hidden
        recommendation_service._friend_ids = original_friend
        recommendation_service._viewer_location = original_viewer_location
        recommendation_service.build_interest_profile = original_interest_profile

    print("TEST_OK feed uuid safety contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
