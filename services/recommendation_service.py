"""Enhanced recommendation engine: intelligent feed ranking, trending,
viral detection, creator discovery, nearby content, and notification ranking."""

import math
import time
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from services.neon_service import fast_query, write_query, is_circuit_open
from services.redis_service import cache_get, cache_set
from services.request_cache import get_or_set
from services.interest_engine import build_interest_profile, interest_match_score
from services.homepage_real_data_guard import filter_profiles, public_profile_sql

# ── Scoring weights ──
W_WATCH_TIME = 1.0
W_COMPLETION = 2.0
W_LIKES = 1.5
W_COMMENTS = 2.0
W_SHARES = 3.0
W_SAVES = 2.5
W_PROFILE_CLICKS = 1.0
W_FOLLOW_CONVERSION = 4.0
W_FRIEND = 5.0
W_RECENCY = 1.0
W_LOCATION = 0.5
W_CREATOR_QUALITY = 1.2
W_INTEREST = 3.0
PENALTY_REPORT = 100.0
PENALTY_HIDE = 80.0

RECENCY_HOURS = 72

# ── Trending windows ──
TRENDING_WINDOWS = [1, 6, 24, 168]  


def _utcnow():
    return datetime.now(timezone.utc)


def _utcnow_iso():
    return _utcnow().isoformat()


def _safe_int(v, d=0):
    try:
        return int(v or d)
    except (TypeError, ValueError):
        return d


def _safe_float(v, d=0.0):
    try:
        return float(v or d)
    except (TypeError, ValueError):
        return d


