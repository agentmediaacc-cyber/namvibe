#!/usr/bin/env python3
import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

from app import app


def check(name, condition, detail=""):
    print(("PASS" if condition else "FAIL"), name)
    if not condition:
        raise AssertionError(detail or name)


def main():
    client = app.test_client()
    cache = {"ai:status:profile-1": {"ai_enabled": True, "provider": "disabled", "interaction_tracking_enabled": True, "recommendations_enabled": False, "algorithm_version": "v1", "external_provider_enabled": False}}
    with client.session_transaction() as session:
        session["auth_user_id"] = "auth-1"
        session["profile_id"] = "profile-1"
        session["profile_data"] = {"id": "profile-1", "username": "tester"}
    with patch("api_routes.ai_routes.get_json", side_effect=lambda key, default=None: cache.get(key, default)), \
         patch("services.ai.feature_flags.table_exists", side_effect=AssertionError("schema introspection should not run")), \
         patch("services.profile_service.neon_table_exists", side_effect=AssertionError("profile schema introspection should not run")):
        resp = client.get("/api/ai/status")
        feed = client.get("/api/feed/check")

    check("ai status cache hit", resp.status_code == 200, resp.status_code)
    check("feed check fast", feed.status_code == 200, feed.status_code)
    print("OK")


if __name__ == "__main__":
    main()
