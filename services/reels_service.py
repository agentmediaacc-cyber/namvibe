"""Reels service with watch-time tracking, events, comments, and save."""
import os
import time
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.reels_engine import list_reels, get_reel, create_reel, record_reel_view, like_reel, share_reel, delete_reel
from services.reels_serialization_service import serialize_reels, serialize_reel, encode_feed_cursor, decode_feed_cursor, DEFAULT_FEED_LIMIT, MAX_FEED_LIMIT
from services.content_service import get_reels_content_version
from engines.cache_engine import cache_key
from services.logging_service import log_info, log_warning
from services.id_validation import normalize_uuid, filter_valid_uuids
from engines.cache_engine import get_cache, set_cache

_REEL_EVENT_QUEUE = []
_REEL_EVENT_LOCK = __import__("threading").Lock()
_REEL_EVENT_FLUSH_INTERVAL = 30
_REEL_EVENT_LAST_FLUSH = 0
_REEL_EVENT_DEBOUNCE_SECONDS = 300

_DEBOUNCE_EVENTS = {}
_DEBOUNCE_EVENTS_LOCK = __import__("threading").Lock()

try:
    from services.redis_service import redis_manager
    _redis_available = True
except Exception:
    _redis_available = False

_CHAIN_TEST_MODE = os.environ.get("CHAIN_TEST_MODE") == "1"
_CHAIN_REELS_PERF = os.environ.get("CHAIN_REELS_PERF_LOG", "").lower() in ("1", "true", "yes", "on")
_PUBLIC_REELS_FEED_TTL_SECONDS = int(os.environ.get("CHAIN_PUBLIC_REELS_FEED_TTL_SECONDS", "300") or "300")
_LOCAL_REELS_FEED_TTL_SECONDS = int(os.environ.get("CHAIN_LOCAL_REELS_FEED_TTL_SECONDS", "30") or "30")
_LOCAL_REELS_COMMENTS_TTL_SECONDS = int(os.environ.get("CHAIN_LOCAL_REELS_COMMENTS_TTL_SECONDS", "30") or "30")


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def normalize_public_reels_cursor(cursor):
    if not cursor or str(cursor).strip().lower() in {"first", "none", ""}:
        return "first"
    return str(cursor)


def build_public_reels_feed_cache_key(*, content_version, limit, cursor, feed_type="public", namespace=None):
    namespace = namespace or os.environ.get("CHAIN_CACHE_NAMESPACE")
    normalized_cursor = normalize_public_reels_cursor(cursor)
    normalized_version = int(content_version or 1)
    normalized_limit = max(1, min(int(limit or DEFAULT_FEED_LIMIT), MAX_FEED_LIMIT))
    parts = ["reels"]
    if namespace:
        parts.append(namespace)
    parts.extend([
        feed_type,
        "feed",
        f"v{normalized_version}",
        f"limit:{normalized_limit}",
        normalized_cursor,
    ])
    return cache_key(*parts)


def build_viewer_reels_feed_cache_key(*, content_version, limit, cursor, viewer_id, feed_type="viewer", namespace=None):
    namespace = namespace or os.environ.get("CHAIN_CACHE_NAMESPACE")
    normalized_cursor = normalize_public_reels_cursor(cursor)
    normalized_version = int(content_version or 1)
    normalized_limit = max(1, min(int(limit or DEFAULT_FEED_LIMIT), MAX_FEED_LIMIT))
    viewer_key = normalize_uuid(viewer_id) or "anon"
    parts = ["reels"]
    if namespace:
        parts.append(namespace)
    parts.extend([
        feed_type,
        "feed",
        f"v{normalized_version}",
        f"viewer:{viewer_key}",
        f"limit:{normalized_limit}",
        normalized_cursor,
    ])
    return cache_key(*parts)