def _parse_dt(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return _utcnow()
    try:
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except Exception:
        return _utcnow()


def _recency_decay(created_at):
    age_h = (_utcnow() - _parse_dt(created_at)).total_seconds() / 3600
    return max(0.0, 1.0 - age_h / RECENCY_HOURS)


def _hours_ago(created_at):
    return (_utcnow() - _parse_dt(created_at)).total_seconds() / 3600


# ═══════════════════════════════════════════════════════════════
#  1. INTELLIGENT FEED RANKING
# ═══════════════════════════════════════════════════════════════

def score_feed_items(profile_id, items, feed_type="for_you"):
    """Rank a list of feed items using the comprehensive scoring formula."""
    if not items:
        return []

    blocked = _blocked_ids(profile_id) if profile_id else set()
    hidden = _hidden_ids(profile_id) if profile_id else set()
    following = set(_following_ids(profile_id)) if profile_id else set()
    friend_ids = set(_friend_ids(profile_id)) if profile_id else set()

    interest_profile = None
    if profile_id:
        try:
            interest_profile = build_interest_profile(profile_id)
        except Exception:
            pass

    scored = []
    for item in items:
        try:
            pid = str(item.get("profile_id") or "")
            iid = str(item.get("id") or "")

            if pid in blocked or iid in blocked:
                continue
            if iid in hidden:
                continue

            score = _compute_item_score(
                item=item,
                is_following=pid in following,
                is_friend=pid in friend_ids,
                interest_profile=interest_profile,
                profile_id=profile_id,
                feed_type=feed_type,
            )
            scored.append((score, item))
        except Exception:
            scored.append((0.0, item))

    scored.sort(key=lambda x: -x[0])
    result = []
    for score, item in scored:
        item["_score"] = score
        result.append(item)
    return result


def _compute_item_score(item, is_following, is_friend, interest_profile, profile_id, feed_type):
    created_at = item.get("created_at")
    age_h = _hours_ago(created_at) if created_at else RECENCY_HOURS
    recency = max(0.0, 1.0 - age_h / RECENCY_HOURS)

    likes = _safe_float(item.get("likes_count")) * W_LIKES
    comments = _safe_float(item.get("comments_count")) * W_COMMENTS
    shares = _safe_float(item.get("shares_count")) * W_SHARES
    saves = _safe_float(item.get("save_count", item.get("saves_count", 0))) * W_SAVES
    views = _safe_float(item.get("views_count", 0)) * W_WATCH_TIME
    creator_quality = _safe_float(item.get("creator_trust", item.get("engagement_score", 0))) * W_CREATOR_QUALITY

    location_bonus = 0.0
    if profile_id and item.get("author_region"):
        try:
            viewer_loc = _viewer_location(profile_id)
            if viewer_loc and viewer_loc.lower() == (item.get("author_region") or "").lower():
                location_bonus = W_LOCATION
        except Exception:
            pass

    interest_score = 0.0
    if interest_profile:
        try:
            interest_score = interest_match_score(profile_id, item) * W_INTEREST
        except Exception:
            pass

    follow_boost = W_FRIEND if is_following else 0
    friend_boost = W_FRIEND * 2.0 if is_friend else 0

    penalty = 0.0
    if _is_reported(iid := str(item.get("id", ""))):
        penalty += PENALTY_REPORT

    return (recency * W_RECENCY
            + likes + comments + shares + saves + views
            + creator_quality + location_bonus + interest_score
            + follow_boost + friend_boost - penalty)


# ═══════════════════════════════════════════════════════════════
#  2. TRENDING ENGINE — Rolling windows
# ═══════════════════════════════════════════════════════════════

def get_trending(window_hours=24, limit=20, content_type=None):
    """Return trending items for a given rolling window."""
    cache_key = f"trending:v2:{window_hours}h:{content_type or 'all'}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    cutoff = _utcnow() - timedelta(hours=window_hours)
    results = {}

    if content_type in (None, "hashtags", "all"):
        rows = fast_query(
            """SELECT hashtag, usage_count, engagement_score, last_used_at
               FROM chain_hashtag_stats
               WHERE last_used_at >= %s
               ORDER BY engagement_score DESC, usage_count DESC
               LIMIT %s""",
            (cutoff, limit), default=[]
        )
        results["hashtags"] = [
            {"tag": r["hashtag"], "score": _safe_float(r.get("engagement_score")),
             "count": _safe_int(r.get("usage_count")), "last_used": r.get("last_used_at")}
            for r in rows
        ]

    if content_type in (None, "posts", "all"):
        rows = fast_query(
            """SELECT id, profile_id, caption, likes_count, comments_count,
                      shares_count, views_count, created_at
               FROM chain_posts
               WHERE deleted_at IS NULL AND status = 'published'
                 AND visibility = 'public'
                 AND created_at >= %s
               ORDER BY (COALESCE(likes_count,0)*1.5 + COALESCE(comments_count,0)*2.0
                        + COALESCE(shares_count,0)*3.0 + COALESCE(views_count,0)*0.5) DESC
               LIMIT %s""",
            (cutoff, limit), default=[]
        )
        results["posts"] = [_trending_post_row(r) for r in rows]

    if content_type in (None, "reels", "all"):
        rows = fast_query(
            """SELECT id, profile_id, caption, likes_count, comments_count,
                      shares_count, views_count, created_at
               FROM chain_reels
               WHERE deleted_at IS NULL AND status = 'published'
                 AND created_at >= %s
               ORDER BY (COALESCE(likes_count,0)*1.5 + COALESCE(comments_count,0)*2.0
                        + COALESCE(shares_count,0)*3.0 + COALESCE(views_count,0)*0.5) DESC
               LIMIT %s""",
            (cutoff, limit), default=[]
        )
        results["reels"] = [_trending_post_row(r) for r in rows]

    if content_type in (None, "creators", "all"):
        rows = fast_query(
            """SELECT p.id, p.username, p.full_name, p.avatar_url, p.is_verified,
                      COALESCE(p.followers_count, 0) AS followers_count,
                      COALESCE(SUM(po.likes_count + po.comments_count), 0) AS engagement
               FROM chain_profiles p
               LEFT JOIN chain_posts po ON po.profile_id = p.id
                 AND po.deleted_at IS NULL AND po.created_at >= %s
               WHERE p.deleted_at IS NULL AND COALESCE(p.is_public, TRUE) = TRUE
               GROUP BY p.id, p.username, p.full_name, p.avatar_url, p.is_verified, p.followers_count
               ORDER BY engagement DESC, followers_count DESC
               LIMIT %s""",
            (cutoff, limit), default=[]
        )
        results["creators"] = [
            {"id": str(r["id"]), "username": r.get("username"), "display_name": r.get("full_name") or r.get("username"),
             "avatar_url": r.get("avatar_url"), "verified": r.get("is_verified", False),
             "follower_count": _safe_int(r.get("followers_count")),
             "engagement_score": _safe_float(r.get("engagement"))}
            for r in rows
        ]

    if content_type in (None, "live", "all"):
        rows = fast_query(
            """SELECT id, profile_id, title, viewer_count, created_at
               FROM chain_live_rooms
               WHERE deleted_at IS NULL
                 AND (COALESCE(is_live, FALSE) = TRUE OR LOWER(COALESCE(status, '')) IN ('live','published','active'))
               ORDER BY viewer_count DESC
               LIMIT %s""",
            (limit,), default=[]
        )
        results["live"] = [
            {"id": str(r["id"]), "profile_id": str(r["profile_id"]),
             "title": r.get("title") or "Live", "viewer_count": _safe_int(r.get("viewer_count"))}
            for r in rows
        ]

    if content_type in (None, "locations", "all"):
        rows = fast_query(
            """SELECT location, COUNT(*) AS profile_count
               FROM chain_profiles
               WHERE location IS NOT NULL AND location != ''
                 AND deleted_at IS NULL
               GROUP BY location
               ORDER BY profile_count DESC LIMIT %s""",
            (limit,), default=[]
        )
        results["locations"] = [
            {"location": r["location"], "count": _safe_int(r.get("profile_count"))}
            for r in rows
        ]

    cache_set(cache_key, results, ttl=30)
    return results


def get_trending_windows(limit=10):
    """Return trending for 1h, 6h, 24h, 7d windows."""
    result = {}
    for w in TRENDING_WINDOWS:
        result[f"{w}h"] = get_trending(window_hours=w, limit=limit)
    return result


def _trending_post_row(r):
    score = (_safe_float(r.get("likes_count")) * 1.5
             + _safe_float(r.get("comments_count")) * 2.0
             + _safe_float(r.get("shares_count")) * 3.0
             + _safe_float(r.get("views_count")) * 0.5)
    return {
        "id": str(r["id"]),
        "profile_id": str(r.get("profile_id", "")),
        "caption": r.get("caption", ""),
        "likes_count": _safe_int(r.get("likes_count")),
        "comments_count": _safe_int(r.get("comments_count")),
        "shares_count": _safe_int(r.get("shares_count")),
        "views_count": _safe_int(r.get("views_count")),
        "score": round(score, 2),
        "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
    }


# ═══════════════════════════════════════════════════════════════
#  3. VIRAL DETECTION
# ═══════════════════════════════════════════════════════════════

def detect_viral_status(item):
    """Classify content as HOT, TRENDING, or VIRAL based on growth signals."""
    likes = _safe_float(item.get("likes_count"))
    comments = _safe_float(item.get("comments_count"))
    shares = _safe_float(item.get("shares_count"))
    saves = _safe_float(item.get("save_count", 0))
    views = _safe_float(item.get("views_count", 0))

    if views < 100:
        return None
    if views == 0:
        return None

    like_rate = likes / max(views, 1)
    comment_rate = comments / max(views, 1)
    share_rate = shares / max(views, 1)
    save_rate = saves / max(views, 1)
    engagement_rate = (likes + comments + shares + saves) / max(views, 1)

    created_at = item.get("created_at")
    age_h = _hours_ago(created_at) if created_at else 99

    if age_h < 1 and engagement_rate > 0.3 and views > 500:
        return "HOT"
    if age_h < 6 and engagement_rate > 0.15 and views > 1000:
        return "TRENDING"
    if age_h < 24 and engagement_rate > 0.08 and views > 5000 and share_rate > 0.02:
        return "VIRAL"
    if age_h < 168 and engagement_rate > 0.05 and views > 10000:
        return "VIRAL"

    if like_rate > 0.4 or share_rate > 0.05:
        return "HOT"
    if engagement_rate > 0.1:
        return "TRENDING"

    return None


def detect_viral_items(items):
    """Batch-detect viral status for a list of items."""
    return [(item, detect_viral_status(item)) for item in items]


# ═══════════════════════════════════════════════════════════════
#  4. CREATOR RECOMMENDATION
# ═══════════════════════════════════════════════════════════════

def get_recommended_profiles(profile_id, limit=10):
    limit = max(1, min(int(limit or 10), 50))
    cache_key = f"recommend:v2:profiles:{profile_id or 'anon'}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    if is_circuit_open():
        cache_set(cache_key, [], ttl=30)
        return []

    def _query():
        following_ids = _following_ids(profile_id) if profile_id else []
        following_set = set(str(f) for f in following_ids)
        blocked_set = _blocked_ids(profile_id) if profile_id else set()

        interest_profile = None
        try:
            if profile_id:
                interest_profile = build_interest_profile(profile_id)
        except Exception:
            pass

        viewer_region_sql = "NULL::text"
        self_filter = ""
        params = []
        if profile_id:
            viewer_region_sql = (
                "(SELECT COALESCE(NULLIF(v.current_location, ''), NULLIF(v.region, ''), "
                "NULLIF(v.country_origin, '')) FROM chain_profiles v WHERE v.id = %s LIMIT 1)"
            )
            self_filter = "AND p.id != %s"
            params.extend([profile_id, profile_id])

        sql = f"""
            SELECT p.id, p.username, p.full_name, p.avatar_url, p.cover_url,
                   p.bio, p.current_location, p.is_verified, p.is_premium, p.is_creator,
                   p.follower_count, p.engagement_score,
                   {viewer_region_sql} AS viewer_region,
                   COALESCE(NULLIF(p.current_location, ''), NULLIF(p.region, ''),
                            NULLIF(p.country_origin, '')) AS author_region
            FROM chain_profiles p
            WHERE p.deleted_at IS NULL
              AND COALESCE(p.is_public, TRUE) = TRUE
              AND {public_profile_sql("p")}
              {self_filter}
            ORDER BY COALESCE(p.is_verified, FALSE) DESC,
                     COALESCE(p.follower_count, 0) DESC,
                     p.created_at DESC
            LIMIT %s
        """
        rows = fast_query(sql, tuple(params + [limit * 3]), timeout_ms=1500, default=[])
        scored = []
        for row in rows:
            pid = str(row["id"])
            if pid in following_set or pid in blocked_set:
                continue

            score = 0.0
            if row.get("is_verified"):
                score += 12
            if row.get("is_creator"):
                score += 8
            if row.get("is_premium"):
                score += 6
            score += min(_safe_float(row.get("follower_count")), 500) * 0.02
            score += _safe_float(row.get("engagement_score", 0)) * 5.0

            region_match = (row.get("viewer_region")
                           and row.get("author_region")
                           and row.get("viewer_region").lower() == row.get("author_region").lower())
            if region_match:
                score += 7

            if interest_profile:
                try:
                    im = interest_match_score(profile_id, row)
                    score += im * 3.0
                except Exception:
                    pass

            p = {
                "id": pid,
                "username": row.get("username", ""),
                "display_name": row.get("full_name") or row.get("username", ""),
                "avatar_url": row.get("avatar_url"),
                "cover_url": row.get("cover_url"),
                "bio": (row.get("bio") or "")[:150],
                "location": row.get("current_location"),
                "is_verified": row.get("is_verified", False),
                "is_premium": row.get("is_premium", False),
                "is_creator": row.get("is_creator", False),
                "follower_count": _safe_int(row.get("follower_count")),
                "score": round(score, 2),
            }
            scored.append((score, p))

        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored][:limit]

    payload = get_or_set(f"recommend_v2_payload:{profile_id or 'anon'}:{limit}", _query)
    if payload is None:
        payload = []
    cache_set(cache_key, payload, ttl=60)
    return payload


