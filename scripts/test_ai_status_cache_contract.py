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
    cache = {}
    calls = {"feature": 0}

    def fake_get_json(key, default=None):
        return cache.get(key, default)

    def fake_set_json(key, value, ttl=60, require_shared=True):
        cache[key] = dict(value)
        return {"success": True, "backend": "redis_local", "shared": True, "persistent": True, "value": value}

    def fake_feature_enabled(feature_key, profile_id=None):
        calls["feature"] += 1
        return feature_key == "ai_interaction_tracking"

    with client.session_transaction() as session:
        session["auth_user_id"] = "auth-1"
        session["profile_id"] = "profile-1"
        session["profile_data"] = {"id": "profile-1", "username": "tester"}

    with patch("api_routes.ai_routes.get_json", side_effect=fake_get_json), \
         patch("api_routes.ai_routes.set_json", side_effect=fake_set_json), \
         patch("api_routes.ai_routes.get_ai_config", return_value=type("Cfg", (), {
             "enabled": True,
             "external_calls_enabled": False,
             "provider": "disabled",
             "recommendation_version": "v1",
             "cache_ttl_seconds": 60,
         })()), \
         patch("api_routes.ai_routes.is_ai_feature_enabled", side_effect=fake_feature_enabled):
        first = client.get("/api/ai/status")
        second = client.get("/api/ai/status")

    body1 = first.get_json()
    body2 = second.get_json()
    check("first ai status ok", first.status_code == 200 and body1["ai_enabled"] is True, body1)
    check("second ai status ok", second.status_code == 200 and body2["provider"] == "disabled", body2)
    check("cache hit on second request", calls["feature"] == 2, calls)
    check("cached payload reused", body1 == body2, (body1, body2))
    print("OK")


if __name__ == "__main__":
    main()
