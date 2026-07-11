#!/usr/bin/env python3
import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

from services.ai import interaction_service as interactions
from services.ai import recommendation_service as recs


def check(name, condition):
    print(("PASS" if condition else "FAIL"), name)
    return 0 if condition else 1


failures = 0
for target in ["post", "reel", "profile"]:
    failures += check(f"target {target} valid", interactions.normalize_target_type(target) == target)
for action in ["view", "like", "block"]:
    failures += check(f"action {action} valid", interactions.normalize_action_type(action) == action)
try:
    interactions.normalize_target_type("bad")
    failures += check("invalid target rejected", False)
except ValueError:
    failures += check("invalid target rejected", True)
try:
    interactions.normalize_action_type("bad")
    failures += check("invalid action rejected", False)
except ValueError:
    failures += check("invalid action rejected", True)

failures += check("weight normalization bounded", interactions._bounded_weight("like", 999) == 20.0)
try:
    interactions.record_interactions_batch("p1", [{}] * 51)
    failures += check("batch max 50 enforced", False)
except ValueError:
    failures += check("batch max 50 enforced", True)

with patch("services.ai.recommendation_service.is_ai_feature_enabled", return_value=False):
    failures += check("recommendations disabled by default", recs.recommend_profiles("viewer") == [])

mock_profiles = [
    {"id": "viewer", "username": "self", "display_name": "Self"},
    {"id": "blocked", "username": "blocked", "display_name": "Blocked", "interests": ["music"], "region": "khomas"},
    {"id": "alpha", "username": "alpha", "display_name": "Alpha", "interests": ["music", "tech"], "region": "khomas", "town": "windhoek", "is_verified": True, "profile_completion": 80},
    {"id": "beta", "username": "beta", "display_name": "Beta", "interests": ["sports"], "region": "erongo", "town": "swakop", "profile_completion": 40},
]
with patch("services.ai.recommendation_service.is_ai_feature_enabled", return_value=True), \
     patch("services.ai.recommendation_service.cache_get", return_value=None), \
     patch("services.ai.recommendation_service.cache_set", return_value=True), \
     patch("services.ai.recommendation_service.fetch_all", return_value=mock_profiles), \
     patch("services.ai.recommendation_service.get_recommendation_context", return_value={
         "explicit_interests": ["music"],
         "inferred_interests": ["tech"],
         "region": "khomas",
         "town": "windhoek",
     }), \
     patch("services.ai.recommendation_service.get_recent_interactions", return_value=[]), \
     patch("services.ai.recommendation_service.is_blocked_any", side_effect=lambda viewer, other: other == "blocked"):
    ranked = recs.recommend_profiles("viewer", limit=100, offset=0)
    failures += check("self excluded from profile recommendations", all(item["target_id"] != "viewer" for item in ranked))
    failures += check("blocked users excluded", all(item["target_id"] != "blocked" for item in ranked))
    failures += check("limit capped at 50", len(ranked) <= 50)
    failures += check("stable deterministic ranking", [item["target_id"] for item in ranked] == [item["target_id"] for item in recs.recommend_profiles("viewer", limit=100, offset=0)])
    failures += check("no fake recommendation content", all(item["display"]["display_name"] in {"Alpha", "Beta"} for item in ranked))

with patch("services.ai.recommendation_service.is_ai_feature_enabled", return_value=True), \
     patch("services.ai.recommendation_service.cache_get", side_effect=RuntimeError("redis down")), \
     patch("services.ai.recommendation_service.fetch_all", side_effect=RuntimeError("db down")), \
     patch("services.ai.recommendation_service.get_recommendation_context", return_value={}), \
     patch("services.ai.recommendation_service.get_recent_interactions", return_value=[]), \
     patch("services.ai.recommendation_service.is_blocked_any", return_value=False):
    result = recs.recommend_posts("viewer")
    failures += check("db/redis failure safe fallback", result == [])

sys.exit(1 if failures else 0)