def get_recommended_posts(profile_id, limit=10):
    limit = max(1, min(int(limit or 10), 50))
    cache_key = f"recommend:v2:posts:{profile_id or 'anon'}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    if is_circuit_open():
        cache_set(cache_key, [], ttl=30)
        return []

    sql = f"""
        SELECT post.id, post.profile_id,
               COALESCE(post.caption, post.body, 'Post') AS title,
               post.created_at, post.likes_count, post.comments_count,
               post.shares_count, post.views_count,
               p.username, p.avatar_url, p.is_verified,
               COALESCE(p.follower_count, 0) AS creator_followers,
               COALESCE(p.engagement_score, 0) AS creator_trust,
               COALESCE(NULLIF(p.current_location, ''), NULLIF(p.region, ''),
                        NULLIF(p.country_origin, '')) AS author_region,
               COALESCE(post.hashtags, '') AS hashtags,
               COALESCE(post.category, '') AS category
        FROM chain_posts post
        JOIN chain_profiles p ON p.id = post.profile_id
        WHERE post.deleted_at IS NULL
          AND COALESCE(post.visibility, 'public') = 'public'
          AND COALESCE(post.status, 'published') = 'published'
          AND {public_profile_sql("p")}
        ORDER BY post.created_at DESC
        LIMIT %s
    """
    payload = get_or_set(
        f"recommend_v2_posts:{profile_id or 'anon'}:{limit}",
        lambda: fast_query(sql, (limit * 2,), timeout_ms=1500, default=[]),
    )
    if payload is None:
        payload = []
    if profile_id:
        scored = score_feed_items(profile_id, payload, feed_type="recommended")
        result = scored[:limit]
    else:
        result = payload[:limit]
    cache_set(cache_key, result, ttl=30)
    return result


