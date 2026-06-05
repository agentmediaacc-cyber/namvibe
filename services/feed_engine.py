import math
from datetime import datetime, timezone

from services.neon_service import fast_query, is_circuit_open
from services.redis_service import cache_get, cache_set
from services.request_cache import get_or_set


_DEFAULT_FEED_LIMIT = 30
_EMPTY_FEED = []


def _utcnow():
    return datetime.now(timezone.utc)


def _feed_cache_key(feed_type, profile_id, limit):
    return f"feed:{feed_type}:{profile_id or 'anon'}:{int(limit)}"


def _feed_cache_ttl(feed_type, profile_id):
    if feed_type in {"trending", "homepage"} and not profile_id:
        return 30
    return 15 if profile_id else 30


def _viewer_exclusion_clause(profile_id):
    if not profile_id:
        return ""
    return """
      AND NOT EXISTS (
        SELECT 1 FROM chain_blocks b
        WHERE b.deleted_at IS NULL
          AND ((b.blocker_profile_id = %s AND b.blocked_profile_id = p.id)
            OR (b.blocker_profile_id = p.id AND b.blocked_profile_id = %s))
      )
      AND NOT EXISTS (
        SELECT 1 FROM chain_mutes m
        WHERE m.deleted_at IS NULL
          AND m.muter_profile_id = %s
          AND m.muted_profile_id = p.id
      )
    """


def _safe_int(value, default=0):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=0.0):
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return default


