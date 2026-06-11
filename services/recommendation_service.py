from datetime import datetime, timezone, timedelta

from services.neon_service import fast_query, is_circuit_open
from services.redis_service import cache_get, cache_set
from services.request_cache import get_or_set
from services.supabase_safe import safe_insert, safe_select, safe_update, safe_count
from utils.supabase_client import get_supabase_admin
from services.homepage_real_data_guard import filter_profiles, public_profile_sql

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def calculate_trending_scores():
    """
    Background logic (simplified):
    Iterate over rooms, profiles, posts and calculate a score.
    Score = (Reactions * 2) + (Comments * 5) + (Follows * 10) + (Gifts * 20) / (Hours since creation ^ 1.5)
    """
    # For now, we'll just mock this or do a simple select
    pass

def get_trending_profiles(limit=10):
    # For now, return verified profiles with high activity
    return filter_profiles(safe_select("chain_profiles", filters={"is_verified": True}, limit=limit, order_by="created_at", desc=True))

def get_trending_live_rooms(limit=10):
    return safe_select("chain_live_rooms", filters={"status": "live"}, limit=limit, order_by="viewer_count", desc=True)

def get_trending_posts(limit=10):
    return safe_select("chain_posts", limit=limit, order_by="created_at", desc=True)

def get_recommended_profiles(profile_id, limit=10):
    limit = max(1, min(int(limit or 10), 50))
    cache_key = f"recommend:profiles:{profile_id or 'anon'}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    if is_circuit_open():
        cache_set(cache_key, [], ttl=30)
        return []

    def _query():
        viewer_region_sql = "NULL::text"
        follow_sql = "FALSE"
        self_filter = ""
        params = []
        if profile_id:
            viewer_region_sql = """
                (
                    SELECT COALESCE(NULLIF(v.current_location, ''), NULLIF(v.region, ''), NULLIF(v.country_origin, ''))
                    FROM chain_profiles v
                    WHERE v.id = %s
                    LIMIT 1
                )
            """
            follow_sql = """
                EXISTS (
                    SELECT 1
                    FROM chain_follows f
                    WHERE f.follower_profile_id = %s
                      AND f.following_profile_id = p.id
                      AND f.deleted_at IS NULL
                )
            """
            self_filter = "AND p.id != %s"
            params.extend([profile_id, profile_id, profile_id])

        sql = f"""
            SELECT
                p.id,
                p.username,
                p.full_name,
                p.avatar_url,
                p.cover_url,
                p.bio,
                p.current_location,
                COALESCE(p.is_verified, FALSE) AS is_verified,
                COALESCE(p.is_premium, FALSE) AS is_premium,
                COALESCE(p.is_creator, FALSE) AS is_creator,
                COALESCE(post_counts.post_count, 0) AS post_count,
                COALESCE(follower_counts.follower_count, 0) AS follower_count,
                COALESCE(reel_counts.reel_count, 0) AS reel_count,
                COALESCE(live.viewer_count, 0) AS live_viewer_count,
                {follow_sql} AS follows_author,
                {viewer_region_sql} AS viewer_region,
                COALESCE(NULLIF(p.current_location, ''), NULLIF(p.region, ''), NULLIF(p.country_origin, '')) AS author_region
            FROM chain_profiles p
            LEFT JOIN (
                SELECT profile_id, COUNT(*) AS post_count
                FROM chain_posts
                WHERE deleted_at IS NULL
                GROUP BY profile_id
            ) post_counts ON post_counts.profile_id = p.id
            LEFT JOIN (
                SELECT following_profile_id, COUNT(*) AS follower_count
                FROM chain_follows
                WHERE deleted_at IS NULL
                GROUP BY following_profile_id
            ) follower_counts ON follower_counts.following_profile_id = p.id
            LEFT JOIN (
                SELECT profile_id, COUNT(*) AS reel_count
                FROM chain_reels
                WHERE deleted_at IS NULL
                GROUP BY profile_id
            ) reel_counts ON reel_counts.profile_id = p.id
            LEFT JOIN LATERAL (
                SELECT viewer_count
                FROM chain_live_rooms lr
                WHERE lr.profile_id = p.id
                  AND lr.deleted_at IS NULL
                  AND (COALESCE(lr.is_live, FALSE) = TRUE OR LOWER(COALESCE(lr.status, '')) IN ('live', 'published', 'active'))
                ORDER BY lr.created_at DESC
                LIMIT 1
            ) live ON TRUE
            WHERE p.deleted_at IS NULL
              AND COALESCE(p.is_public, TRUE) = TRUE
              AND {public_profile_sql("p")}
              {self_filter}
            ORDER BY COALESCE(p.is_verified, FALSE) DESC, COALESCE(live.viewer_count, 0) DESC, p.created_at DESC
            LIMIT %s
        """
        rows = fast_query(sql, tuple(params + [limit]), timeout_ms=1000, default=[])
        ranked = []
        for row in rows:
            region_score = 1 if (row.get("viewer_region") and row.get("viewer_region") == row.get("author_region")) else 0
            score = (
                (12 if row.get("is_verified") else 0)
                + (8 if row.get("is_creator") else 0)
                + (6 if row.get("is_premium") else 0)
                + min(int(row.get("live_viewer_count") or 0), 50) * 0.2
                + min(int(row.get("follower_count") or 0), 500) * 0.02
                + min(int(row.get("reel_count") or 0), 100) * 0.2
                + (10 if row.get("follows_author") else 0)
                + (7 if region_score else 0)
            )
            ranked.append({**row, "recommendation_score": round(score, 3)})
        ranked.sort(key=lambda item: item["recommendation_score"], reverse=True)
        return ranked[:limit]

    payload = get_or_set(f"recommend_payload:{profile_id or 'anon'}:{limit}", _query)
    if payload is None:
        payload = []
    cache_set(cache_key, payload, ttl=30)
    return payload

def get_recommended_posts(profile_id, limit=10):
    limit = max(1, min(int(limit or 10), 50))
    cache_key = f"recommend:posts:{profile_id or 'anon'}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    if is_circuit_open():
        cache_set(cache_key, [], ttl=30)
        return []

    sql = f"""
        SELECT
            post.id,
            post.profile_id,
            COALESCE(post.caption, post.body, 'Post') AS title,
            post.created_at,
            COALESCE(post.likes_count, 0) AS likes_count,
            COALESCE(post.comments_count, 0) AS comments_count,
            COALESCE(post.shares_count, 0) AS shares_count,
            p.username,
            p.avatar_url,
            COALESCE(p.is_verified, FALSE) AS is_verified
        FROM chain_posts post
        JOIN chain_profiles p ON p.id = post.profile_id
        WHERE post.deleted_at IS NULL
          AND COALESCE(post.visibility, 'public') = 'public'
          AND {public_profile_sql("p")}
        ORDER BY post.created_at DESC
        LIMIT %s
    """
    payload = get_or_set(
        f"recommend_posts_payload:{profile_id or 'anon'}:{limit}",
        lambda: fast_query(sql, (limit,), timeout_ms=1000, default=[]),
    )
    if payload is None:
        payload = []
    cache_set(cache_key, payload, ttl=30)
    return payload
