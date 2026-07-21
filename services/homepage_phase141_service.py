"""
Phase 141 — Homepage Timeout Fix: Efficient Query Patterns

This module provides optimized functions that avoid expensive LEFT JOIN chains
by fetching content first, then profiles in a separate batch query.

New pattern:
A. Query content only with LIMIT 20 and timeout_ms=800.
B. Collect all author/profile IDs.
C. Fetch profiles once in batch.
D. Merge profiles into content rows in Python.
"""

import time
from services.neon_service import fast_query
from engines.cache_engine import cache_key, get_cache, set_cache
from services.feed_ranking_service import rank_feed
from services.ads_service import get_ads_for_feed
from services.homepage_real_data_guard import public_profile_sql
from services.id_validation import normalize_uuid, filter_valid_uuids
from services.media_pipeline import normalize_public_media_url

def _format_relative(value):
    """Format relative time - duplicated to avoid circular import."""
    if not value:
        return "Just now"
    from datetime import datetime, timezone
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw[:16].replace("T", " ")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    delta = now - parsed.astimezone(timezone.utc)
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 604800:
        return f"{seconds // 86400}d ago"
    return parsed.strftime("%d %b")


# Profile batch fetch columns for efficient loading
_PROFILE_BATCH_COLUMNS = [
    "id", "username", "display_name", "avatar_url", "profile_photo", "is_verified", "verified",
    "is_online", "profile_score", "profile_level", "activity_status"
]


def _profile_avatar(profile):
    if not profile:
        return ""
    return profile.get("avatar_url") or profile.get("profile_photo") or ""


def fetch_liked_entity_ids(entity_type, viewer_id, entity_ids, timeout_ms=5000):
    """Return the entity IDs liked by the current viewer for homepage rendering."""
    viewer_id = normalize_uuid(viewer_id)
    if not viewer_id or not entity_ids:
        return set()

    table_map = {
        "post": ("chain_post_reactions", "post_id"),
        "reel": ("chain_reel_reactions", "reel_id"),
    }
    table_info = table_map.get(entity_type)
    if not table_info:
        return set()

    table_name, column_name = table_info
    normalized_ids = filter_valid_uuids(entity_ids)
    if not normalized_ids:
        return set()

    try:
        placeholders = ",".join(["%s"] * len(normalized_ids))
        rows = fast_query(
            (
                f"SELECT {column_name} FROM {table_name} "
                f"WHERE profile_id = %s AND reaction_type = 'like' "
                f"AND {column_name} IN ({placeholders})"
            ),
            [viewer_id, *normalized_ids],
            timeout_ms=timeout_ms,
            default=[],
        )
    except Exception:
        return set()

    liked_ids = set()
    for row in rows or []:
        entity_id = row.get(column_name) if isinstance(row, dict) else None
        if entity_id:
            liked_ids.add(str(entity_id))
    return liked_ids


def fetch_profiles_batch(profile_ids, timeout_ms=5000):
    """Fetch profiles by IDs in a single batch query.
    
    Returns dict {id: profile_dict} for efficient lookup.
    """
    if not profile_ids:
        return {}
    unique_ids = filter_valid_uuids(profile_ids)
    if not unique_ids:
        return {}
    
    try:
        placeholders = ",".join(["%s"] * len(unique_ids))
        columns = ", ".join(_PROFILE_BATCH_COLUMNS)
        rows = fast_query(
            f"SELECT {columns} FROM chain_profiles WHERE id IN ({placeholders}) LIMIT %s",
            unique_ids + [len(unique_ids)],
            timeout_ms=timeout_ms,
            default=[]
        )
        return {str(r.get("id")): r for r in rows if isinstance(r, dict) and r.get("id")}
    except Exception:
        return {}