def get_reel_feed(limit=20, cursor=None, viewer_id=None):
    """Get reels feed with proper visibility filtering.
    
    Visibility rules:
    - public: everyone can see
    - followers: only followers can see
    - private: only owner can see
    
    Caching:
    - Anonymous/public reels (no viewer_id) are cached with short TTL (15s)
    - Authenticated feeds bypass cache (privacy-sensitive)
    """
    started = time.perf_counter()
    limit = max(1, min(int(limit or DEFAULT_FEED_LIMIT), MAX_FEED_LIMIT))
    profile_id_param = normalize_uuid(viewer_id)
    cursor_data = decode_feed_cursor(cursor) if cursor else None
    if cursor and not cursor_data:
        raise ValueError("invalid_cursor")

    # Anonymous/public feed is safe to cache briefly
    if not profile_id_param and not cursor_data:
        local_cache_key = None
        try:
            from services.redis_service import redis_manager as _rmanager
            content_version = get_reels_content_version("public")
            cache_key_str = build_public_reels_feed_cache_key(
                content_version=content_version,
                limit=limit,
                cursor="first" if not cursor_data else "cursor",
                feed_type="public",
            )
            local_cache_key = f"local:{cache_key_str}"
            cached = get_cache(local_cache_key)
            if cached is not None:
                if _CHAIN_REELS_PERF:
                    log_info("reels_feed_timing", cache_hit=True, cache_backend="memory", cache_shared=False, cache_persistent=False, total_ms=round((time.perf_counter() - started) * 1000, 2), viewer=bool(profile_id_param), cursor=bool(cursor_data), limit=limit)
                return cached
            cached_result = _rmanager.get_json_result(cache_key_str)
            cached = cached_result.get("value")
            if cached is not None:
                if isinstance(cached, dict):
                    set_cache(local_cache_key, cached, ttl=_LOCAL_REELS_FEED_TTL_SECONDS)
                    if _CHAIN_REELS_PERF:
                        log_info("reels_feed_timing", cache_hit=True, cache_backend=cached_result.get("backend"), cache_shared=True, cache_persistent=True, total_ms=round((time.perf_counter() - started) * 1000, 2), viewer=bool(profile_id_param), cursor=bool(cursor_data), limit=limit)
                    return cached
                if isinstance(cached, list):
                    payload = {"items": cached, "next_cursor": None, "has_more": False}
                    set_cache(local_cache_key, payload, ttl=_LOCAL_REELS_FEED_TTL_SECONDS)
                    if _CHAIN_REELS_PERF:
                        log_info("reels_feed_timing", cache_hit=True, cache_backend=cached_result.get("backend"), cache_shared=True, cache_persistent=True, total_ms=round((time.perf_counter() - started) * 1000, 2), viewer=bool(profile_id_param), cursor=bool(cursor_data), limit=limit)
                    return payload
        except Exception:
            pass
    elif profile_id_param:
        try:
            from services.redis_service import redis_manager as _rmanager
            content_version = get_reels_content_version("public")
            cache_key_str = build_viewer_reels_feed_cache_key(
                content_version=content_version,
                limit=limit,
                cursor=cursor,
                viewer_id=profile_id_param,
                feed_type="viewer",
            )
            cached_result = _rmanager.get_json_result(cache_key_str)
            cached = cached_result.get("value")
            if cached is not None:
                if isinstance(cached, dict):
                    if _CHAIN_REELS_PERF:
                        log_info("reels_feed_timing", cache_hit=True, cache_backend=cached_result.get("backend"), cache_shared=True, cache_persistent=True, total_ms=round((time.perf_counter() - started) * 1000, 2), viewer=bool(profile_id_param), cursor=bool(cursor_data), limit=limit)
                    return cached
                if isinstance(cached, list):
                    payload = {"items": cached, "next_cursor": None, "has_more": False}
                    if _CHAIN_REELS_PERF:
                        log_info("reels_feed_timing", cache_hit=True, cache_backend=cached_result.get("backend"), cache_shared=True, cache_persistent=True, total_ms=round((time.perf_counter() - started) * 1000, 2), viewer=bool(profile_id_param), cursor=bool(cursor_data), limit=limit)
                    return payload
        except Exception:
            pass

    query = """
        SELECT r.*,
               p.username,
               p.display_name,
               p.avatar_url,
               p.profile_photo,
               p.is_verified,
               COALESCE(r.views_count, 0) AS views_count,
               COALESCE(r.likes_count, 0) AS likes_count,
               COALESCE(r.comments_count, 0) AS comments_count,
               COALESCE(r.shares_count, 0) AS shares_count,
               COALESCE(r.saves_count, 0) AS saves_count
        FROM chain_reels r
        JOIN chain_profiles p ON p.id = r.profile_id
        WHERE r.status = 'published'
          AND r.processing_status = 'ready' AND r.deleted_at IS NULL
    """
    params = []
    
    # Add visibility filter based on viewer
    if profile_id_param:
        # Show: owner's own reels (any visibility) + public reels + followers reels from followed users
        query += """ AND (
            r.profile_id = %s
            OR r.visibility = 'public'
            OR (r.visibility = 'followers' AND EXISTS (
                SELECT 1 FROM chain_follows 
                WHERE follower_profile_id = %s AND following_profile_id = r.profile_id
            ))
        )"""
        params.extend([profile_id_param, profile_id_param])
    else:
        # No viewer - only public reels
        query += " AND r.visibility = 'public'"

    if cursor_data:
        query += " AND (r.created_at, r.id) < (%s::timestamptz, %s::uuid)"
        params.extend([cursor_data["created_at"], cursor_data["id"]])
    
    params.append(limit + 1)
    query += " ORDER BY r.created_at DESC, r.id DESC LIMIT %s"
    db_started = time.perf_counter()
    result = fast_query(query, params, timeout_ms=2000, default=[]) or []
    db_ms = round((time.perf_counter() - db_started) * 1000, 2)

    has_more = len(result) > limit
    if has_more:
        result = result[:limit]
    serialize_started = time.perf_counter()
    serialized = serialize_reels(result, viewer_id=viewer_id)
    serialize_ms = round((time.perf_counter() - serialize_started) * 1000, 2)
    next_cursor = encode_feed_cursor(result[-1].get("created_at"), result[-1].get("id")) if has_more and result else None

    # Cache anonymous/public feed briefly
    if not profile_id_param and not cursor_data:
        try:
            from services.redis_service import redis_manager as _rmanager
            content_version = get_reels_content_version("public")
            cache_key_str = build_public_reels_feed_cache_key(
                content_version=content_version,
                limit=limit,
                cursor="first",
                feed_type="public",
            )
            cache_payload = {"items": serialized, "next_cursor": next_cursor, "has_more": bool(next_cursor)}
            if cache_key_str:
                set_cache(f"local:{cache_key_str}", cache_payload, ttl=_LOCAL_REELS_FEED_TTL_SECONDS)
            _rmanager.set_json_result(cache_key_str, cache_payload, ttl=_PUBLIC_REELS_FEED_TTL_SECONDS, require_shared=True)
            if _CHAIN_REELS_PERF:
                log_info("reels_cache_write_success", category="feed", cache_key_category="public_feed", ttl=_PUBLIC_REELS_FEED_TTL_SECONDS, count=len(serialized))
        except Exception as exc:
            log_warning("reels_cache_write_failed", category="feed", cache_key_category="public_feed", error_type=type(exc).__name__)
    elif profile_id_param:
        try:
            from services.redis_service import redis_manager as _rmanager
            content_version = get_reels_content_version("public")
            cache_key_str = build_viewer_reels_feed_cache_key(
                content_version=content_version,
                limit=limit,
                cursor=cursor,
                viewer_id=profile_id_param,
                feed_type="viewer",
            )
            cache_payload = {"items": serialized, "next_cursor": next_cursor, "has_more": bool(next_cursor)}
            if cache_key_str:
                set_cache(f"local:{cache_key_str}", cache_payload, ttl=_LOCAL_REELS_FEED_TTL_SECONDS)
            _rmanager.set_json_result(cache_key_str, cache_payload, ttl=15, require_shared=True)
            if _CHAIN_REELS_PERF:
                log_info("reels_cache_write_success", category="feed", cache_key_category="viewer_feed", ttl=15, count=len(serialized))
        except Exception as exc:
            log_warning("reels_cache_write_failed", category="feed", cache_key_category="viewer_feed", error_type=type(exc).__name__)
    payload = {"items": serialized, "next_cursor": next_cursor, "has_more": bool(next_cursor)}
    if _CHAIN_REELS_PERF:
        log_info(
            "reels_feed_timing",
            cache_hit=False,
            total_ms=round((time.perf_counter() - started) * 1000, 2),
            query_ms=db_ms,
            serialize_ms=serialize_ms,
            viewer=bool(profile_id_param),
            cursor=bool(cursor_data),
            limit=limit,
            count=len(serialized),
        )
    return payload


