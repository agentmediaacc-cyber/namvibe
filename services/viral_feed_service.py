"""Viral feed algorithm: For You tab scoring + feed building."""

import math
from datetime import datetime, timezone
from services.neon_service import fast_query

RECENCY_HOURS = 72
LIKE_WEIGHT = 1.5
COMMENT_WEIGHT = 2.0
SHARE_WEIGHT = 3.0
SAVE_WEIGHT = 2.5
WATCH_WEIGHT = 1.0
CREATOR_WEIGHT = 1.2
LOCATION_WEIGHT = 0.5
FOLLOWING_BOOST = 5.0
SAFETY_PENALTY = 100.0


def score_for_you_posts(profile_id=None, cursor=None, limit=20):
    blocked = _blocked_ids(profile_id)
    following = _following_ids(profile_id) if profile_id else []

    rows = fast_query(
        """SELECT p.id, p.profile_id, p.caption, p.created_at, p.media_url, p.media_type,
                  p.likes_count, p.comments_count, p.shares_count,
                  COALESCE(pr.location, '') AS location,
                  COALESCE(pr.follower_count, 0) AS creator_followers,
                  COALESCE(pr.engagement_score, 0) AS creator_trust
           FROM chain_posts p
           JOIN chain_profiles pr ON pr.id = p.profile_id
           WHERE p.deleted_at IS NULL
             AND p.status = 'published'
             AND p.visibility = 'public'
           ORDER BY p.created_at DESC LIMIT 500""",
        default=[],
    )

    scored = []
    for row in rows:
        pid = str(row["id"])
        uid = str(row["profile_id"])
        if uid in blocked:
            continue

        score = _compute_score(row, uid in following, profile_id)
        scored.append((score, _row_to_post(row)))

    scored.sort(key=lambda x: -x[0])
    items = [item for _, item in scored]

    if cursor:
        try:
            idx = next(i for i, item in enumerate(items) if item["id"] == cursor)
            items = items[idx + 1:]
        except (StopIteration, ValueError):
            pass

    result = items[:limit]
    next_cursor = result[-1]["id"] if len(result) == limit and items[limit:] else None
    return result, next_cursor


def score_following_feed(profile_id, cursor=None, limit=20):
    following = _following_ids(profile_id)
    if not following:
        return [], None

    blocked = _blocked_ids(profile_id)

    rows = fast_query(
        """SELECT p.id, p.profile_id, p.caption, p.created_at, p.media_url, p.media_type,
                  p.likes_count, p.comments_count, p.shares_count
           FROM chain_posts p
           WHERE p.profile_id = ANY(%s)
             AND p.deleted_at IS NULL
             AND p.status = 'published'
           ORDER BY p.created_at DESC LIMIT 500""",
        (following,), default=[],
    )

    items = []
    for row in rows:
        uid = str(row["profile_id"])
        if uid in blocked:
            continue
        items.append(_row_to_post(row))

    if cursor:
        try:
            idx = next(i for i, item in enumerate(items) if item["id"] == cursor)
            items = items[idx + 1:]
        except (StopIteration, ValueError):
            pass

    result = items[:limit]
    next_cursor = result[-1]["id"] if len(result) == limit and items[limit:] else None
    return result, next_cursor


def score_trending_feed(profile_id=None, cursor=None, limit=20):
    blocked = _blocked_ids(profile_id) if profile_id else set()

    rows = fast_query(
        """SELECT p.id, p.profile_id, p.caption, p.created_at, p.media_url, p.media_type,
                  p.likes_count, p.comments_count, p.shares_count,
                  COALESCE(pr.location, '') AS location,
                  COALESCE(pr.follower_count, 0) AS creator_followers,
                  COALESCE(pr.engagement_score, 0) AS creator_trust
           FROM chain_posts p
           JOIN chain_profiles pr ON pr.id = p.profile_id
           WHERE p.deleted_at IS NULL
             AND p.status = 'published'
             AND p.visibility = 'public'
           ORDER BY (COALESCE(p.likes_count,0)*1.5 + COALESCE(p.comments_count,0)*2.0 + COALESCE(p.shares_count,0)*3.0) DESC
           LIMIT 500""",
        default=[],
    )

    items = []
    for row in rows:
        uid = str(row["profile_id"])
        if uid in blocked:
            continue
        items.append(_row_to_post(row))

    if cursor:
        try:
            idx = next(i for i, item in enumerate(items) if item["id"] == cursor)
            items = items[idx + 1:]
        except (StopIteration, ValueError):
            pass

    result = items[:limit]
    next_cursor = result[-1]["id"] if len(result) == limit and items[limit:] else None
    return result, next_cursor