def normalize_story_v2(row, profile_map):
    """Normalize story row with profile data from map."""
    if not row or not row.get("id"):
        return {}
    profile_id = row.get("profile_id")
    profile = profile_map.get(str(profile_id)) if profile_id else {}
    
    display_name = profile.get("display_name") or profile.get("username") or ""
    username = profile.get("username") or ""
    avatar_url = _profile_avatar(profile)
    verified = bool(profile.get("verified") or profile.get("is_verified"))
    is_online = bool(profile.get("is_online"))
    
    return {
        "id": row.get("id"),
        "display_name": display_name,
        "username": username,
        "avatar_url": avatar_url,
        "verified": verified,
        "is_online": is_online,
        "caption": row.get("caption") or "",
        "created_label": _format_relative(row.get("created_at")),
        "profile_url": f"/profile/@{username}" if username else "/discover/",
        "media_url": row.get("media_url") or row.get("thumbnail_url") or "",
        "video_url": row.get("video_url") or "",
        "thumbnail_url": row.get("thumbnail_url") or row.get("media_url") or "",
        "duration_seconds": row.get("duration_seconds"),
        "background_color": row.get("background_color"),
        "text_content": row.get("text_content"),
        "views_count": int(row.get("views_count") or 0),
        "visibility": row.get("visibility") or "followers",
    }


def normalize_live_room_v2(row, profile_map):
    """Normalize live room row with profile data from map."""
    if not row or not row.get("id"):
        return {}
    profile_id = row.get("profile_id") or row.get("host_id") or row.get("creator_id")
    profile = profile_map.get(str(profile_id)) if profile_id else {}
    
    title = row.get("title") or row.get("room_title") or ""
    viewers = row.get("viewer_count") or row.get("viewers") or 0
    creator_name = profile.get("display_name") or profile.get("username") or ""
    
    return {
        "id": row.get("id"),
        "type": "live_room",
        "title": title,
        "category": row.get("category") or "",
        "viewer_count": int(viewers) if viewers else 0,
        "entry_fee_label": f"{int(float(row.get('entry_fee') or 0))} coins" if row.get('entry_fee') else "",
        "cover_url": row.get("cover_url") or row.get("thumbnail_url") or "",
        "creator_name": creator_name,
        "creator_avatar": _profile_avatar(profile),
        "creator_verified": bool(profile.get("verified")),
        "creator_location": profile.get("town") or profile.get("location") or "",
        "created_label": _format_relative(row.get("created_at")),
        "watch_url": "/live/",
    }
def normalize_post_v2(row, profile_map):
    """Normalize post/reel row with profile data from map."""
    if not row or not row.get("id"):
        return {}
    profile_id = row.get("profile_id")
    profile = profile_map.get(str(profile_id)) if profile_id else {}
    
    caption = row.get("caption") or row.get("content") or row.get("body") or ""
    display_name = profile.get("display_name") or profile.get("username") or ""
    username = profile.get("username") or ""
    public_url = row.get("public_url") or ""
    image_url = row.get("image_url") or ""
    video_url = row.get("video_url") or ""
    thumbnail_url = row.get("thumbnail_url") or ""
    media_url = normalize_public_media_url(row.get("media_url") or public_url or image_url or thumbnail_url or video_url or "")
    mime_type = row.get("mime_type") or ""
    media_type = row.get("media_type") or ""
    if not media_type and mime_type:
        media_type = "video" if mime_type.startswith("video/") else "image" if mime_type.startswith("image/") else ""
    video_url = normalize_public_media_url(video_url)
    thumbnail_url = normalize_public_media_url(thumbnail_url or media_url or video_url)
    is_video = bool(video_url) or media_type in ("video", "reel") or mime_type.startswith("video/")
    
    is_online = bool(profile.get("is_online"))
    profile_score = int(profile.get("profile_score") or 0)
    profile_level = profile.get("profile_level") or ""
    return {
        "id": row.get("id"),
        "type": row.get("type") or ("reel" if row.get("video_url") and row.get("music_title") else "post"),
        "display_name": display_name,
        "username": username,
        "avatar_url": _profile_avatar(profile),
        "verified": bool(profile.get("verified")),
        "is_online": is_online,
        "profile_score": profile_score,
        "profile_level": profile_level,
        "caption": caption,
        "excerpt": caption[:180] + ("..." if len(caption) > 180 else ""),
        "media_url": media_url,
        "public_url": public_url or media_url,
        "image_url": image_url or media_url,
        "video_url": video_url,
        "thumbnail_url": thumbnail_url,
        "link_url": row.get("link_url") or "",
        "town_tag": row.get("town_tag") or "",
        "visibility": row.get("visibility") or "public",
        "post_type": row.get("post_type") or "",
        "media_type": media_type or ("video" if video_url else "image" if media_url else ""),
        "mime_type": mime_type,
        "is_video": is_video,
        "likes_count": int(row.get("likes_count") or 0),
        "comments_count": int(row.get("comments_count") or 0),
        "views_count": int(row.get("views_count") or 0),
        "shares_count": int(row.get("shares_count") or 0),
        "music_title": row.get("music_title") or "",
        "category": row.get("category") or "",
        "is_liked": bool(row.get("is_liked")),
        "user_liked": bool(row.get("is_liked")),
        "viewer_has_liked": bool(row.get("is_liked")),
        "created_label": _format_relative(row.get("created_at")),
        "profile_url": f"/profile/@{username}" if username else "/discover/",
    }


