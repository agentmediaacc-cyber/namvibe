from datetime import datetime, timezone

from psycopg2.extras import Json

from services.ai.feature_flags import is_ai_feature_enabled
from services.ai.privacy_guard import sanitize_metadata
from services.logging_service import log_warning
from services.neon_service import execute, fetch_all, table_exists
from services.redis_service import get_json, set_json
from services.id_validation import normalize_uuid


VALID_TARGET_TYPES = {
    "post", "reel", "story", "profile", "live", "marketplace",
    "event", "business", "dating_profile", "hashtag",
}
VALID_ACTION_TYPES = {
    "impression", "view", "open", "like", "unlike", "comment", "share", "save",
    "unsave", "follow", "unfollow", "friend_request", "friend_accept", "message",
    "call", "hide", "report", "block", "purchase", "join", "complete",
}
SAFE_METADATA_KEYS = {
    "playback_percent",
    "completion_percent",
    "media_type",
    "recommendation_request_id",
    "feed_position",
    "relationship_type",
}
ACTION_WEIGHTS = {
    "impression": 0.05,
    "view": 0.5,
    "open": 0.8,
    "like": 2,
    "unlike": -1,
    "comment": 3,
    "share": 4,
    "save": 4,
    "unsave": -2,
    "follow": 5,
    "unfollow": -3,
    "friend_request": 5,
    "friend_accept": 7,
    "message": 5,
    "call": 6,
    "hide": -5,
    "report": -10,
    "block": -12,
    "purchase": 8,
    "join": 5,
    "complete": 3,
}


def normalize_target_type(value):
    normalized = str(value or "").strip().lower()
    if normalized not in VALID_TARGET_TYPES:
        raise ValueError("invalid_target_type")
    return normalized


def normalize_action_type(value):
    normalized = str(value or "").strip().lower()
    if normalized not in VALID_ACTION_TYPES:
        raise ValueError("invalid_action_type")
    return normalized


def get_action_weight(action_type):
    return ACTION_WEIGHTS[normalize_action_type(action_type)]


def _bounded_weight(action_type, explicit_weight=None):
    default = get_action_weight(action_type)
    if explicit_weight is None:
        return default
    try:
        weight = float(explicit_weight)
    except (TypeError, ValueError):
        return default
    return max(-20.0, min(20.0, weight))


def _dedupe_impression_key(profile_id, target_type, target_id, source_surface):
    return f"ai:impression:{profile_id}:{target_type}:{target_id}:{source_surface or 'unknown'}"


def record_interaction(profile_id, target_type, target_id, action_type, source_surface=None, session_id=None, dwell_time_ms=None, metadata=None, action_weight=None):
    profile_id = normalize_uuid(profile_id)
    if not profile_id or not is_ai_feature_enabled("ai_interaction_tracking", profile_id=profile_id):
        return {"ok": False, "skipped": True}
    target_type = normalize_target_type(target_type)
    action_type = normalize_action_type(action_type)
    if action_type == "impression":
        key = _dedupe_impression_key(profile_id, target_type, target_id, source_surface)
        if get_json(key):
            return {"ok": True, "deduped": True}
        set_json(key, {"seen": True}, ttl=120)
    payload = sanitize_metadata(metadata or {})
    bounded_dwell = None
    if dwell_time_ms is not None:
        try:
            bounded_dwell = max(0, min(int(dwell_time_ms), 600000))
        except (TypeError, ValueError):
            bounded_dwell = None
    try:
        if table_exists("chain_ai_interactions"):
            execute(
                """
                INSERT INTO chain_ai_interactions
                    (profile_id, target_type, target_id, action_type, action_weight, source_surface, session_id, dwell_time_ms, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    profile_id,
                    target_type,
                    str(target_id)[:200],
                    action_type,
                    _bounded_weight(action_type, action_weight),
                    (source_surface or "")[:80] or None,
                    (session_id or "")[:120] or None,
                    bounded_dwell,
                    Json(payload),
                ),
                timeout_ms=2000,
            )
        if table_exists("chain_ai_user_profiles"):
            execute(
                """
                INSERT INTO chain_ai_user_profiles (profile_id, interaction_count, last_interaction_at)
                VALUES (%s, 1, now())
                ON CONFLICT (profile_id)
                DO UPDATE SET
                    interaction_count = chain_ai_user_profiles.interaction_count + 1,
                    last_interaction_at = now(),
                    updated_at = now()
                """,
                (profile_id,),
                timeout_ms=2000,
            )
        return {"ok": True}
    except Exception as error:
        log_warning("ai_record_interaction_failed", action_type=action_type, target_type=target_type, error=str(error)[:120])
        return {"ok": False, "error": "interaction_unavailable"}


def build_safe_metadata(metadata=None):
    if not isinstance(metadata, dict):
        return {}
    filtered = {}
    for key in SAFE_METADATA_KEYS:
        if key not in metadata:
            continue
        value = metadata.get(key)
        if value in (None, "", []):
            continue
        filtered[key] = value
    return sanitize_metadata(filtered)


def track_interaction_safe(profile_id, target_type, target_id, action_type, source_surface=None, session_id=None, dwell_time_ms=None, metadata=None, action_weight=None):
    try:
        return record_interaction(
            profile_id=profile_id,
            target_type=target_type,
            target_id=target_id,
            action_type=action_type,
            source_surface=source_surface,
            session_id=session_id,
            dwell_time_ms=dwell_time_ms,
            metadata=build_safe_metadata(metadata),
            action_weight=action_weight,
        )
    except Exception as error:
        log_warning("ai_track_interaction_safe_failed", action_type=action_type, target_type=target_type, error=str(error)[:120])
        return {"ok": False, "error": "interaction_unavailable"}


def record_interactions_batch(profile_id, interactions):
    items = list(interactions or [])
    if len(items) > 50:
        raise ValueError("batch_too_large")
    results = []
    for item in items:
        results.append(record_interaction(profile_id=profile_id, **item))
    return results


def get_recent_interactions(profile_id, limit=100):
    safe_limit = max(1, min(int(limit or 100), 100))
    profile_id = normalize_uuid(profile_id)
    if not profile_id or not table_exists("chain_ai_interactions"):
        return []
    try:
        return fetch_all(
            """
            SELECT profile_id, target_type, target_id, action_type, action_weight, source_surface, session_id, dwell_time_ms, metadata, created_at
            FROM chain_ai_interactions
            WHERE profile_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (profile_id, safe_limit),
            timeout_ms=2000,
        ) or []
    except Exception as error:
        log_warning("ai_recent_interactions_failed", error=str(error)[:120])
        return []


def summarize_user_interactions(profile_id):
    summary = {"total": 0, "last_interaction_at": None, "action_counts": {}, "top_targets": []}
    rows = get_recent_interactions(profile_id, limit=100)
    summary["total"] = len(rows)
    if rows:
        summary["last_interaction_at"] = rows[0].get("created_at")
    target_scores = {}
    for row in rows:
        action = row.get("action_type")
        summary["action_counts"][action] = summary["action_counts"].get(action, 0) + 1
        target_key = f"{row.get('target_type')}:{row.get('target_id')}"
        target_scores[target_key] = target_scores.get(target_key, 0) + float(row.get("action_weight") or 0)
    summary["top_targets"] = [
        {"target": key, "score": score}
        for key, score in sorted(target_scores.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]
    return summary