def _event_debounce_key(reel_id, user_id, event_type):
    return f"reel_event:{reel_id}:{user_id or 'anon'}:{event_type}"


def _check_event_debounce(reel_id, user_id, event_type):
    if _CHAIN_TEST_MODE:
        return False
    key = _event_debounce_key(reel_id, user_id, event_type)
    if _redis_available:
        try:
            val = redis_manager.get_json(key)
            if val is not None:
                return True
        except Exception:
            pass
    with _DEBOUNCE_EVENTS_LOCK:
        last = _DEBOUNCE_EVENTS.get(key)
        now = time.time()
        if last and (now - last) < _REEL_EVENT_DEBOUNCE_SECONDS:
            return True
        _DEBOUNCE_EVENTS[key] = now
        if len(_DEBOUNCE_EVENTS) > 10000:
            cutoff = now - _REEL_EVENT_DEBOUNCE_SECONDS
            _DEBOUNCE_EVENTS = {k: v for k, v in _DEBOUNCE_EVENTS.items() if v > cutoff}
        return False


def _mark_event_debounce(reel_id, user_id, event_type):
    if _CHAIN_TEST_MODE:
        return
    key = _event_debounce_key(reel_id, user_id, event_type)
    if _redis_available:
        try:
            redis_manager.set_json(key, "1", ttl=_REEL_EVENT_DEBOUNCE_SECONDS)
        except Exception:
            pass


