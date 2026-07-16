from datetime import datetime, timezone
import uuid

from services.ai.config import get_ai_config
from services.ai.feature_flags import is_ai_feature_enabled
from services.ai.interaction_service import get_recent_interactions
from services.ai.user_profile_service import get_recommendation_context
from services.blocking_service import is_blocked_any
from services.logging_service import log_warning
from services.neon_service import fetch_all, execute, table_exists
from services.redis_service import cache_get, cache_set
from services.id_validation import normalize_uuid


MAX_LIMIT = 50


def _safe_limit(limit):
    try:
        return max(1, min(int(limit or 20), MAX_LIMIT))
    except (TypeError, ValueError):
        return 20


def _safe_offset(offset):
    try:
        return max(0, min(int(offset or 0), 500))
    except (TypeError, ValueError):
        return 0


def _cache_key(kind, profile_id, limit, offset):
    version = get_ai_config().recommendation_version
    return f"ai:recs:{version}:{kind}:{profile_id}:{limit}:{offset}"


def explain_score(score_components):
    reasons = []
    for key, value in score_components.items():
        if value <= 0:
            continue
        if key == "mutual_connections":
            reasons.append("mutual_connections")
        elif key == "same_region":
            reasons.append("same_region")
        elif key == "shared_interest":
            reasons.append("shared_interest")
        elif key == "recently_active":
            reasons.append("recently_active")
        elif key == "verified_creator":
            reasons.append("verified_creator")
        elif key == "fresh_content":
            reasons.append("fresh_content")
        elif key == "local_content":
            reasons.append("local_content")
        elif key == "trending":
            reasons.append("trending")
        elif key == "followed_creator":
            reasons.append("followed_creator")
        elif key == "exploration":
            reasons.append("exploration")
    return reasons[:5]


def score_candidate(profile_id, candidate, context):
    components = {}
    viewer_interests = set((context.get("explicit_interests") or []) + (context.get("inferred_interests") or []))
    candidate_interests = set(_as_list(candidate.get("interests")))
    shared = viewer_interests.intersection(candidate_interests)
    if shared:
        components["shared_interest"] = min(6.0, len(shared) * 2.0)
    if context.get("region") and str(candidate.get("region") or "").lower() == str(context.get("region")).lower():
        components["same_region"] = 3.0
    if context.get("town") and str(candidate.get("town") or "").lower() == str(context.get("town")).lower():
        components["local_content"] = 2.0
    if candidate.get("is_verified") or candidate.get("verified"):
        components["verified_creator"] = 1.5
    completeness = float(candidate.get("profile_completion") or candidate.get("completion_percentage") or 0)
    if completeness > 0:
        components["profile_complete"] = min(3.0, completeness / 40.0)
    score = round(sum(components.values()), 6)
    return score, components


def _as_list(value):
    if isinstance(value, str):
        return [part.strip().lower() for part in value.split(",") if part.strip()]
    return [str(item).strip().lower() for item in (value or []) if str(item).strip()]


def _viewer_negative_sets(profile_id):
    profile_id = normalize_uuid(profile_id)
    if not profile_id:
        return set(), set()
    hidden_ids = set()
    reported_ids = set()
    for row in get_recent_interactions(profile_id, limit=200):
        target = str(row.get("target_id") or "")
        if row.get("action_type") == "hide":
            hidden_ids.add(target)
        if row.get("action_type") in {"report", "block"}:
            reported_ids.add(target)
    return hidden_ids, reported_ids


