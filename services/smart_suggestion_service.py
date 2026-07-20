"""Smart, privacy-aware profile suggestions for homepage surfaces."""

from __future__ import annotations

import time
from typing import Dict, Iterable, List, Optional

from engines.cache_engine import cache_key, get_cache, set_cache
from services.homepage_real_data_guard import public_profile_sql
from services.neon_service import fast_query, get_cached_table_columns
from services.production_content_guard import is_fake_content
from services.relationship_cache_service import get_many_relationship_states
from services.relationship_privacy_service import is_blocked_any
from services.social_action_policy import get_account_kind, get_primary_action
from services.redis_service import invalidate_pattern


_SUGGESTION_TTL_SECONDS = 60

_ACTION_LABELS = {
    "friend_request": ("friend", "Add Friend", False),
    "request_sent": ("status", "Requested", True),
    "requested": ("status", "Requested", True),
    "accept_request": ("friend", "Accept", False),
    "follow": ("follow", "Follow", False),
    "request_follow": ("follow", "Request Follow", False),
    "following": ("follow", "Following", False),
    "approve_follow": ("follow", "Follow Back", False),
}

_LEGACY_ACTION_TYPES = {
    "friend_request": "add_friend",
    "accept_request": "add_friend",
    "request_sent": "request_follow",
    "requested": "request_follow",
    "follow": "follow",
    "request_follow": "request_follow",
    "following": "follow",
    "approve_follow": "follow",
}


def _profile_id(profile_or_id):
    if isinstance(profile_or_id, dict):
        return profile_or_id.get("id")
    return profile_or_id


def _safe_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _viewer_context(viewer_profile_id: Optional[str]) -> Dict:
    if not viewer_profile_id:
        return {}
    rows = fast_query(
        """
        SELECT id, username, town, region, country, current_country, current_location,
               bio, creator_category
        FROM chain_profiles
        WHERE id = %s AND deleted_at IS NULL
        LIMIT 1
        """,
        (viewer_profile_id,),
        timeout_ms=500,
        default=[],
    )
    return rows[0] if rows else {"id": viewer_profile_id}


def _exclude_ids(viewer_profile_id: Optional[str]) -> set:
    if not viewer_profile_id:
        return set()
    excluded = {str(viewer_profile_id)}
    queries = [
        (
            "SELECT CASE WHEN profile_id_1 = %s THEN profile_id_2 ELSE profile_id_1 END AS id "
            "FROM chain_friends WHERE (profile_id_1 = %s OR profile_id_2 = %s) AND status = 'friend' LIMIT 500",
            (viewer_profile_id, viewer_profile_id, viewer_profile_id),
        ),
        (
            "SELECT recipient_profile_id AS id FROM chain_friend_requests WHERE sender_profile_id = %s AND status = 'pending' LIMIT 500",
            (viewer_profile_id,),
        ),
        (
            "SELECT target_profile_id AS id FROM chain_follow_requests WHERE requester_profile_id = %s AND status = 'pending' LIMIT 500",
            (viewer_profile_id,),
        ),
        (
            "SELECT following_profile_id AS id FROM chain_follows WHERE follower_profile_id = %s LIMIT 1000",
            (viewer_profile_id,),
        ),
    ]
    for sql, params in queries:
        for row in fast_query(sql, params, timeout_ms=500, default=[]):
            if row.get("id"):
                excluded.add(str(row["id"]))
    return excluded


def _mutual_counts(viewer_profile_id: Optional[str], candidate_ids: Iterable[str]) -> Dict[str, int]:
    ids = [str(i) for i in candidate_ids if i]
    if not viewer_profile_id or not ids:
        return {}
    placeholders = ", ".join(["%s"] * len(ids))
    rows = fast_query(
        f"""
        WITH viewer_friends AS (
            SELECT CASE WHEN profile_id_1 = %s THEN profile_id_2 ELSE profile_id_1 END AS friend_id
            FROM chain_friends
            WHERE (profile_id_1 = %s OR profile_id_2 = %s) AND status = 'friend'
        ),
        candidate_friends AS (
            SELECT CASE WHEN profile_id_1 = ANY(%s::uuid[]) THEN profile_id_2 ELSE profile_id_1 END AS friend_id,
                   CASE WHEN profile_id_1 = ANY(%s::uuid[]) THEN profile_id_1 ELSE profile_id_2 END AS candidate_id
            FROM chain_friends
            WHERE (profile_id_1 IN ({placeholders}) OR profile_id_2 IN ({placeholders})) AND status = 'friend'
        )
        SELECT candidate_id::text AS candidate_id, COUNT(*) AS mutual_count
        FROM candidate_friends cf
        JOIN viewer_friends vf ON vf.friend_id = cf.friend_id
        GROUP BY candidate_id
        """,
        (viewer_profile_id, viewer_profile_id, viewer_profile_id, ids, ids, *ids, *ids),
        timeout_ms=700,
        default=[],
    )
    return {str(row["candidate_id"]): _safe_int(row.get("mutual_count")) for row in rows}


