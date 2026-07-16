#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app


INVALID_IDS = ["None", "null", "undefined", "not-a-uuid"]


def main() -> int:
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.test_client() as client:
        for bad_id in INVALID_IDS:
            with patch("services.reels_engine.get_reel", side_effect=AssertionError("get_reel should not run")), \
                 patch("services.profile_service.get_current_profile", side_effect=AssertionError("get_current_profile should not run")), \
                 patch("services.engagement_service.is_liked", side_effect=AssertionError("is_liked should not run")), \
                 patch("services.ai.interaction_service.track_interaction_safe", side_effect=AssertionError("track_interaction_safe should not run")):
                response = client.get(f"/reels/{bad_id}")
                assert response.status_code == 404, (bad_id, response.status_code, response.data[:200])
                body = response.get_data(as_text=True).lower()
                assert "invalid input syntax for type uuid" not in body
                assert "nodename" not in body

        with patch("services.reels_engine.get_reel", side_effect=AssertionError("get_reel should not run")), \
             patch("services.profile_service.get_current_profile", side_effect=AssertionError("get_current_profile should not run")):
            response = client.get("/reels/")
            assert response.status_code == 200, response.status_code
            body = response.get_data(as_text=True).lower()
            assert "/reels/none" not in body
            assert "invalid input syntax for type uuid" not in body

    print("TEST_OK reel invalid id contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
