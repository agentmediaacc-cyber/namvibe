import time

from engines.cache_engine import cache_key, get_cache, set_cache
from services.neon_service import fast_query, is_circuit_open
from services.profile_service import normalize_profile
from services.recommendation_service import get_recommended_posts
from services.request_cache import get_or_set
from services.homepage_real_data_guard import filter_feed_posts, public_profile_sql, public_profile_subquery
from services.relationship_cache_service import get_many_relationship_states
from services.logging_service import log_info


DISCOVERY_PROFILE_COLUMNS = [
    "id",
    "username",
    "full_name",
    "bio",
    "current_location",
    "avatar_url",
    "is_premium",
    "premium_tier",
    "is_verified",
    "date_of_birth",
    "country_origin",
    "interests",
    "cover_url",
]


def _ms(start):
    return round((time.perf_counter() - start) * 1000, 2)


def _account_kind(profile):
    account_type = str(profile.get("account_type") or "").lower()
    profile_type = str(profile.get("profile_type") or "").lower()
    if account_type == "business" or profile_type == "seller":
        return "business"
    if profile.get("is_creator") or profile_type in {"creator", "host"}:
        return "creator"
    if profile.get("is_premium"):
        return "premium"
    return "person"


def _visibility(profile):
    return str(profile.get("profile_visibility") or profile.get("visibility") or "public").lower()


def _can_view_profile_from_state(viewer_id, profile, state):
    if not viewer_id:
        return _visibility(profile) == "public"
    if state.get("is_self"):
        return True
    if state.get("blocked"):
        return False
    rule = _visibility(profile)
    if rule == "public":
        return True
    if rule == "friends_only":
        return bool(state.get("is_friend"))
    if rule in {"followers_only", "private"}:
        return bool(state.get("is_friend") or state.get("is_following"))
    return True


def _primary_action_from_state(viewer_id, profile, state):
    if not viewer_id:
        return "none"
    if state.get("is_self"):
        return "self"
    if state.get("blocked"):
        return "none"
    if state.get("is_friend"):
        return "message"
    if state.get("friend_request_sent"):
        return "request_sent"
    if state.get("friend_request_received"):
        return "accept_request"
    if state.get("is_following"):
        return "following"
    if state.get("follow_request_sent"):
        return "requested"
    if state.get("follow_request_received"):
        return "approve_follow"
    if _account_kind(profile) == "person":
        return "friend_request"
    return "request_follow" if _visibility(profile) == "private" else "follow"


def _follow_status_from_state(state):
    if state.get("is_self"):
        return "self"
    if state.get("is_following"):
        return "following"
    if state.get("follow_request_sent"):
        return "requested"
    if state.get("follow_request_received"):
        return "request_received"
    return "none"


def _discovery_cache_key(section, viewer_id=None):
    if viewer_id:
        return None
    return cache_key("discovery_v2", section)


def _load_profiles(where_clause="", params=None, limit=20, timeout_ms=5000):
    query = f"""
        SELECT {", ".join("chain_profiles." + column for column in DISCOVERY_PROFILE_COLUMNS)}
        FROM chain_profiles
        WHERE deleted_at IS NULL
          AND COALESCE(is_public, TRUE) = TRUE
          AND {public_profile_sql("chain_profiles")}
          {where_clause}
        ORDER BY COALESCE(is_premium, FALSE) DESC, created_at DESC
        LIMIT %s
    """
    rows = get_or_set(
        f"discover_profiles:{where_clause}:{params}:{limit}",
        lambda: fast_query(query, list(params or []) + [limit], timeout_ms=timeout_ms, default=[]),
    )
    return [normalize_profile(profile) for profile in rows]


def _load_trending(limit=50, timeout_ms=5000):
    query = """
        SELECT id, profile_id, body, caption, media_url, created_at, visibility
        FROM chain_posts
        WHERE deleted_at IS NULL
          AND profile_id IN ({public_profile_subquery()})
        ORDER BY created_at DESC
        LIMIT %s
    """
    return get_or_set(
        f"discover_trending:{limit}",
        lambda: fast_query(query, [limit], timeout_ms=timeout_ms, default=[]),
    )