def _candidate_rows(viewer: Dict, limit: int) -> List[Dict]:
    town = viewer.get("town") or viewer.get("current_location")
    region = viewer.get("region")
    country = viewer.get("country") or viewer.get("current_country") or "Namibia"
    params = []
    score_parts = ["COALESCE(followers_count, 0) * 0.02"]
    where = ["deleted_at IS NULL", public_profile_sql("chain_profiles")]
    if town:
        score_parts.append("CASE WHEN LOWER(COALESCE(town, current_location, '')) = LOWER(%s) THEN 30 ELSE 0 END")
        params.append(town)
    if region:
        score_parts.append("CASE WHEN LOWER(COALESCE(region, '')) = LOWER(%s) THEN 20 ELSE 0 END")
        params.append(region)
    if country:
        score_parts.append("CASE WHEN LOWER(COALESCE(country, current_country, country_origin, '')) = LOWER(%s) THEN 12 ELSE 0 END")
        params.append(country)
    score_parts.append("CASE WHEN is_creator = TRUE OR profile_type IN ('creator','business','page','premium') THEN 8 ELSE 0 END")
    score_parts.append("CASE WHEN created_at > now() - interval '30 days' THEN 10 ELSE 0 END")
    try:
        profile_cols = set(get_cached_table_columns("chain_profiles", timeout_ms=2000) or [])
    except Exception:
        profile_cols = set()
    has_discovery = "allow_profile_discovery" in profile_cols
    columns = """
        id, username, display_name, full_name, avatar_url, thumbnail_url, town, region,
        country, current_country, current_location, bio, is_verified, verified,
        is_creator, creator_category, is_premium, profile_type, profile_visibility,
        followers_count, created_at
    """
    if has_discovery:
        columns += ", allow_profile_discovery"
    where_clause = " AND ".join(where)
    if has_discovery:
        where_clause += " AND COALESCE(allow_profile_discovery, TRUE) = TRUE"
    sql = f"""
        SELECT {columns}, ({' + '.join(score_parts)}) AS base_score
        FROM chain_profiles
        WHERE {where_clause}
        ORDER BY base_score DESC, created_at DESC NULLS LAST
        LIMIT %s
    """
    params.append(min(max(limit * 8, 30), 120))
    return fast_query(sql, tuple(params), timeout_ms=900, default=[])


def _reason(row: Dict, viewer: Dict, mutual_count: int) -> str:
    if mutual_count:
        return "Followed by your friends"
    if row.get("town") and (row.get("town") == viewer.get("town") or row.get("town") == viewer.get("current_location")):
        return "Lives near you"
    if row.get("region") and row.get("region") == viewer.get("region"):
        return "Same region"
    if row.get("is_creator") or row.get("profile_type") in {"creator", "business", "page", "premium"}:
        return "Creator you may like"
    if row.get("created_at") and "202" in str(row.get("created_at")):
        return "New on NamVibe"
    return "Popular in Namibia"