def _flush_reel_events():
    global _REEL_EVENT_LAST_FLUSH
    now = time.time()
    if now - _REEL_EVENT_LAST_FLUSH < _REEL_EVENT_FLUSH_INTERVAL:
        return
    with _REEL_EVENT_LOCK:
        if now - _REEL_EVENT_LAST_FLUSH < _REEL_EVENT_FLUSH_INTERVAL:
            return
        batch = list(_REEL_EVENT_QUEUE)
        _REEL_EVENT_QUEUE.clear()
        _REEL_EVENT_LAST_FLUSH = now
    if not batch:
        return
    def _do_flush():
        for row in batch:
            try:
                write_query(
                    "INSERT INTO chain_reel_events (reel_id, user_id, event_type, watch_ms) VALUES (%s, %s, %s, %s)",
                    (row[0], row[1], row[2], row[3]),
                )
            except Exception:
                pass
    __import__("threading").Thread(target=_do_flush, daemon=True).start()


def track_reel_event(reel_id, user_id, event_type, watch_ms=0):
    """Tracks a reel event with debounce and batched flush."""
    if _check_event_debounce(reel_id, user_id, event_type):
        return True
    _mark_event_debounce(reel_id, user_id, event_type)
    with _REEL_EVENT_LOCK:
        _REEL_EVENT_QUEUE.append((reel_id, user_id, event_type, watch_ms))
    _flush_reel_events()
    return True