def recommend_profiles(profile_id, limit=20, offset=0):
    safe_limit = _safe_limit(limit)
    safe_offset = _safe_offset(offset)
    profile_id = normalize_uuid(profile_id)
    if not is_ai_feature_enabled("ai_recommendations", profile_id=profile_id):
        return []
    cache_key = _cache_key("profiles", profile_id, safe_limit, safe_offset)
    try:
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
    except Exception as error:
        log_warning("ai_recommend_profiles_cache_read_failed", error=str(error)[:120])
    context = get_recommendation_context(profile_id)
    hidden_ids, reported_ids = _viewer_negative_sets(profile_id)
    try:
        rows = fetch_all(
            """
            SELECT
                p.id, p.username, p.display_name, p.full_name, p.avatar_url, p.bio,
                p.region, p.town, p.interests, p.is_verified, p.verified,
                p.profile_completion, p.completion_percentage, p.last_login_at, p.updated_at
            FROM chain_profiles p
            WHERE p.deleted_at IS NULL
              AND COALESCE(p.is_public, TRUE) = TRUE
              AND p.id <> %s
              AND NOT EXISTS (
                  SELECT 1 FROM chain_friends f
                  WHERE f.deleted_at IS NULL
                    AND f.status = 'friend'
                    AND ((f.profile_id_1 = %s AND f.profile_id_2 = p.id) OR (f.profile_id_2 = %s AND f.profile_id_1 = p.id))
              )
            ORDER BY COALESCE(p.updated_at, p.created_at) DESC, p.id ASC
            LIMIT %s OFFSET %s
            """,
            (profile_id, profile_id, profile_id, max(safe_limit * 4, 40), safe_offset),
            timeout_ms=3000,
        ) or []
    except Exception as error:
        log_warning("ai_recommend_profiles_query_failed", error=str(error)[:120])
        return []
    items = []
    for row in rows:
        candidate_id = str(row.get("id") or "")
        if not candidate_id or candidate_id in hidden_ids or candidate_id in reported_ids:
            continue
        if is_blocked_any(profile_id, candidate_id):
            continue
        score, components = score_candidate(profile_id, row, context)
        if score <= 0:
            continue
        items.append({
            "target_type": "profile",
            "target_id": candidate_id,
            "score": score,
            "reason_codes": explain_score(components),
            "algorithm_version": get_ai_config().recommendation_version,
            "display": {
                "id": candidate_id,
                "username": row.get("username"),
                "display_name": row.get("display_name") or row.get("full_name") or row.get("username"),
                "avatar_url": row.get("avatar_url"),
                "bio": row.get("bio"),
                "region": row.get("region"),
                "town": row.get("town"),
                "is_verified": bool(row.get("is_verified") or row.get("verified")),
            },
        })
    items.sort(key=lambda item: (-item["score"], item["target_id"]))
    result = items[:safe_limit]
    try:
        cache_set(cache_key, result, ttl=min(get_ai_config().cache_ttl_seconds, 180))
    except Exception as error:
        log_warning("ai_recommend_profiles_cache_write_failed", error=str(error)[:120])
    return result