def _decorate_suggestion(row: Dict, viewer_profile_id: Optional[str], viewer: Dict, mutual_count: int) -> Optional[Dict]:
    pid = str(row.get("id") or "")
    if not pid:
        return None
    if is_fake_content(row):
        return None
    if viewer_profile_id and is_blocked_any(viewer_profile_id, pid):
        return None

    state = get_many_relationship_states(viewer_profile_id, [pid]).get(pid, {}) if viewer_profile_id else {}
    if state.get("is_friend") or state.get("relationship") == "friend":
        return None

    action_type = get_primary_action(viewer_profile_id, row)
    if action_type in {"none", "message", "blocked", "self"}:
        return None

    action_kind, action_label, action_disabled = _ACTION_LABELS.get(action_type, ("follow", "View profile", False))
    if action_type == "message":
        return None

    if action_label == "View profile":
        return None

    score = float(row.get("base_score") or 0) + (mutual_count * 12)
    return {
        "profile_id": pid,
        "id": pid,
        "username": row.get("username") or "",
        "display_name": row.get("display_name") or row.get("full_name") or row.get("username") or "NamVibe member",
        "avatar_url": row.get("avatar_url") or row.get("thumbnail_url") or "",
        "account_kind": get_account_kind(row),
        "reason": _reason(row, viewer, mutual_count),
        "mutual_count": mutual_count,
        "primary_action": action_type,
        "action_type": _LEGACY_ACTION_TYPES.get(action_type, "follow"),
        "action_kind": action_kind,
        "action_label": action_label,
        "action_disabled": action_disabled,
        "score": round(score, 2),
        "relationship_state": state.get("relationship", "none"),
    }


def invalidate_suggestion_caches(viewer_profile_id: Optional[str] = None, target_profile_id: Optional[str] = None) -> int:
    deleted = 0
    if viewer_profile_id:
        deleted += invalidate_pattern("cache", "smart_suggestions_v1", viewer_profile_id, "*")
        deleted += invalidate_pattern("cache", "smart_suggestions_v1", "*", viewer_profile_id)
        deleted += invalidate_pattern("cache", "suggested_people", str(viewer_profile_id))
    if target_profile_id:
        deleted += invalidate_pattern("cache", "smart_suggestions_v1", "*", target_profile_id)
        deleted += invalidate_pattern("cache", "smart_suggestions_v1", target_profile_id, "*")
        deleted += invalidate_pattern("cache", "suggested_people", str(target_profile_id))
    if not viewer_profile_id and not target_profile_id:
        deleted += invalidate_pattern("cache", "smart_suggestions_v1", "*")
        deleted += invalidate_pattern("cache", "suggested_people", "*")
    return deleted


def get_smart_suggestions(viewer_profile_id=None, limit: int = 10) -> List[Dict]:
    """Return real-data suggestions with privacy, relationship, and fake-content filters."""
    viewer_profile_id = _profile_id(viewer_profile_id)
    limit = min(max(int(limit or 10), 1), 20)
    key = cache_key("smart_suggestions_v1", viewer_profile_id or "anon", str(limit))
    cached = get_cache(key)
    if isinstance(cached, list):
        return cached

    viewer = _viewer_context(viewer_profile_id)
    excluded = _exclude_ids(viewer_profile_id)
    candidates = _candidate_rows(viewer, limit)
    mutuals = _mutual_counts(viewer_profile_id, [row.get("id") for row in candidates])
    suggestions = []
    seen = set()

    for row in candidates:
        pid = str(row.get("id") or "")
        if not pid or pid in seen or pid in excluded:
            continue
        mutual_count = mutuals.get(pid, 0)
        suggestion = _decorate_suggestion(row, viewer_profile_id, viewer, mutual_count)
        if not suggestion:
            continue
        suggestions.append(suggestion)
        seen.add(pid)
        if len(suggestions) >= limit:
            break

    suggestions.sort(key=lambda item: item.get("score", 0), reverse=True)
    set_cache(key, suggestions, ttl=_SUGGESTION_TTL_SECONDS)
    return suggestions


def build_recommendation_cards(viewer_profile_id=None, limit: int = 3) -> List[Dict]:
    suggestions = get_smart_suggestions(viewer_profile_id, limit=limit)
    cards = []
    if suggestions:
        cards.append({
            "id": "people-you-may-know",
            "type": "people",
            "title": "People You May Know",
            "subtitle": "Real profiles matched by location, friends, and activity.",
            "items": suggestions[:3],
        })
    cards.append({
        "id": "complete-profile",
        "type": "profile",
        "title": "Complete Your Profile",
        "subtitle": "A complete profile helps friends and creators recognize you.",
        "items": [],
        "action_url": "/profile/edit",
    })
    return cards[:limit]
