from collections import Counter

from psycopg2.extras import Json

from services.ai.interaction_service import get_recent_interactions
from services.ai.privacy_guard import sanitize_metadata
from services.logging_service import log_warning
from services.neon_service import execute, fetch_one, fetch_all, get_cached_table_columns, table_exists
from services.profile_service import get_profile_by_id


def _listify(values, limit=20):
    if isinstance(values, str):
        values = [part.strip() for part in values.split(",") if part.strip()]
    values = values or []
    normalized = []
    for value in values[:limit]:
        text = str(value).strip().lower()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def get_or_create_ai_user_profile(profile_id):
    if not profile_id:
        return None
    if not table_exists("chain_ai_user_profiles"):
        return {
            "profile_id": profile_id,
            "inferred_interests": [],
            "explicit_interests": [],
            "preferred_languages": [],
            "preferred_content_types": [],
            "recommendation_settings": {},
            "safety_settings": {},
        }
    row = fetch_one("SELECT * FROM chain_ai_user_profiles WHERE profile_id = %s", (profile_id,), timeout_ms=2000)
    if row:
        return row
    profile = get_profile_by_id(profile_id) or {}
    execute(
        """
        INSERT INTO chain_ai_user_profiles (profile_id, region, town)
        VALUES (%s, %s, %s)
        ON CONFLICT (profile_id) DO NOTHING
        """,
        (profile_id, profile.get("region"), profile.get("town")),
        timeout_ms=2000,
    )
    return fetch_one("SELECT * FROM chain_ai_user_profiles WHERE profile_id = %s", (profile_id,), timeout_ms=2000)


def update_explicit_interests(profile_id, interests):
    cleaned = _listify(interests)
    execute(
        "UPDATE chain_ai_user_profiles SET explicit_interests = %s::jsonb, updated_at = now() WHERE profile_id = %s",
        (Json(cleaned), profile_id),
        timeout_ms=2000,
    )
    return cleaned


def update_language_preferences(profile_id, languages):
    cleaned = _listify(languages, limit=10)
    execute(
        "UPDATE chain_ai_user_profiles SET preferred_languages = %s::jsonb, updated_at = now() WHERE profile_id = %s",
        (Json(cleaned), profile_id),
        timeout_ms=2000,
    )
    return cleaned


def rebuild_inferred_interests(profile_id):
    interactions = get_recent_interactions(profile_id, limit=200)
    profile = get_profile_by_id(profile_id) or {}
    counter = Counter()
    counter.update(_listify(profile.get("interests"), limit=20))
    counter.update(_listify(profile.get("favorite_artists"), limit=10))
    counter.update(_listify(profile.get("favorite_games"), limit=10))
    counter.update(_listify(profile.get("favorite_songs"), limit=10))
    for row in interactions:
        target_type = row.get("target_type")
        if target_type:
            counter[target_type] += max(1, int(float(row.get("action_weight") or 0) > 0))
        metadata = sanitize_metadata(row.get("metadata") or {})
        counter.update(_listify(metadata.get("hashtags"), limit=10))
        counter.update(_listify(metadata.get("categories"), limit=10))
        counter.update(_listify(metadata.get("content_types"), limit=5))
    inferred = [name for name, _score in counter.most_common(20)]
    try:
        if table_exists("chain_ai_user_profiles"):
            execute(
                "UPDATE chain_ai_user_profiles SET inferred_interests = %s::jsonb, updated_at = now() WHERE profile_id = %s",
                (Json(inferred), profile_id),
                timeout_ms=2000,
            )
    except Exception as error:
        log_warning("ai_rebuild_inferred_interests_failed", error=str(error)[:120])
    return inferred


def get_recommendation_context(profile_id):
    ai_profile = get_or_create_ai_user_profile(profile_id) or {}
    profile = get_profile_by_id(profile_id) or {}
    if not ai_profile.get("inferred_interests"):
        ai_profile["inferred_interests"] = rebuild_inferred_interests(profile_id)
    return {
        "profile_id": profile_id,
        "region": ai_profile.get("region") or profile.get("region"),
        "town": ai_profile.get("town") or profile.get("town"),
        "explicit_interests": _listify(ai_profile.get("explicit_interests")),
        "inferred_interests": _listify(ai_profile.get("inferred_interests")),
        "preferred_languages": _listify(ai_profile.get("preferred_languages")),
        "preferred_content_types": _listify(ai_profile.get("preferred_content_types")),
        "recommendation_settings": ai_profile.get("recommendation_settings") or {},
    }