# ═══════════════════════════════════════════════════════════════
#  5. NEARBY CONTENT
# ═══════════════════════════════════════════════════════════════

def get_nearby_content(profile_id, content_type="all", limit=20):
    """Get content geographically close to the viewer."""
    if not profile_id:
        return []
    cache_key = f"nearby:v2:{profile_id}:{content_type}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    viewer_loc = _viewer_location(profile_id)
    if not viewer_loc:
        return []

    result = {}

    if content_type in ("all", "posts"):
        rows = fast_query(
            """SELECT p.id, p.profile_id, p.caption, p.created_at, p.likes_count,
                      p.comments_count, p.shares_count, p.media_url
               FROM chain_posts p
               JOIN chain_profiles pr ON pr.id = p.profile_id
               WHERE p.deleted_at IS NULL AND p.visibility = 'public'
                 AND p.status = 'published'
                 AND LOWER(COALESCE(pr.current_location, '')) = LOWER(%s)
               ORDER BY p.created_at DESC LIMIT %s""",
            (viewer_loc, limit), default=[]
        )
        result["posts"] = [
            {"id": str(r["id"]), "profile_id": str(r["profile_id"]),
             "caption": r.get("caption", ""), "likes_count": _safe_int(r.get("likes_count")),
             "created_at": r["created_at"].isoformat() if r.get("created_at") else None}
            for r in rows
        ]

    if content_type in ("all", "live"):
        rows = fast_query(
            """SELECT lr.id, lr.profile_id, lr.title, lr.viewer_count
               FROM chain_live_rooms lr
               JOIN chain_profiles pr ON pr.id = lr.profile_id
               WHERE lr.deleted_at IS NULL
                 AND (COALESCE(lr.is_live, FALSE) = TRUE
                      OR LOWER(COALESCE(lr.status, '')) IN ('live','published','active'))
                 AND LOWER(COALESCE(pr.current_location, '')) = LOWER(%s)
               ORDER BY lr.viewer_count DESC LIMIT %s""",
            (viewer_loc, limit), default=[]
        )
        result["live"] = [
            {"id": str(r["id"]), "profile_id": str(r["profile_id"]),
             "title": r.get("title") or "Live", "viewer_count": _safe_int(r.get("viewer_count"))}
            for r in rows
        ]

    if content_type in ("all", "creators"):
        rows = fast_query(
            """SELECT id, username, full_name, avatar_url, is_verified, follower_count,
                      engagement_score
               FROM chain_profiles
               WHERE deleted_at IS NULL
                 AND COALESCE(is_public, TRUE) = TRUE
                 AND LOWER(COALESCE(current_location, '')) = LOWER(%s)
               ORDER BY follower_count DESC LIMIT %s""",
            (viewer_loc, limit), default=[]
        )
        result["creators"] = [
            {"id": str(r["id"]), "username": r.get("username"),
             "display_name": r.get("full_name") or r.get("username"),
             "avatar_url": r.get("avatar_url"),
             "follower_count": _safe_int(r.get("follower_count"))}
            for r in rows
        ]

    cache_set(cache_key, result, ttl=120)
    return result