def _load_live(limit=50, timeout_ms=5000):
    query = """
        SELECT id, title, status, access_type, viewer_count
        FROM chain_live_rooms
        WHERE deleted_at IS NULL
          AND (
            COALESCE(is_live, FALSE) = TRUE
            OR LOWER(COALESCE(status, '')) IN ('live', 'published', 'active')
          )
        ORDER BY created_at DESC
        LIMIT %s
    """
    return get_or_set(
        f"discover_live:{limit}",
        lambda: fast_query(query, [limit], timeout_ms=timeout_ms, default=[]),
    )


def _strip_private_data(item):
    sensitive_keys = {"reel_count", "live_count", "current_location", "date_of_birth", "country_origin", "interests", "cover_url"}
    stripped = dict(item)
    for key in sensitive_keys:
        stripped.pop(key, None)
    stripped["privacy_restricted"] = True
    stripped["bio"] = (item.get("bio") or "")[:120]
    return stripped


def get_discovery_data(section, viewer_id=None, limit=50):
    total_start = time.perf_counter()
    try:
        key = _discovery_cache_key(section, viewer_id=viewer_id)
        cached_data = get_cache(key)
        if cached_data is not None and not viewer_id:
            log_info("discovery_timing", section=section, viewer=bool(viewer_id), phase="cache_hit", duration_ms=_ms(total_start))
            return cached_data

        data = []
        title = section.replace("-", " ").title()

        if is_circuit_open():
            result = {"title": title, "section": section, "items": []}
            if key:
                set_cache(key, result, ttl=30)
            return result

        load_start = time.perf_counter()
        if section == "dating":
            profiles = _load_profiles("AND COALESCE(dating_mode_enabled, FALSE) = TRUE", limit=limit, timeout_ms=5000)
            viewer_profile = {}
            if viewer_id:
                viewer_rows = fast_query(
                    f"SELECT {', '.join(DISCOVERY_PROFILE_COLUMNS)} FROM chain_profiles WHERE id = %s AND deleted_at IS NULL LIMIT 1",
                    [viewer_id],
                    timeout_ms=5000,
                    default=[],
                )
                viewer_profile = normalize_profile(viewer_rows[0]) if viewer_rows else {}

            for p in profiles:
                if p["id"] == viewer_id:
                    continue
                p["compatibility_score"] = _calculate_compatibility(viewer_profile, p)
                data.append(p)

            data.sort(key=lambda x: x.get('compatibility_score', 0), reverse=True)
            title = "Dating Discovery"
        elif section == "live-now" or section == "live":
            data = _load_live(limit=limit)
            title = "Live Now"
        elif section == "members" or section == "recommended":
            data = _load_profiles(limit=limit)
            title = "Recommended Members"
        elif section == "trending":
            data = filter_feed_posts(get_recommended_posts(viewer_id, limit=limit) or _load_trending(limit=limit))
            title = "Trending Feed"
        elif section == "nearby":
            data = _load_profiles("AND current_location IS NOT NULL", limit=limit)
            title = "Nearby Members"
        else:
            data = _load_profiles(limit=limit)
        log_info("discovery_timing", section=section, viewer=bool(viewer_id), phase="load_items", item_count=len(data or []), duration_ms=_ms(load_start))

        enriched = []
        profile_ids = [item.get("id") for item in data if isinstance(item, dict) and item.get("id")]
        rel_start = time.perf_counter()
        rel_states = get_many_relationship_states(viewer_id, profile_ids) if viewer_id and profile_ids else {}
        log_info("discovery_timing", section=section, viewer=bool(viewer_id), phase="load_relationships", item_count=len(profile_ids), duration_ms=_ms(rel_start))

        enrich_start = time.perf_counter()
        for item in data:
            if isinstance(item, dict) and "username" in item:
                pid = item.get("id")
                state = rel_states.get(str(pid), {}) if viewer_id and pid else {}
                if state.get("blocked"):
                    continue

                account_kind = _account_kind(item)
                primary_action = _primary_action_from_state(viewer_id, item, state)
                item["account_kind"] = account_kind
                item["relationship"] = state.get("relationship", "none")
                item["follow_status"] = _follow_status_from_state(state)
                item["primary_action"] = primary_action
                item["can_send_friend_request"] = bool(viewer_id and account_kind == "person" and primary_action == "friend_request")
                item["can_follow"] = bool(viewer_id and primary_action in {"follow", "request_follow", "following"})

                can_view = _can_view_profile_from_state(viewer_id, item, state)
                if not can_view:
                    item = _strip_private_data(item)
            enriched.append(item)
        log_info("discovery_timing", section=section, viewer=bool(viewer_id), phase="enrich_items", item_count=len(enriched), duration_ms=_ms(enrich_start))

        result = {
            "title": title,
            "section": section,
            "items": enriched
        }
        if key:
            set_cache(key, result, ttl=30)
        log_info("discovery_timing", section=section, viewer=bool(viewer_id), phase="total", item_count=len(enriched), duration_ms=_ms(total_start))
        return result
    except Exception as error:
        print(f"[discovery_service] get_discovery_data failed: {error}")
        return {"title": "Discovery", "section": section, "items": []}

