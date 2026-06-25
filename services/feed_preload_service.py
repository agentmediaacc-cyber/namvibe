"""NamVibe Smart Feed Preload — mixed feed with cursor pagination, content separation, and privacy-safe access."""

from datetime import datetime, timezone, timedelta

from services.neon_service import fast_query
from services.feed_cursor_service import encode_cursor, decode_cursor
from services.ads_service import get_ads_for_feed
from services.homepage_phase141_service import fetch_profiles_batch, normalize_post_v2, normalize_story_v2


def _utcnow():
    return datetime.now(timezone.utc)


_STORY_COLS = [
    "id", "profile_id", "caption", "media_url", "video_url", "thumbnail_url",
    "visibility", "created_at", "expires_at", "duration_seconds",
    "background_color", "text_content", "views_count",
]

_POST_COLS = [
    "id", "profile_id", "caption", "content", "body", "media_url", "video_url",
    "thumbnail_url", "link_url", "town_tag", "visibility", "post_type",
    "likes_count", "comments_count", "created_at", "category",
]

_REEL_COLS = [
    "id", "profile_id", "caption", "video_url", "thumbnail_url", "media_url",
    "visibility", "created_at", "likes_count", "comments_count", "views_count",
    "duration_seconds", "music_title",
]


def _fetch_stories(profile_id, limit):
    now = _utcnow()
    cutoff = now - timedelta(hours=24)
    cols = [c for c in _STORY_COLS]
    col_list = ", ".join(cols)
    clauses = ["deleted_at IS NULL", "created_at >= %s"]
    params = [cutoff]
    if "expires_at" in cols:
        clauses.append("(expires_at IS NULL OR expires_at > %s)")
        params.append(now)
    if profile_id:
        clauses.append("""(
            profile_id = %s
            OR (visibility = 'followers' AND EXISTS (
                SELECT 1 FROM chain_follows
                WHERE follower_profile_id = %s AND following_profile_id = chain_status_posts.profile_id
            ))
        )""")
        params.extend([profile_id, profile_id])
    else:
        clauses.append("visibility = 'public'")
    clauses.append("COALESCE(status, '') <> 'deleted'")
    query = (
        f"SELECT {col_list} FROM chain_status_posts"
        f" WHERE {' AND '.join(clauses)}"
        f" ORDER BY created_at DESC LIMIT %s"
    )
    params.append(limit)
    rows = fast_query(query, params, timeout_ms=3000, default=[])
    profile_ids = [r.get("profile_id") for r in rows if r.get("profile_id")]
    profile_map = fetch_profiles_batch(profile_ids, timeout_ms=2000)
    normalized = []
    for r in rows:
        n = normalize_story_v2(r, profile_map)
        if n.get("id"):
            n["created_at"] = r.get("created_at")
            normalized.append(n)
    return normalized


def _fetch_posts(profile_id, cursor_ts, limit):
    cols = [c for c in _POST_COLS]
    col_list = ", ".join(cols)
    clauses = ["deleted_at IS NULL"]
    params = []
    if cursor_ts:
        clauses.append("created_at < %s")
        params.append(cursor_ts)
    if profile_id:
        clauses.append("""(
            profile_id = %s
            OR visibility = 'public'
            OR (visibility = 'followers' AND EXISTS (
                SELECT 1 FROM chain_follows
                WHERE follower_profile_id = %s AND following_profile_id = chain_posts.profile_id
            ))
        )""")
        params.extend([profile_id, profile_id])
    else:
        clauses.append("visibility = 'public'")
    query = (
        f"SELECT {col_list} FROM chain_posts"
        f" WHERE {' AND '.join(clauses)}"
        f" ORDER BY created_at DESC LIMIT %s"
    )
    params.append(limit + 1)
    rows = fast_query(query, params, timeout_ms=3000, default=[])
    has_more = len(rows) > limit
    items = rows[:limit]
    profile_ids = [r.get("profile_id") for r in items if r.get("profile_id")]
    profile_map = fetch_profiles_batch(profile_ids, timeout_ms=2000)
    normalized = []
    for r in items:
        n = normalize_post_v2(r, profile_map)
        if n.get("id"):
            n["created_at"] = r.get("created_at")
            normalized.append(n)
    return normalized, has_more


def _fetch_reels(profile_id, cursor_ts, limit):
    cols = [c for c in _REEL_COLS]
    col_list = ", ".join(cols)
    clauses = [
        "deleted_at IS NULL",
        "video_url IS NOT NULL",
        "video_url != ''",
    ]
    params = []
    if cursor_ts:
        clauses.append("created_at < %s")
        params.append(cursor_ts)
    if profile_id:
        clauses.append("""(
            profile_id = %s
            OR visibility = 'public'
            OR (visibility = 'followers' AND EXISTS (
                SELECT 1 FROM chain_follows
                WHERE follower_profile_id = %s AND following_profile_id = chain_reels.profile_id
            ))
        )""")
        params.extend([profile_id, profile_id])
    else:
        clauses.append("visibility = 'public'")
    query = (
        f"SELECT {col_list} FROM chain_reels"
        f" WHERE {' AND '.join(clauses)}"
        f" ORDER BY created_at DESC LIMIT %s"
    )
    params.append(limit + 1)
    rows = fast_query(query, params, timeout_ms=3000, default=[])
    has_more = len(rows) > limit
    items = rows[:limit]
    profile_ids = [r.get("profile_id") for r in items if r.get("profile_id")]
    profile_map = fetch_profiles_batch(profile_ids, timeout_ms=2000)
    normalized = []
    for r in items:
        n = normalize_post_v2(r, profile_map)
        if n.get("id"):
            n["created_at"] = r.get("created_at")
            n["duration_seconds"] = r.get("duration_seconds")
            n["music_title"] = r.get("music_title")
            normalized.append(n)
    return normalized, has_more


def _oldest(items):
    candidates = [i.get("created_at") for i in items if i.get("created_at")]
    if not candidates:
        return None
    return min(candidates)


def get_mixed_feed(profile_id=None, cursor=None, limit=20):
    """Return mixed feed with stories, feed_items (posts), reels, and ads.

    Stories are always most-recent 24h items (cursor-independent).
    Posts and reels paginate via the created_at-based cursor.
    Returns at least 20 combined items when available.
    """
    limit = max(20, int(limit))
    cursor_ts = decode_cursor(cursor)

    stories_limit = max(limit // 3, 6)
    posts_limit = max(limit // 2, 10)
    reels_limit = max(limit - stories_limit - posts_limit, 4)

    stories = _fetch_stories(profile_id, limit=stories_limit)
    posts, posts_has_more = _fetch_posts(profile_id, cursor_ts, limit=posts_limit)
    reels, reels_has_more = _fetch_reels(profile_id, cursor_ts, limit=reels_limit)
    ads = get_ads_for_feed(viewer_id=profile_id, slot_count=2)

    paginated = posts + reels
    if paginated and (posts_has_more or reels_has_more):
        oldest_ts = _oldest(paginated)
        next_cursor = encode_cursor(oldest_ts) if oldest_ts else None
    else:
        next_cursor = None

    has_more = posts_has_more or reels_has_more

    return {
        "stories": stories,
        "feed_items": posts,
        "reels": reels,
        "ads": ads,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


def get_feed_v2(profile_id, cursor=None, limit=20):
    """Cursor-paginated flat feed for logged-in users."""
    return get_mixed_feed(profile_id=profile_id, cursor=cursor, limit=limit)


def get_public_feed(cursor=None, limit=20):
    """Cursor-paginated public feed for anonymous users."""
    return get_mixed_feed(profile_id=None, cursor=cursor, limit=limit)