def normalize_profile_v2(row):
    """Normalize profile row."""
    if not row or not row.get("id"):
        return {}
    username = row.get("username") or ""
    display_name = row.get("display_name") or row.get("full_name") or username or ""
    return {
        "id": row.get("id"),
        "username": username,
        "display_name": display_name,
        "avatar_url": _profile_avatar(row),
        "verified": bool(row.get("verified") or row.get("is_verified")),
        "is_online": bool(row.get("is_online")),
        "profile_score": int(row.get("profile_score") or 0),
        "profile_level": row.get("profile_level") or "",
        "followers_count": int(row.get("followers_count") or 0),
        "town": row.get("town") or "",
        "location": row.get("location") or "",
        "profile_url": f"/profile/@{username}" if username else "/discover/",
    }


def fetch_stories_v2(story_columns, timeout_ms=800, limit=20, viewer_id=None, include_status_posts=True):
    """Phase 141: Fetch stories WITHOUT expensive profile JOIN.

    Visibility rules:
    - public: everyone can see
    - followers: only followers can see
    - subscribers/locked: only subscribers can see
    - private: only owner can see
    """
    cache_key_str = cache_key(f"homepage:v2:stories:viewer:{viewer_id or 'anon'}")
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached, True, None

    if not story_columns:
        return [], False, "stories: unavailable"

    try:
        # Build visibility-aware query
        profile_id_param = normalize_uuid(viewer_id)
        base_query = f"SELECT {', '.join(story_columns)} FROM chain_status_posts WHERE (expires_at IS NULL OR expires_at > NOW()) AND deleted_at IS NULL"
        
        if profile_id_param:
            query = base_query + """ AND (
                profile_id = %s
                OR (visibility = 'followers' AND EXISTS (
                    SELECT 1 FROM chain_follows 
                    WHERE follower_profile_id = %s AND following_profile_id = profile_id
                ))
                OR (visibility IN ('subscribers','locked') AND EXISTS (
                    SELECT 1 FROM chain_creator_subscriptions
                    WHERE subscriber_profile_id = %s AND creator_profile_id = profile_id AND status = 'active'
                ))
            ) ORDER BY created_at DESC LIMIT %s"""
            rows = fast_query(query, [profile_id_param, profile_id_param, profile_id_param, limit], timeout_ms=timeout_ms, default=[])
        else:
            # Anonymous: show only public stories
            query = base_query + """ AND (visibility IS NULL OR visibility = 'public')
                ORDER BY created_at DESC LIMIT %s"""
            rows = fast_query(query, [limit], timeout_ms=timeout_ms, default=[])

        if include_status_posts:
            sp_cols = _status_select()
            if sp_cols:
                sc = ", ".join(f"sp.{c}" for c in sp_cols)
                status_available = set(sp_cols)
                status_where = []
                status_params = []
                if "deleted_at" in status_available:
                    status_where.append("sp.deleted_at IS NULL")
                if "expires_at" in status_available:
                    status_where.append("(sp.expires_at IS NULL OR sp.expires_at > %s)")
                    status_params.append(_utcnow())
                if "visibility" in status_available:
                    status_where.append("sp.visibility = 'public'")
                if "status" in status_available:
                    status_where.append("COALESCE(sp.status, '') <> 'deleted'")
                status_query = (
                    f"SELECT {sc} FROM chain_status_posts sp "
                    f"{'WHERE ' + ' AND '.join(status_where) if status_where else ''} "
                    f"ORDER BY sp.created_at DESC LIMIT {limit}"
                )
                status_rows = fast_query(status_query, status_params, timeout_ms=timeout_ms, default=[])
                rows = list(rows or []) + list(status_rows or [])

        if not rows:
            return [], False, None

        # Collect profile IDs
        profile_ids = [r.get("profile_id") for r in rows if r.get("profile_id")]

        # Batch fetch profiles
        profile_map = fetch_profiles_batch(profile_ids, timeout_ms=5000)

        # Normalize with profile data
        normalized = [normalize_story_v2(r, profile_map) for r in rows if r.get("id")]
        normalized = [r for r in normalized if r.get("id")]

        result = normalized[:limit]
        set_cache(cache_key_str, result, ttl=60)
        return result, False, None

    except Exception as e:
        return [], False, f"stories: error {e}"