def _calculate_compatibility(a, b):
    score = 50
    a_interests = set(a.get("interests") or [])
    b_interests = set(b.get("interests") or [])
    shared = a_interests.intersection(b_interests)
    score += len(shared) * 10

    if a.get("country_origin") == b.get("country_origin"):
        score += 15

    if b.get("is_premium"):
        score += 5

    return min(score, 99)


def search_profiles(query, viewer_id=None, limit=50, offset=0, timeout_ms=5000):
    """
    Search profiles by username, display_name, or full_name using ILIKE.
    Returns dict with items and has_more for pagination.
    """
    if not query:
        return {"items": [], "has_more": False, "query": ""}
    
    search_pattern = f"%{query}%"
    columns = ", ".join("chain_profiles." + col for col in DISCOVERY_PROFILE_COLUMNS)
    
    sql = f"""
        SELECT {columns}
        FROM chain_profiles
        WHERE deleted_at IS NULL
          AND COALESCE(is_public, TRUE) = TRUE
          AND {public_profile_sql("chain_profiles")}
          AND (
            LOWER(username) LIKE LOWER(%s)
            OR LOWER(display_name) LIKE LOWER(%s)
            OR LOWER(full_name) LIKE LOWER(%s)
          )
        ORDER BY COALESCE(is_premium, FALSE) DESC, created_at DESC
        LIMIT %s OFFSET %s
    """
    
    rows = fast_query(
        sql,
        [search_pattern, search_pattern, search_pattern, limit, offset],
        timeout_ms=timeout_ms,
        default=[],
    )
    
    profiles = [normalize_profile(row) for row in rows]
    
    # Check if there are more results
    has_more = len(profiles) == limit
    if has_more:
        # Check if there's actually one more
        check_sql = f"""
            SELECT 1 FROM chain_profiles
            WHERE deleted_at IS NULL
              AND COALESCE(is_public, TRUE) = TRUE
              AND {public_profile_sql("chain_profiles")}
              AND (
                LOWER(username) LIKE LOWER(%s)
                OR LOWER(display_name) LIKE LOWER(%s)
                OR LOWER(full_name) LIKE LOWER(%s)
              )
            ORDER BY COALESCE(is_premium, FALSE) DESC, created_at DESC
            LIMIT 1 OFFSET %s
        """
        has_more_row = fast_query(check_sql, [search_pattern, search_pattern, search_pattern, limit + offset], timeout_ms=timeout_ms, default=[])
        has_more = len(has_more_row) > 0
    
    # Enrich profiles with relationship data
    enriched = []
    profile_ids = [p.get("id") for p in profiles if isinstance(p, dict) and p.get("id")]
    rel_states = get_many_relationship_states(viewer_id, profile_ids) if viewer_id and profile_ids else {}
    
    for item in profiles:
        if isinstance(item, dict) and "username" in item:
            pid = item.get("id")
            state = rel_states.get(str(pid), {}) if viewer_id and pid else {}
            if state.get("blocked"):
                continue
            
            account_kind = _account_kind(item)
            primary_action = _primary_action_from_state(viewer_id, item, state)
            item["account_kind"] = account_kind
            item["relationship"] = state.get("relationship", "none")
            item["follow_status"] = _follow_status_from_state(state)
            item["primary_action"] = primary_action
            item["can_send_friend_request"] = bool(viewer_id and account_kind == "person" and primary_action == "friend_request")
            item["can_follow"] = bool(viewer_id and primary_action in {"follow", "request_follow", "following"})
            
            can_view = _can_view_profile_from_state(viewer_id, item, state)
            if not can_view:
                item = _strip_private_data(item)
            enriched.append(item)
    
    return {
        "items": enriched,
        "has_more": has_more,
        "query": query,
        "offset": offset + len(enriched)
    }