def score_nearby_feed(profile_id=None, cursor=None, limit=20):
    if not profile_id:
        return [], None
    profile = fast_query(
        "SELECT location FROM chain_profiles WHERE id = %s", (profile_id,), default=[]
    )
    if not profile or not profile[0].get("location"):
        return [], None

    user_location = profile[0]["location"]
    blocked = _blocked_ids(profile_id)

    rows = fast_query(
        """SELECT p.id, p.profile_id, p.caption, p.created_at, p.media_url, p.media_type,
                  p.likes_count, p.comments_count, p.shares_count,
                  pr.location
           FROM chain_posts p
           JOIN chain_profiles pr ON pr.id = p.profile_id
           WHERE p.deleted_at IS NULL
             AND p.status = 'published'
             AND p.visibility = 'public'
             AND pr.location IS NOT NULL
             AND pr.location != ''
           ORDER BY p.created_at DESC LIMIT 500""",
        default=[],
    )

    items = []
    for row in rows:
        uid = str(row["profile_id"])
        if uid in blocked:
            continue
        loc = (row.get("location") or "").lower()
        score = LOCATION_WEIGHT if loc == user_location.lower() else 0
        item = _row_to_post(row)
        item["_location_match"] = score > 0
        items.append((score, item))

    items.sort(key=lambda x: -x[0])
    items = [item for _, item in items]

    if cursor:
        try:
            idx = next(i for i, item in enumerate(items) if item["id"] == cursor)
            items = items[idx + 1:]
        except (StopIteration, ValueError):
            pass

    result = items[:limit]
    next_cursor = result[-1]["id"] if len(result) == limit and items[limit:] else None
    return result, next_cursor


def _compute_score(row, is_following, profile_id):
    age_hours = (datetime.now(timezone.utc) - row["created_at"]).total_seconds() / 3600 if row.get("created_at") else RECENCY_HOURS
    recency = max(0, 1 - age_hours / RECENCY_HOURS)
    likes = float(row.get("likes_count", 0) or 0) * LIKE_WEIGHT
    comments = float(row.get("comments_count", 0) or 0) * COMMENT_WEIGHT
    shares = float(row.get("shares_count", 0) or 0) * SHARE_WEIGHT
    saves = 0
    trust = float(row.get("creator_trust", 0) or 0) * CREATOR_WEIGHT
    location = float(row.get("location", "") and 1 or 0) * LOCATION_WEIGHT
    follow_boost = FOLLOWING_BOOST if is_following else 0
    penalty = SAFETY_PENALTY if _is_reported_content(str(row["id"])) else 0
    return recency + likes + comments + shares + saves + trust + location + follow_boost - penalty


def _row_to_post(row):
    return {
        "id": str(row["id"]),
        "profile_id": str(row["profile_id"]),
        "caption": row.get("caption", ""),
        "media_url": row.get("media_url", ""),
        "media_type": row.get("media_type", "image"),
        "likes_count": row.get("likes_count", 0) or 0,
        "comments_count": row.get("comments_count", 0) or 0,
        "shares_count": row.get("shares_count", 0) or 0,
        "save_count": 0,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


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
        "SELECT following_profile_id FROM chain_follows WHERE follower_profile_id = %s",
        (profile_id,), default=[],
    )
    return [str(r["following_profile_id"]) for r in rows] if rows else []


def _is_reported_content(content_id):
    try:
        rows = fast_query(
            "SELECT 1 FROM chain_reports WHERE content_id = %s LIMIT 1",
            (content_id,), default=[],
        )
        return bool(rows)
    except Exception:
        return False