def _parse_dt(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return _utcnow()
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return _utcnow()


def _follow_join(profile_id):
    if not profile_id:
        return "FALSE AS follows_author,"
    return f"""
        EXISTS (
            SELECT 1
            FROM chain_follows f
            WHERE f.follower_profile_id = %s
              AND f.following_profile_id = p.id
              AND f.deleted_at IS NULL
        ) AS follows_author,
    """


def _viewer_region_join(profile_id):
    if not profile_id:
        return "NULL::text AS viewer_region,"
    return f"""
        (
            SELECT COALESCE(NULLIF(v.current_location, ''), NULLIF(v.region, ''), NULLIF(v.country_origin, ''))
            FROM chain_profiles v
            WHERE v.id = %s
            LIMIT 1
        ) AS viewer_region,
    """


def _load_feed_rows(profile_id=None, limit=_DEFAULT_FEED_LIMIT, feed_type="explore"):
    if is_circuit_open():
        return []

    sql = f"""
        WITH post_rows AS (
            SELECT
                'post' AS type,
                post.id,
                post.profile_id,
                COALESCE(NULLIF(post.caption, ''), NULLIF(post.body, ''), 'Feed Post') AS title,
                post.created_at,
                COALESCE(post.likes_count, 0) AS likes_count,
                COALESCE(post.comments_count, 0) AS comments_count,
                COALESCE(post.shares_count, 0) AS shares_count,
                0::bigint AS views_count,
                0::bigint AS live_viewer_count,
                FALSE AS is_live,
                FALSE AS is_reel,
                'clean' AS moderation_status,
                post.visibility,
                p.username,
                p.full_name,
                p.avatar_url,
                COALESCE(p.is_verified, FALSE) AS is_verified,
                COALESCE(p.is_premium, FALSE) AS is_premium,
                COALESCE(p.is_creator, FALSE) AS is_creator,
                COALESCE(NULLIF(p.current_location, ''), NULLIF(p.region, ''), NULLIF(p.country_origin, '')) AS author_region,
                {_follow_join(profile_id)}
                {_viewer_region_join(profile_id)}
                COALESCE(live.viewer_count, 0) AS author_live_viewers
            FROM chain_posts post
            JOIN chain_profiles p ON p.id = post.profile_id
            LEFT JOIN LATERAL (
                SELECT viewer_count
                FROM chain_live_rooms lr
                WHERE lr.profile_id = p.id
                  AND lr.deleted_at IS NULL
                  AND (COALESCE(lr.is_live, FALSE) = TRUE OR LOWER(COALESCE(lr.status, '')) IN ('live', 'published', 'active'))
                ORDER BY lr.created_at DESC
                LIMIT 1
            ) live ON TRUE
            WHERE post.deleted_at IS NULL
              AND COALESCE(post.visibility, 'public') = 'public'
              {_viewer_exclusion_clause(profile_id)}
        ),
        reel_rows AS (
            SELECT
                'reel' AS type,
                r.id,
                r.profile_id,
                COALESCE(NULLIF(r.caption, ''), 'Reel') AS title,
                r.created_at,
                COALESCE(r.likes_count, 0) AS likes_count,
                COALESCE(r.comments_count, 0) AS comments_count,
                COALESCE(r.shares_count, 0) AS shares_count,
                COALESCE(r.views_count, 0) AS views_count,
                0::bigint AS live_viewer_count,
                FALSE AS is_live,
                TRUE AS is_reel,
                COALESCE(r.moderation_status, 'clean') AS moderation_status,
                r.visibility,
                p.username,
                p.full_name,
                p.avatar_url,
                COALESCE(p.is_verified, FALSE) AS is_verified,
                COALESCE(p.is_premium, FALSE) AS is_premium,
                COALESCE(p.is_creator, FALSE) AS is_creator,
                COALESCE(NULLIF(p.current_location, ''), NULLIF(p.region, ''), NULLIF(p.country_origin, '')) AS author_region,
                {_follow_join(profile_id)}
                {_viewer_region_join(profile_id)}
                COALESCE(live.viewer_count, 0) AS author_live_viewers
            FROM chain_reels r
            JOIN chain_profiles p ON p.id = r.profile_id
            LEFT JOIN LATERAL (
                SELECT viewer_count
                FROM chain_live_rooms lr
                WHERE lr.profile_id = p.id
                  AND lr.deleted_at IS NULL
                  AND (COALESCE(lr.is_live, FALSE) = TRUE OR LOWER(COALESCE(lr.status, '')) IN ('live', 'published', 'active'))
                ORDER BY lr.created_at DESC
                LIMIT 1
            ) live ON TRUE
            WHERE r.deleted_at IS NULL
              AND COALESCE(r.status, 'published') = 'published'
              AND COALESCE(r.processing_status, 'ready') IN ('ready', 'published')
              AND COALESCE(r.visibility, 'public') = 'public'
              {_viewer_exclusion_clause(profile_id)}
        ),
        live_rows AS (
            SELECT
                'live_room' AS type,
                l.id,
                l.profile_id,
                COALESCE(NULLIF(l.title, ''), 'Live Room') AS title,
                l.created_at,
                0::bigint AS likes_count,
                0::bigint AS comments_count,
                0::bigint AS shares_count,
                COALESCE(l.viewer_count, 0) AS views_count,
                COALESCE(l.viewer_count, 0) AS live_viewer_count,
                TRUE AS is_live,
                FALSE AS is_reel,
                'clean' AS moderation_status,
                'public' AS visibility,
                p.username,
                p.full_name,
                p.avatar_url,
                COALESCE(p.is_verified, FALSE) AS is_verified,
                COALESCE(p.is_premium, FALSE) AS is_premium,
                COALESCE(p.is_creator, FALSE) AS is_creator,
                COALESCE(NULLIF(p.current_location, ''), NULLIF(p.region, ''), NULLIF(p.country_origin, '')) AS author_region,
                {_follow_join(profile_id)}
                {_viewer_region_join(profile_id)}
                COALESCE(l.viewer_count, 0) AS author_live_viewers
            FROM chain_live_rooms l
            JOIN chain_profiles p ON p.id = l.profile_id
            WHERE l.deleted_at IS NULL
              AND (COALESCE(l.is_live, FALSE) = TRUE OR LOWER(COALESCE(l.status, '')) IN ('live', 'published', 'active'))
              {_viewer_exclusion_clause(profile_id)}
        )
        SELECT *
        FROM (
            SELECT * FROM post_rows
            UNION ALL
            SELECT * FROM reel_rows
            UNION ALL
            SELECT * FROM live_rows
        ) items
        ORDER BY created_at DESC
        LIMIT %s
    """
    overscan_limit = max(int(limit) * 3, 60)
    params = []
    if profile_id:
        params.extend([
            profile_id, profile_id, profile_id, profile_id, profile_id,
            profile_id, profile_id, profile_id, profile_id, profile_id,
            profile_id, profile_id, profile_id, profile_id, profile_id,
        ])
    params.append(overscan_limit)
    request_key = f"feed_rows:{feed_type}:{profile_id or 'anon'}:{overscan_limit}"
    return get_or_set(
        request_key,
        lambda: fast_query(sql, tuple(params), timeout_ms=1000, default=[]),
    )


def _rank_item(row, feed_type="explore", diversity_counts=None):
    created_at = _parse_dt(row.get("created_at"))
    age_hours = max((_utcnow() - created_at).total_seconds() / 3600.0, 0.05)
    
    # 1. Recency Score (Exponential decay)
    freshness_decay = 1.0 / math.pow(age_hours + 1.0, 1.25)
    
    # 2. Engagement Velocity
    engagement_velocity = (
        _safe_float(row.get("likes_count")) * 1.5
        + _safe_float(row.get("comments_count")) * 2.2
        + _safe_float(row.get("shares_count")) * 3.0
        + _safe_float(row.get("views_count")) * 0.1
    ) / max(age_hours, 0.5)

    # 3. Boosts
    verified_boost = 15.0 if row.get("is_verified") else 0.0
    creator_boost = 10.0 if row.get("is_creator") else 0.0
    follow_boost = 40.0 if row.get("follows_author") else 0.0
    live_boost = 25.0 if row.get("is_live") else 0.0
    reels_boost = 12.0 if row.get("is_reel") else 0.0
    
    # 4. Diversity Penalty (Avoid spamming same author)
    diversity_penalty = 0.0
    if diversity_counts is not None:
        author_id = row.get("profile_id")
        count = diversity_counts.get(author_id, 0)
        diversity_penalty = count * 15.0 # -15 points for each subsequent post from same author
        diversity_counts[author_id] = count + 1

    # 5. Quality Score (Placeholder for table-backed score)
    quality_score = _safe_float(row.get("quality_score"), 1.0) * 10.0

    # 6. Tab Specific Logic
    if feed_type == "trending":
        freshness_decay *= 0.5 # Less focus on newness, more on velocity
        engagement_velocity *= 2.0
    elif feed_type == "following":
        if not row.get("follows_author"):
            return -1000 # Filter out non-followed content if strict
        follow_boost = 0 # Already filtered

    score = (
        freshness_decay * 120.0
        + engagement_velocity
        + verified_boost
        + creator_boost
        + follow_boost
        + live_boost
        + reels_boost
        + quality_score
        - diversity_penalty
    )

    return round(score, 3)

def _build_feed_uncached(profile_id=None, limit=_DEFAULT_FEED_LIMIT, feed_type="explore"):
    rows = _load_feed_rows(profile_id=profile_id, limit=limit, feed_type=feed_type)
    if not rows:
        return []

    diversity_counts = {}
    ranked = []
    seen = set()
    
    # Pre-fetch quality scores if needed (Omitted for brevity, assuming row might have it soon)

    for row in rows:
        item_key = (row.get("type"), row.get("id"))
        if item_key in seen:
            continue
        seen.add(item_key)
        
        score = _rank_item(row, feed_type=feed_type, diversity_counts=diversity_counts)
        if score > -500: # Filter out penalized content
            ranked.append(_normalize_item(row, score))

    ranked.sort(key=lambda item: item["rank_score"], reverse=True)
    return ranked[: int(limit)]

def build_for_you_feed(profile_id, limit=30):
    return build_feed(profile_id=profile_id, limit=limit, feed_type="for_you")


def build_feed(profile_id=None, limit=30, feed_type="explore"):
    """Builds a ranked feed with cache-backed fallbacks and request dedupe."""
    limit = max(1, min(int(limit or _DEFAULT_FEED_LIMIT), 60))
    key = _feed_cache_key(feed_type, profile_id, limit)
    cached = cache_get(key)
    if cached is not None:
        return cached

    payload = get_or_set(
        f"feed_payload:{feed_type}:{profile_id or 'anon'}:{limit}",
        lambda: _build_feed_uncached(profile_id=profile_id, limit=limit, feed_type=feed_type),
    )
    if payload is None:
        payload = list(_EMPTY_FEED)
    cache_set(key, payload, ttl=_feed_cache_ttl(feed_type, profile_id))
    return payload


def record_feed_event(profile_id, event_type, entity_type, entity_id, actor_profile_id=None):
    from services.analytics_engine import track_event

    return track_event(
        f"feed_{event_type}",
        profile_id=profile_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_profile_id=actor_profile_id,
    )


def trending_feed(limit=30):
    return build_feed(limit=limit, feed_type="trending")


def following_feed(profile_id, limit=30):
    return build_feed(profile_id=profile_id, limit=limit, feed_type="following")


def homepage_feed(profile_id=None, limit=12):
    return build_feed(profile_id=profile_id, limit=limit, feed_type="homepage")


def build_trending_feed(limit=30):
    return trending_feed(limit=limit)


def build_following_feed(profile_id, limit=30):
    return following_feed(profile_id=profile_id, limit=limit)

def _normalize_item(row, score):
    item_type = row.get("type") or "post"
    target = {
        "post": f"/feed/post/{row.get('id')}",
        "reel": f"/reels/{row.get('id')}",
        "live_room": f"/live/room/{row.get('id')}",
    }.get(item_type, f"/feed/item/{row.get('id')}")
    return {
        "id": row.get("id"),
        "type": item_type,
        "title": row.get("title") or item_type.replace("_", " ").title(),
        "profile_id": row.get("profile_id"),
        "created_at": row.get("created_at"),
        "username": row.get("username"),
        "full_name": row.get("full_name"),
        "avatar_url": row.get("avatar_url"),
        "is_verified": bool(row.get("is_verified")),
        "is_premium": bool(row.get("is_premium")),
        "is_live": bool(row.get("is_live")),
        "is_reel": bool(row.get("is_reel")),
        "likes_count": _safe_int(row.get("likes_count")),
        "comments_count": _safe_int(row.get("comments_count")),
        "shares_count": _safe_int(row.get("shares_count")),
        "views_count": _safe_int(row.get("views_count")),
        "rank_score": score,
        "target_url": target,
    }