# ═══════════════════════════════════════════════════════════════
#  6. SMART NOTIFICATION RANKING
# ═══════════════════════════════════════════════════════════════

NOTIFICATION_PRIORITY = {
    "message": 100,
    "friend_request": 90,
    "mention": 80,
    "comment": 60,
    "like": 40,
    "live_start": 50,
    "follower": 30,
    "recommendation": 20,
    "system": 10,
}


def rank_notifications(notifications):
    """Rank notifications by type priority, recency, and deduplicate likes."""
    if not notifications:
        return []

    grouped = defaultdict(list)
    for n in notifications:
        ntype = (n.get("type") or n.get("event_type") or "system").lower()
        grouped[ntype].append(n)

    ranked = []
    for ntype, items in grouped.items():
        priority = NOTIFICATION_PRIORITY.get(ntype, 10)
        items.sort(key=lambda x: _parse_dt(x.get("created_at") or x.get("timestamp") or _utcnow_iso()), reverse=True)

        if ntype == "like":
            deduped = {}
            for item in items:
                actor_id = str(item.get("actor_id") or item.get("from_profile_id") or "")
                entity_id = str(item.get("entity_id") or item.get("post_id") or "")
                key = f"{actor_id}:{entity_id}"
                if key not in deduped:
                    deduped[key] = item
                    deduped[key]["count"] = 1
                else:
                    deduped[key]["count"] = deduped[key].get("count", 1) + 1
            items = list(deduped.values())

        for item in items:
            item["_priority"] = priority
            ranked.append((priority, _parse_dt(item.get("created_at") or item.get("timestamp") or _utcnow_iso()), item))

    ranked.sort(key=lambda x: (-x[0], -x[1].timestamp()))
    return [item for _, _, item in ranked]


