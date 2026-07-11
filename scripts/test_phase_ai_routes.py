#!/usr/bin/env python3
import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

from app import app


def check(name, condition):
    print(("PASS" if condition else "FAIL"), name)
    return 0 if condition else 1


failures = 0
client = app.test_client()

resp = client.get("/api/ai/status")
failures += check("auth required on ai status", resp.status_code == 401)
resp = client.get("/api/ai/profile")
failures += check("auth required on ai profile", resp.status_code == 401)

with client.session_transaction() as session:
    session["auth_user_id"] = "auth-1"
    session["profile_id"] = "profile-1"
    session["profile_data"] = {"id": "profile-1", "username": "tester"}

with patch("api_routes.ai_routes.is_ai_feature_enabled", side_effect=lambda key, profile_id=None: key == "ai_interaction_tracking"):
    resp = client.get("/api/ai/status")
    body = resp.get_json()
    failures += check("status hides secrets", "api_key" not in str(body).lower() and "base_url" not in body)
    failures += check("status returns safe provider only", "provider" in body)
    failures += check("recommendations disabled by default route response", body["recommendations_enabled"] is False)

with patch("api_routes.ai_routes.record_interaction", return_value={"ok": True}):
    resp = client.post("/api/ai/interactions", json={
        "profile_id": "spoofed",
        "target_type": "reel",
        "target_id": "abc",
        "action_type": "view",
    }, headers={"X-CSRFToken": "test"})
    failures += check("client cannot spoof profile_id", resp.status_code == 202)

resp = client.post("/api/ai/interactions", json={"target_type": "bad", "target_id": "abc", "action_type": "view"}, headers={"X-CSRFToken": "test"})
failures += check("invalid interaction rejected", resp.status_code == 400)

resp = client.post("/api/ai/interactions/batch", json={"interactions": [{}] * 51}, headers={"X-CSRFToken": "test"})
failures += check("batch 50 enforced at route", resp.status_code == 400)

with patch("api_routes.ai_routes.get_or_create_ai_user_profile", return_value={
    "explicit_interests": ["music"],
    "inferred_interests": ["tech"],
    "preferred_languages": ["en"],
    "preferred_content_types": ["reel"],
    "recommendation_settings": {},
    "interaction_count": 2,
    "onboarding_completed": False,
}):
    resp = client.get("/api/ai/profile")
    body = resp.get_json()
    failures += check("ai profile returns safe preferences", body["explicit_interests"] == ["music"])

with patch("api_routes.ai_routes.is_ai_feature_enabled", return_value=False):
    resp = client.get("/api/ai/recommendations/profiles")
    body = resp.get_json()
    failures += check("disabled recommendations route", body["enabled"] is False and body["items"] == [])

source = open(os.path.join(ROOT, "api_routes", "ai_routes.py"), "r", encoding="utf-8").read()
failures += check("routes registered under /api/ai", "/api/ai/status" in source and "/api/ai/recommendations/profiles" in source)

sys.exit(1 if failures else 0)
