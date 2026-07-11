import hashlib

from services.ai.config import get_ai_config
from services.logging_service import log_warning
from services.neon_service import fetch_one, table_exists
from services.redis_service import get_json, set_json, delete_key


FEATURE_FLAG_CACHE_TTL = 30


def _cache_key(feature_key):
    return f"ai:feature_flag:{feature_key}"


def _stable_rollout(feature_key, profile_id):
    digest = hashlib.sha256(f"{feature_key}:{profile_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def _load_feature_flag(feature_key):
    cached = get_json(_cache_key(feature_key))
    if cached is not None:
        return cached
    if not table_exists("chain_ai_feature_flags"):
        return None
    row = fetch_one(
        "SELECT feature_key, enabled, rollout_percentage, configuration FROM chain_ai_feature_flags WHERE feature_key = %s",
        (feature_key,),
        timeout_ms=1500,
    )
    if row:
        set_json(_cache_key(feature_key), row, ttl=FEATURE_FLAG_CACHE_TTL)
    return row


def is_ai_feature_enabled(feature_key, profile_id=None):
    if feature_key == "ai_interaction_tracking":
        env_enabled = get_ai_config().interaction_tracking_enabled
    else:
        env_enabled = False
    try:
        row = _load_feature_flag(feature_key)
    except Exception as error:
        log_warning("ai_feature_flag_lookup_failed", feature_key=feature_key, error=str(error)[:120])
        return env_enabled if feature_key == "ai_interaction_tracking" else False
    if not row:
        return env_enabled if feature_key == "ai_interaction_tracking" else False
    if not bool(row.get("enabled")):
        return False
    rollout = max(0, min(100, int(row.get("rollout_percentage") or 0)))
    if rollout >= 100 or profile_id is None:
        return rollout > 0
    return _stable_rollout(feature_key, profile_id) < rollout


def get_ai_feature_configuration(feature_key):
    try:
        row = _load_feature_flag(feature_key)
    except Exception:
        return {}
    if not row:
        return {}
    return row.get("configuration") or {}


def invalidate_ai_feature_flag_cache(feature_key=None):
    if feature_key:
        delete_key(_cache_key(feature_key))
        return True
    return False