# ═══════════════════════════════════════════════════════════════
#  7. CALCULATE TRENDING SCORES (existing interface)
# ═══════════════════════════════════════════════════════════════

def calculate_trending_scores():
    try:
        sql = """
            WITH profile_engagement AS (
                SELECT p.id, p.created_at,
                       COALESCE(SUM(po.likes_count), 0) AS total_likes,
                       COALESCE(SUM(po.comments_count), 0) AS total_comments,
                       COALESCE(fc.follower_count, 0) AS follower_count,
                       COALESCE(rc.reel_count, 0) AS reel_count
                FROM chain_profiles p
                LEFT JOIN chain_posts po ON po.profile_id = p.id AND po.deleted_at IS NULL
                LEFT JOIN (SELECT following_profile_id, COUNT(*) AS follower_count
                           FROM chain_follows WHERE deleted_at IS NULL
                           GROUP BY following_profile_id) fc
                  ON fc.following_profile_id = p.id
                LEFT JOIN (SELECT profile_id, COUNT(*) AS reel_count
                           FROM chain_reels WHERE deleted_at IS NULL
                           GROUP BY profile_id) rc
                  ON rc.profile_id = p.id
                WHERE p.deleted_at IS NULL
                GROUP BY p.id, p.created_at, fc.follower_count, rc.reel_count
            )
            UPDATE chain_profiles cp
            SET trending_score = ROUND(
                (total_likes * 2.0 + total_comments * 5.0 + follower_count * 10.0 + reel_count * 8.0)
                / GREATEST(POWER(EXTRACT(EPOCH FROM (now() - pe.created_at)) / 86400.0, 0.5), 1.0)::numeric, 4
            )::double precision
            FROM profile_engagement pe
            WHERE cp.id = pe.id
        """
        write_query(sql)
    except Exception:
        pass