def _recommend_content_rows(profile_id, table_name, target_type, limit=20, offset=0):
    safe_limit = _safe_limit(limit)
    safe_offset = _safe_offset(offset)
    profile_id = normalize_uuid(profile_id)
    if not is_ai_feature_enabled("ai_recommendations", profile_id=profile_id):
        return []
    cache_key = _cache_key(target_type, profile_id, safe_limit, safe_offset)
    try:
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
    except Exception as error:
        log_warning("ai_recommend_content_cache_read_failed", target_type=target_type, error=str(error)[:120])
    context = get_recommendation_context(profile_id)
    hidden_ids, reported_ids = _viewer_negative_sets(profile_id)
    select_views = "views_count," if table_name in {"chain_reels", "chain_stories"} else ""
    try:
        profile_filter = "AND c.profile_id <> %s" if profile_id else ""
        params = [profile_id] if profile_id else []
        params.extend([max(safe_limit * 4, 40), safe_offset])
        rows = fetch_all(
            f"""
            SELECT
                c.id, c.profile_id, c.caption, c.created_at, c.likes_count, c.comments_count, c.shares_count,
                {select_views}
                p.username, p.display_name, p.avatar_url, p.region, p.town, p.interests, p.is_verified, p.verified
            FROM {table_name} c
            JOIN chain_profiles p ON p.id = c.profile_id
            WHERE c.deleted_at IS NULL
              AND p.deleted_at IS NULL
              AND COALESCE(p.is_public, TRUE) = TRUE
              {profile_filter}
            ORDER BY c.created_at DESC, c.id ASC
            LIMIT %s OFFSET %s
            """,
            tuple(params),
            timeout_ms=3000,
        ) or []
    except Exception as error:
        log_warning("ai_recommend_content_query_failed", target_type=target_type, error=str(error)[:120])
        return []
    items = []
    for row in rows:
        creator_id = str(row.get("profile_id") or "")
        item_id = str(row.get("id") or "")
        if item_id in hidden_ids or item_id in reported_ids or creator_id in reported_ids:
            continue
        if is_blocked_any(profile_id, creator_id):
            continue
        score, components = score_candidate(profile_id, row, context)
        recency_bonus = _freshness_bonus(row.get("created_at"))
        components["fresh_content"] = recency_bonus
        engagement = float(row.get("likes_count") or 0) + float(row.get("comments_count") or 0) * 1.5 + float(row.get("shares_count") or 0) * 2.0
        if engagement > 0:
            components["trending"] = min(4.0, engagement / 10.0)
        components["exploration"] = _exploration_bonus(profile_id, item_id)
        total_score = round(score + sum(value for key, value in components.items() if key not in {"shared_interest", "same_region", "local_content", "verified_creator", "profile_complete"}), 6)
        items.append({
            "target_type": target_type,
            "target_id": item_id,
            "score": total_score,
            "reason_codes": explain_score(components),
            "algorithm_version": get_ai_config().recommendation_version,
            "display": {
                "id": item_id,
                "profile_id": creator_id,
                "caption": row.get("caption"),
                "created_at": row.get("created_at"),
                "username": row.get("username"),
                "display_name": row.get("display_name") or row.get("username"),
                "avatar_url": row.get("avatar_url"),
            },
        })
    items.sort(key=lambda item: (-item["score"], item["target_id"]))
    result = items[:safe_limit]
    try:
        cache_set(cache_key, result, ttl=min(get_ai_config().cache_ttl_seconds, 180))
    except Exception as error:
        log_warning("ai_recommend_content_cache_write_failed", target_type=target_type, error=str(error)[:120])
    return result


def _freshness_bonus(created_at):
    if not created_at:
        return 0.0
    if isinstance(created_at, datetime):
        dt = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    age_hours = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0)
    return max(0.0, 4.0 - min(age_hours / 12.0, 4.0))


def _exploration_bonus(profile_id, target_id):
    digest = uuid.uuid5(uuid.NAMESPACE_DNS, f"{profile_id}:{target_id}:{get_ai_config().recommendation_version}")
    return round((digest.int % 25) / 100.0, 2)


def recommend_posts(profile_id, limit=20, offset=0):
    return _recommend_content_rows(profile_id, "chain_posts", "post", limit=limit, offset=offset)


def recommend_reels(profile_id, limit=20, offset=0):
    return _recommend_content_rows(profile_id, "chain_reels", "reel", limit=limit, offset=offset)


def recommend_content(profile_id, content_type, limit=20, offset=0):
    if content_type == "post":
        return recommend_posts(profile_id, limit=limit, offset=offset)
    if content_type == "reel":
        return recommend_reels(profile_id, limit=limit, offset=offset)
    return []


def log_recommendation_impressions(profile_id, recommendation_type, items, request_id=None):
    if not table_exists("chain_ai_recommendation_events"):
        return False
    try:
        for item in list(items or [])[:50]:
            execute(
                """
                INSERT INTO chain_ai_recommendation_events
                    (profile_id, recommendation_type, target_type, target_id, score, reason_codes, algorithm_version, request_id)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (
                    profile_id,
                    recommendation_type,
                    item.get("target_type"),
                    item.get("target_id"),
                    float(item.get("score") or 0),
                    __import__("json").dumps(item.get("reason_codes") or []),
                    item.get("algorithm_version") or get_ai_config().recommendation_version,
                    request_id,
                ),
                timeout_ms=2000,
            )
        return True
    except Exception as error:
        log_warning("ai_recommendation_impression_log_failed", error=str(error)[:120])
        return False