def get_reel_comments(reel_id, limit=20):
    cache_key_str = cache_key("reels", "comments", reel_id, "first", f"limit:{limit}", f"v{get_reels_content_version('public')}")
    local_cache_key = f"local:{cache_key_str}"
    cached = get_cache(local_cache_key)
    if cached is not None:
        return cached
    try:
            cached_result = redis_manager.get_json_result(cache_key_str)
            cached = cached_result.get("value")
            if cached is not None:
                set_cache(local_cache_key, cached, ttl=_LOCAL_REELS_COMMENTS_TTL_SECONDS)
                return cached
    except Exception:
        pass
    rows = fast_query("""
        SELECT c.*, p.username, p.avatar_url
        FROM chain_reel_comments c
        JOIN chain_profiles p ON c.profile_id = p.id
        WHERE c.reel_id = %s
        ORDER BY c.created_at DESC
        LIMIT %s
    """, (reel_id, limit), timeout_ms=2000, default=[])
    rows = rows or []
    try:
        set_cache(local_cache_key, rows, ttl=_LOCAL_REELS_COMMENTS_TTL_SECONDS)
        redis_manager.set_json_result(cache_key_str, rows, ttl=20, require_shared=True)
    except Exception:
        pass
    return rows


def get_reel_comments_page(reel_id, limit=20, cursor=None):
    limit = max(1, min(int(limit or 20), 50))
    cursor_data = decode_feed_cursor(cursor) if cursor else None
    if cursor and not cursor_data:
        raise ValueError("invalid_cursor")
    content_version = get_reels_content_version("public")
    cache_key_str = cache_key("reels", "comments", reel_id, f"v{content_version}", f"limit:{limit}", cursor_data["id"] if cursor_data else "first")
    local_cache_key = f"local:{cache_key_str}"
    cached = get_cache(local_cache_key)
    if cached is not None:
        return cached
    try:
            cached_result = redis_manager.get_json_result(cache_key_str)
            cached = cached_result.get("value")
            if cached is not None:
                set_cache(local_cache_key, cached, ttl=_LOCAL_REELS_COMMENTS_TTL_SECONDS)
                return cached
    except Exception:
        pass
    query = """
        SELECT c.*, p.username, p.avatar_url, p.is_verified
        FROM chain_reel_comments c
        JOIN chain_profiles p ON p.id = c.profile_id
        WHERE c.reel_id = %s
    """
    params = [reel_id]
    if cursor_data:
        query += " AND (c.created_at, c.id) < (%s::timestamptz, %s::uuid)"
        params.extend([cursor_data["created_at"], cursor_data["id"]])
    query += " ORDER BY c.created_at DESC, c.id DESC LIMIT %s"
    params.append(limit + 1)
    rows = fast_query(query, tuple(params), timeout_ms=2000, default=[]) or []
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    comments = rows
    next_cursor = encode_feed_cursor(rows[-1].get("created_at"), rows[-1].get("id")) if has_more and rows else None
    payload = {"items": comments, "comments": comments, "next_cursor": next_cursor, "has_more": bool(next_cursor)}
    try:
        set_cache(local_cache_key, payload, ttl=_LOCAL_REELS_COMMENTS_TTL_SECONDS)
        redis_manager.set_json_result(cache_key_str, payload, ttl=20, require_shared=True)
    except Exception:
        pass
    return payload


def add_reel_comment(profile_id, reel_id, body):
    from services.engagement_service import add_comment
    return add_comment(profile_id, "reel", reel_id, body)


def toggle_reel_like(profile_id, reel_id):
    from services.engagement_service import toggle_like
    return toggle_like(profile_id, "reel", reel_id)


def toggle_reel_save(profile_id, reel_id):
    from services.engagement_service import toggle_save
    return toggle_save(profile_id, "reel", reel_id)


def is_following_creator(follower_id, creator_id):
    follower_id = normalize_uuid(follower_id)
    creator_id = normalize_uuid(creator_id)
    if not follower_id or not creator_id:
        return False
    rows = fast_query(
        "SELECT id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s AND deleted_at IS NULL",
        (follower_id, creator_id), timeout_ms=2000, default=[]
    )
    return bool(rows)


def batch_is_following(follower_id, creator_ids):
    follower_id = normalize_uuid(follower_id)
    if not follower_id or not creator_ids:
        return set()
    creator_ids = filter_valid_uuids(creator_ids)
    if not creator_ids:
        return set()
    rows = fast_query(
        "SELECT following_profile_id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = ANY(%s) AND deleted_at IS NULL",
        (follower_id, list(creator_ids)), timeout_ms=500, default=[]
    )
    return {r["following_profile_id"] for r in rows}