def get_trending_profiles(limit=10):
    return filter_profiles(
        fast_query(
            "SELECT * FROM chain_profiles WHERE is_verified = TRUE AND deleted_at IS NULL ORDER BY created_at DESC LIMIT %s",
            (limit,), default=[]
        )
    )


def get_trending_live_rooms(limit=10):
    return fast_query(
        "SELECT * FROM chain_live_rooms WHERE status = 'live' ORDER BY viewer_count DESC LIMIT %s",
        (limit,), default=[]
    )


def get_trending_posts(limit=10):
    return fast_query(
        "SELECT * FROM chain_posts WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT %s",
        (limit,), default=[]
    )


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def _blocked_ids(profile_id):
    if not profile_id:
        return set()
    rows = fast_query(
        """SELECT blocked_profile_id FROM chain_blocks
           WHERE blocker_profile_id = %s AND deleted_at IS NULL
           UNION
           SELECT blocker_profile_id FROM chain_blocks
           WHERE blocked_profile_id = %s AND deleted_at IS NULL""",
        (profile_id, profile_id), default=[],
    )
    return {str(r["blocked_profile_id"]) for r in rows} if rows else set()


def _following_ids(profile_id):
    rows = fast_query(
        "SELECT following_profile_id FROM chain_follows WHERE follower_profile_id = %s AND deleted_at IS NULL",
        (profile_id,), default=[],
    )
    return [str(r["following_profile_id"]) for r in rows] if rows else []


def _friend_ids(profile_id):
    rows = fast_query(
        """SELECT f1.follower_profile_id AS friend_id
           FROM chain_follows f1
           JOIN chain_follows f2 ON f1.follower_profile_id = f2.following_profile_id
           WHERE f1.following_profile_id = %s
             AND f2.follower_profile_id = %s
             AND f1.deleted_at IS NULL
             AND f2.deleted_at IS NULL""",
        (profile_id, profile_id), default=[],
    )
    return [str(r["friend_id"]) for r in rows] if rows else []


def _hidden_ids(profile_id):
    if not profile_id:
        return set()
    try:
        rows = fast_query(
            "SELECT entity_id FROM chain_hidden_content WHERE profile_id = %s AND deleted_at IS NULL",
            (profile_id,), default=[],
        )
        return {str(r["entity_id"]) for r in rows} if rows else set()
    except Exception:
        return set()


def _viewer_location(profile_id):
    if not profile_id:
        return None
    rows = fast_query(
        "SELECT COALESCE(NULLIF(current_location, ''), NULLIF(region, ''), NULLIF(country_origin, '')) AS loc "
        "FROM chain_profiles WHERE id = %s LIMIT 1",
        (profile_id,), default=[]
    )
    return rows[0].get("loc") if rows else None


def _is_reported(entity_id):
    if not entity_id:
        return False
    try:
        rows = fast_query(
            "SELECT 1 FROM chain_reports WHERE entity_id = %s LIMIT 1",
            (entity_id,), default=[]
        )
        return bool(rows)
    except Exception:
        return False