def fetch_reels_v2(reel_columns, timeout_ms=800, limit=20, viewer_id=None, return_raw=False):
    """Phase 141: Fetch reels WITHOUT expensive profile JOIN.
    
    Visibility rules:
    - public: everyone can see
    - followers: only followers can see
    - private: only owner can see
    """
    cache_key_str = cache_key(f"homepage:v2:reels:viewer:{viewer_id or 'anon'}")
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached, True, None
    
    if not reel_columns:
        return [], False, "reels: unavailable"
    
    try:
        profile_id_param = normalize_uuid(viewer_id)
        base_query = f"SELECT {', '.join(reel_columns)} FROM chain_reels WHERE deleted_at IS NULL AND video_url IS NOT NULL AND video_url != ''"
        
        if profile_id_param:
            query = base_query + """ AND (
                profile_id = %s
                OR visibility = 'public'
                OR (visibility = 'followers' AND EXISTS (
                    SELECT 1 FROM chain_follows 
                    WHERE follower_profile_id = %s AND following_profile_id = profile_id
                ))
            ) ORDER BY created_at DESC LIMIT %s"""
            rows = fast_query(query, [profile_id_param, profile_id_param, limit], timeout_ms=timeout_ms, default=[])
        else:
            query = base_query + " AND visibility = 'public' ORDER BY created_at DESC LIMIT %s"
            rows = fast_query(query, [limit], timeout_ms=timeout_ms, default=[])
        
        if not rows:
            return [], False, None
        
        liked_ids = fetch_liked_entity_ids("reel", viewer_id, [r.get("id") for r in rows], timeout_ms=5000)
        for row in rows:
            row["type"] = "reel"
            row["is_liked"] = str(row.get("id")) in liked_ids

        if return_raw:
            return rows, False, None

        profile_ids = [r.get("profile_id") for r in rows if r.get("profile_id")]
        profile_map = fetch_profiles_batch(profile_ids, timeout_ms=5000)

        normalized = [normalize_post_v2(r, profile_map) for r in rows if r.get("id")]
        normalized = [r for r in normalized if r.get("id")]

        # Keep the newest reels visible on homepage so fresh uploads reflect immediately.
        newest = normalized[: min(5, len(normalized))]
        ranked = rank_feed(normalized, viewer_id=viewer_id, tab="for_you", limit=max(limit, len(normalized)))
        merged = []
        seen = set()
        for item in newest + ranked:
            item_id = str(item.get("id") or "")
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            merged.append(item)
            if len(merged) >= limit:
                break
        result = merged[:limit]
        set_cache(cache_key_str, result, ttl=60)
        return result, False, None
        
    except Exception as e:
        return [], False, f"reels: error {e}"


