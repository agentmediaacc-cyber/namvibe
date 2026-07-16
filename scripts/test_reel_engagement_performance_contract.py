#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.engagement_service import add_comment, toggle_like, toggle_save


def main() -> int:
    profile_id = "010e54de-c11e-4f5f-9f98-4d674d721d59"
    reel_id = "9f2f6b59-70ec-5870-9595-eaab42c354c1"

    with patch("services.engagement_service._owner_for", return_value="other-owner"), \
         patch("services.engagement_service._table_available", return_value=True), \
         patch("services.engagement_service.neon_service.insert_row", return_value={"id": "c1", "profile_id": profile_id, "reel_id": reel_id, "body": "hello", "created_at": "2026-07-15T00:00:00+00:00"}) as insert_row_mock, \
         patch("services.engagement_service.fast_query", return_value=[{"count": 1}]) as fast_query_mock, \
         patch("services.engagement_service._notify_async") as notify_async_mock:
        result = add_comment(profile_id, "reel", reel_id, "hello")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["comment"]["id"] == "c1"
        assert insert_row_mock.call_count == 1
        assert fast_query_mock.call_count >= 1
        assert notify_async_mock.call_count == 1

    with patch("services.engagement_service._owner_for", return_value="other-owner"), \
         patch("services.engagement_service._table_available", return_value=True), \
         patch("services.engagement_service.fast_query", return_value=[]), \
         patch("services.engagement_service.neon_service.insert_row", return_value={"id": "l1"}) as insert_like_mock, \
         patch("services.engagement_service.write_query", return_value={"rowcount": 1}) as write_query_mock:
        result = toggle_like(profile_id, "reel", reel_id)
        assert result["success"] is True
        assert insert_like_mock.call_count == 1
        assert write_query_mock.call_count == 0

    with patch("services.engagement_service._table_available", return_value=True), \
         patch("services.engagement_service.fast_query", return_value=[]), \
         patch("services.engagement_service.neon_service.insert_row", return_value={"id": "s1"}) as insert_save_mock, \
         patch("services.engagement_service.write_query", return_value={"rowcount": 1}) as write_query_mock:
        result = toggle_save(profile_id, "reel", reel_id)
        assert result["success"] is True
        assert insert_save_mock.call_count == 1
        assert write_query_mock.call_count == 0

    print("TEST_OK reel engagement performance contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
