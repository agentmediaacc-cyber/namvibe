from engines.cache_engine import cache_key, get_cache, set_cache
from services.neon_service import fast_query, is_circuit_open
from services.profile_service import normalize_profile
from services.recommendation_service import get_recommended_posts, get_recommended_profiles
from services.request_cache import get_or_set


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


def _discovery_cache_key(section, viewer_id=None):
    if viewer_id:
        return None
    return cache_key("discovery_v2", section)


def _load_profiles(where_clause="", params=None, limit=20, timeout_ms=350):
    query = f"""
        SELECT {", ".join("chain_profiles." + column for column in DISCOVERY_PROFILE_COLUMNS)},
               COALESCE(reel_counts.reel_count, 0) AS reel_count,
               COALESCE(live_counts.live_count, 0) AS live_count
        FROM chain_profiles
        LEFT JOIN (
            SELECT profile_id, COUNT(*) AS reel_count
            FROM chain_reels
            WHERE deleted_at IS NULL
            GROUP BY profile_id
        ) reel_counts ON reel_counts.profile_id = chain_profiles.id
        LEFT JOIN (
            SELECT profile_id, COUNT(*) AS live_count
            FROM chain_live_rooms
            WHERE deleted_at IS NULL
            GROUP BY profile_id
        ) live_counts ON live_counts.profile_id = chain_profiles.id
        WHERE deleted_at IS NULL
          AND COALESCE(is_public, TRUE) = TRUE
          {where_clause}
        ORDER BY COALESCE(is_premium, FALSE) DESC, created_at DESC
        LIMIT %s
    """
    rows = get_or_set(
        f"discover_profiles:{where_clause}:{params}:{limit}",
        lambda: fast_query(query, list(params or []) + [limit], timeout_ms=timeout_ms, default=[]),
    )
    return [normalize_profile(profile) for profile in rows]


def _load_trending(limit=50, timeout_ms=350):
    query = """
        SELECT id, profile_id, body, caption, media_url, created_at, visibility
        FROM chain_posts
        WHERE deleted_at IS NULL
        ORDER BY created_at DESC
        LIMIT %s
    """
    return get_or_set(
        f"discover_trending:{limit}",
        lambda: fast_query(query, [limit], timeout_ms=timeout_ms, default=[]),
    )


def _load_live(limit=50, timeout_ms=350):
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


def get_discovery_data(section, viewer_id=None):
    try:
        key = _discovery_cache_key(section, viewer_id=viewer_id)
        cached_data = get_cache(key)
        if cached_data is not None and not viewer_id:
            return cached_data

        data = []
        title = section.replace("-", " ").title()

        if is_circuit_open():
            result = {"title": title, "section": section, "items": []}
            if key:
                set_cache(key, result, ttl=30)
            return result

        if section == "dating":
            profiles = _load_profiles("AND COALESCE(dating_mode_enabled, FALSE) = TRUE", limit=50, timeout_ms=450)
            viewer_profile = {}
            if viewer_id:
                viewer_rows = fast_query(
                    f"SELECT {', '.join(DISCOVERY_PROFILE_COLUMNS)} FROM chain_profiles WHERE id = %s AND deleted_at IS NULL LIMIT 1",
                    [viewer_id],
                    timeout_ms=250,
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
            data = _load_live(limit=50)
            title = "Live Now"
        elif section == "members" or section == "recommended":
            recommended = get_recommended_profiles(viewer_id, limit=50)
            data = [normalize_profile(profile) for profile in recommended] if recommended else _load_profiles(limit=50)
            title = "Recommended Members"
        elif section == "trending":
            data = get_recommended_posts(viewer_id, limit=50) or _load_trending(limit=50)
            title = "Trending Feed"
        elif section == "nearby":
            data = _load_profiles("AND current_location IS NOT NULL", limit=50)
            title = "Nearby Members"
        else:
            data = _load_profiles(limit=20)

        result = {
            "title": title,
            "section": section,
            "items": data
        }
        if key:
            set_cache(key, result, ttl=30)
        return result
    except Exception as error:
        print(f"[discovery_service] get_discovery_data failed: {error}")
        return {"title": "Discovery", "section": section, "items": []}

def _calculate_compatibility(a, b):
    """Calculates a compatibility score between 0-100"""
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