def fetch_posts_v2(post_columns, timeout_ms=800, limit=20, viewer_id=None, include_ads=True, return_raw=False):
    """Phase 141: Fetch posts WITHOUT expensive profile JOIN.
    
    Visibility rules:
    - public: everyone can see
    - followers: only followers can see
    - private: only owner can see
    """
    cache_key_str = cache_key(f"homepage:v2:posts:viewer:{viewer_id or 'anon'}")
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached, True, None
    
    if not post_columns:
        return [], False, "posts: unavailable"
    
    try:
        profile_id_param = normalize_uuid(viewer_id)
        base_query = f"SELECT {', '.join(post_columns)} FROM chain_posts WHERE deleted_at IS NULL"
        
        if profile_id_param:
            # Show: owner's own posts (any visibility) + public posts + followers posts from followed users
            query = base_query + """ AND (
                profile_id = %s
                OR visibility = 'public'
                OR (visibility = 'followers' AND EXISTS (
                    SELECT 1 FROM chain_follows 
                    WHERE follower_profile_id = %s AND following_profile_id = profile_id
                ))
            ) ORDER BY created_at DESC LIMIT %s"""
            rows = fast_query(query, [profile_id_param, profile_id_param, limit], timeout_ms=timeout_ms, default=[])
        else:
            # No viewer - only public posts
            query = base_query + " AND visibility = 'public' ORDER BY created_at DESC LIMIT %s"
            rows = fast_query(query, [limit], timeout_ms=timeout_ms, default=[])
        
        if not rows:
            return [], False, None
        
        liked_ids = fetch_liked_entity_ids("post", viewer_id, [r.get("id") for r in rows], timeout_ms=5000)
        for row in rows:
            row["type"] = row.get("type") or "post"
            row["is_liked"] = str(row.get("id")) in liked_ids

        if return_raw:
            return rows, False, None

        profile_ids = [r.get("profile_id") for r in rows if r.get("profile_id")]
        profile_map = fetch_profiles_batch(profile_ids, timeout_ms=5000)

        normalized = [normalize_post_v2(r, profile_map) for r in rows if r.get("id")]
        normalized = [r for r in normalized if r.get("id")]
        
        ranked = rank_feed(normalized, viewer_id=viewer_id, tab="trending", limit=limit)
        if include_ads and viewer_id is None:
            ad_slots = get_ads_for_feed(viewer_id=None, slot_count=1)
            if ad_slots and len(ranked) >= 3:
                ranked.insert(3, ad_slots[0])
        result = ranked[:limit]
        set_cache(cache_key_str, result, ttl=60)
        return result, False, None
        
    except Exception as e:
        return [], False, f"posts: error {e}"


def fetch_live_rooms_v2(live_columns, timeout_ms=800, limit=5):
    """Phase 141: Fetch live rooms WITHOUT expensive profile JOIN."""
    cache_key_str = cache_key("homepage:v2:public:live_rooms")
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached, True, None
    
    if not live_columns:
        return [], False, "live_rooms: unavailable"
    
    try:
        rows = fast_query(
            f"SELECT {', '.join(live_columns)} FROM chain_live_rooms WHERE (is_live = TRUE OR status = 'live') AND deleted_at IS NULL ORDER BY created_at DESC LIMIT {limit}",
            timeout_ms=timeout_ms,
            default=[]
        )
        
        if not rows:
            return [], False, None
        
        profile_ids = [r.get("profile_id") or r.get("host_id") or r.get("creator_id") for r in rows if r.get("profile_id") or r.get("host_id") or r.get("creator_id")]
        profile_map = fetch_profiles_batch(profile_ids, timeout_ms=5000)
        
        normalized = [normalize_live_room_v2(r, profile_map) for r in rows if r.get("id")]
        normalized = [r for r in normalized if r.get("id")]
        
        result = normalized[:limit]
        set_cache(cache_key_str, result, ttl=60)
        return result, False, None
        
    except Exception as e:
        return [], False, f"live_rooms: error {e}"


def fetch_suggested_people_v2(profile_columns, timeout_ms=500, limit=10):
    """Phase 141: Fetch suggested people WITHOUT expensive operations."""
    cache_key_str = cache_key("homepage:v1:public:suggested_people")
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached, True
    
    if not profile_columns:
        return [], False
    
    try:
        public_sql = public_profile_sql("chain_profiles")
        rows = fast_query(
            f"""
            SELECT {', '.join(profile_columns)}
            FROM chain_profiles
            WHERE deleted_at IS NULL
              AND COALESCE(is_public, TRUE) = TRUE
              AND {public_sql}
            ORDER BY COALESCE(is_verified, FALSE) DESC,
                     COALESCE(followers_count, 0) DESC,
                     created_at DESC
            LIMIT {limit * 3}
            """,
            timeout_ms=timeout_ms,
            default=[]
        )
        
        normalized = [normalize_profile_v2(r) for r in rows if r.get("id")]
        normalized = [r for r in normalized if r.get("id")]
        result = normalized[:limit]
        set_cache(cache_key_str, result, ttl=60)
        return result, False
        
    except Exception:
        return [], False
