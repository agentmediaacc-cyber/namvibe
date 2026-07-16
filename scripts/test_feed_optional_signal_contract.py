#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import services.interest_engine as interest_engine
import services.recommendation_service as recommendation_service
import services.ai.user_profile_service as user_profile_service


def main() -> int:
    counters = {"interest": 0, "recommend": 0, "context": 0}

    def fail_fast(*args, **kwargs):
        raise AssertionError("optional signal query should be skipped")

    original_interest = interest_engine.fast_query
    original_recommend = recommendation_service.fast_query
    original_context = user_profile_service.fetch_one
    original_execute = user_profile_service.execute
    original_table_exists = user_profile_service.table_exists

    try:
        interest_engine.fast_query = fail_fast
        recommendation_service.fast_query = fail_fast
        user_profile_service.fetch_one = fail_fast
        user_profile_service.execute = fail_fast
        user_profile_service.table_exists = lambda table: False

        assert interest_engine.build_interest_profile("viewer-1") == {}, "invalid viewer should skip interest queries"
        assert user_profile_service.get_recommendation_context("viewer-1")["profile_id"] is None
        result = recommendation_service.score_feed_items("viewer-1", [{"id": "1", "profile_id": "2", "created_at": None}], feed_type="for_you")
        assert result and result[0]["id"] == "1", result
    finally:
        interest_engine.fast_query = original_interest
        recommendation_service.fast_query = original_recommend
        user_profile_service.fetch_one = original_context
        user_profile_service.execute = original_execute
        user_profile_service.table_exists = original_table_exists

    print("TEST_OK feed optional signal contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
