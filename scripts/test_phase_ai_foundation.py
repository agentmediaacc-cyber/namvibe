#!/usr/bin/env python3
import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"


def check(name, condition):
    print(("PASS" if condition else "FAIL"), name)
    return 0 if condition else 1


def read(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


failures = 0

for key in [
    "NAMVIBE_AI_ENABLED", "NAMVIBE_AI_PROVIDER", "NAMVIBE_AI_MODEL", "NAMVIBE_AI_API_KEY",
    "NAMVIBE_AI_BASE_URL", "NAMVIBE_AI_TIMEOUT_SECONDS", "NAMVIBE_AI_MAX_RETRIES",
    "NAMVIBE_AI_RECOMMENDATIONS_ENABLED", "NAMVIBE_AI_INTERACTION_TRACKING_ENABLED",
    "NAMVIBE_AI_EXTERNAL_CALLS_ENABLED", "NAMVIBE_AI_LOG_PROVIDER_USAGE",
    "NAMVIBE_AI_CACHE_TTL_SECONDS", "NAMVIBE_AI_RECOMMENDATION_VERSION",
]:
    os.environ.pop(key, None)

config_mod = importlib.import_module("services.ai.config")
cfg = config_mod.get_ai_config()
failures += check("config defaults external disabled", cfg.external_calls_enabled is False)
failures += check("config default provider disabled", cfg.provider == "disabled")
failures += check("config import safe without env", bool(cfg))
failures += check("timeout capped range", 1 <= cfg.timeout_seconds <= 30)
failures += check("retries capped range", 0 <= cfg.max_retries <= 3)

provider = importlib.import_module("services.ai.provider_factory").get_ai_provider()
health = provider.healthcheck()
failures += check("disabled provider health unavailable", health.get("available") is False)
try:
    provider.generate_text("hello")
    failures += check("disabled provider raises unavailable", False)
except Exception as exc:
    failures += check("disabled provider raises unavailable", exc.__class__.__name__ == "AIProviderUnavailable")

sql = read("sql/phase_ai_platform.sql")
for token in [
    "CREATE TABLE IF NOT EXISTS chain_ai_user_profiles",
    "CREATE TABLE IF NOT EXISTS chain_ai_interactions",
    "CREATE TABLE IF NOT EXISTS chain_ai_recommendation_events",
    "CREATE TABLE IF NOT EXISTS chain_ai_provider_usage",
    "CREATE TABLE IF NOT EXISTS chain_ai_feature_flags",
    "idx_chain_ai_interactions_profile_created_at",
    "idx_chain_ai_recommendation_events_profile_shown_at",
]:
    failures += check(token, token in sql)

env_example = read(".env.example")
failures += check(".env example has AI enabled flag", "NAMVIBE_AI_ENABLED=false" in env_example)
failures += check(".env example has external calls disabled", "NAMVIBE_AI_EXTERNAL_CALLS_ENABLED=false" in env_example)

app_source = read("app.py")
failures += check("app registers ai routes import", "from api_routes.ai_routes import ai_bp" in app_source)

sys.exit(1 if failures else 0)
