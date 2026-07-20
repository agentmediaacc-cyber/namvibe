"""Phase 59 — Real Feed API + Follow + Like/Save/Share actions.
   Phase 120 — Premium Homepage JSON endpoints."""

import os
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request, session
from services.profile_service import get_current_profile
from services.homepage_service import (
    get_feed_tab,
    get_homepage_payload,
    get_homepage_sidebar_payload,
    rank_homepage_sections,
    _fetch_friend_activity,
)
from services.homepage_cache_service import get_full, get_full_with_stale, get_payload, get_payload_with_stale
from services.homepage_phase141_service import (
    fetch_posts_v2,
    fetch_reels_v2,
    fetch_stories_v2,
    fetch_live_rooms_v2,
    fetch_suggested_people_v2,
    fetch_liked_entity_ids,
    fetch_profiles_batch,
    normalize_post_v2,
)
from services.engagement_service import follow_profile, unfollow_profile, toggle_like, toggle_save
from services.ai.interaction_service import track_interaction_safe
from services.neon_service import fast_query, is_circuit_open
from services.homepage_real_data_guard import filter_content, filter_profiles, public_profile_sql
from services.media_pipeline import normalize_public_media_url
from services.logging_service import log_info
from api_routes.profile_routes import login_required

homepage_api_bp = Blueprint("homepage_api", __name__)
feed_preload_bp = Blueprint("feed_preload", __name__)


def _current_profile():
    profile = get_current_profile()
    if profile and profile.get("id"):
        return profile
    pid = session.get("profile_id")
    if pid:
        return {"id": pid}
    return None


def _json_ok(data, status=200):
    return jsonify({"ok": True, **data}), status


def _json_error(message, status=400):
    return jsonify({"ok": False, "error": message}), status


def _safe_degraded_homepage_payload():
    return {
        "success": True,
        "homepage_degraded": True,
        "feed_items": [],
        "feed_for_you": [],
        "posts": [],
        "reels": [],
        "stories": [],
        "live_rooms": [],
        "suggested_creators": [],
        "suggested_people": [],
        "trending_hashtags": [],
        "online_users": [],
        "friend_activity": [],
        "counts": {
            "live_now": 0,
            "unread_messages": 0,
            "coins": 0,
        },
        "wallet": {"coin_balance": 0, "label_balance": "0"},
        "unread_counts": {},
        "empty_states": {},
    }


def _minimal_feed_payload():
    return {
        "feed_items": [],
        "stories": [],
        "reels": [],
        "friend_activity": [],
        "homepage_degraded": True,
    }


_HOMEPAGE_CACHE = {"payload": None, "expires_at": 0}
_HOMEPAGE_CACHE_TTL = 60
_HOMEPAGE_WIDGET_CACHE = {}
_HOMEPAGE_WIDGET_CACHE_TTL = 45


def _cached_public_homepage_snapshot():
    full = get_full("public")
    if full:
        return full
    full, _ = get_full_with_stale("public")
    if full:
        return full
    payload, _ = get_payload_with_stale()
    if payload:
        return payload
    return {}


def _homepage_response_from_snapshot(snapshot, viewer_id=None, limit=20, tab="for_you"):
    if not snapshot:
        return None
    posts = list(snapshot.get("feed_items") or snapshot.get("posts") or [])
    reels = list(snapshot.get("reels") or [])
    stories = list(snapshot.get("stories") or [])
    live_rooms = list(snapshot.get("live_rooms") or [])
    suggested_creators = list(snapshot.get("suggested_creators") or snapshot.get("suggested_people") or [])
    counts = dict(snapshot.get("counts") or {})
    timings = dict(snapshot.get("timings") or {})
    payload = {
        "success": True,
        "posts": posts,
        "reels": reels,
        "stories": stories,
        "live_rooms": live_rooms,
        "suggested_creators": suggested_creators,
        "suggested_people": list(suggested_creators),
        "trending_hashtags": list(snapshot.get("trending_hashtags") or []),
        "online_users": list(snapshot.get("online_users") or []),
        "counts": counts,
        "feed_items": posts,
        "feed_for_you": list(posts),
        "homepage_degraded": bool(snapshot.get("homepage_degraded")),
        "timings": timings,
        "empty_states": {
            "feed": not bool(posts),
            "stories": not bool(stories),
            "reels": not bool(reels),
            "live": not bool(live_rooms),
            "suggested": not bool(suggested_creators),
            "hashtags": not bool(snapshot.get("trending_hashtags") or []),
        },
    }
    if tab == "live":
        payload["feed_items"] = []
        payload["feed_for_you"] = []
    elif tab == "following" and viewer_id:
        payload["feed_for_you"] = list(posts)
    return payload


def _timed_section(name, collector, fn):
    started = time.perf_counter()
    try:
        return fn()
    finally:
        collector[name] = round((time.perf_counter() - started) * 1000, 2)


def _widget_cache_key(viewer_id):
    return str(viewer_id or "anon")


def _get_widget_cache(viewer_id):
    key = _widget_cache_key(viewer_id)
    cached = _HOMEPAGE_WIDGET_CACHE.get(key)
    now = time.time()
    if cached and now < cached.get("expires_at", 0):
        return cached.get("payload")
    return None


def _set_widget_cache(viewer_id, payload):
    _HOMEPAGE_WIDGET_CACHE[_widget_cache_key(viewer_id)] = {
        "payload": payload,
        "expires_at": time.time() + _HOMEPAGE_WIDGET_CACHE_TTL,
    }


def _parse_dt(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _iso(value):
    parsed = _parse_dt(value)
    return parsed.astimezone(timezone.utc).isoformat() if parsed else None


def _safe_int(value, default=0):
    try:
        return int(float(value or 0))
    except Exception:
        return default


def _extract_hashtags(*texts):
    found = {}
    for text in texts:
        for token in str(text or "").split():
            if token.startswith("#"):
                tag = "".join(ch for ch in token[1:] if ch.isalnum() or ch == "_").lower()
                if tag:
                    found[tag] = found.get(tag, 0) + 1
    return found


def _normalize_content_item(item, default_type):
    item = dict(item or {})
    caption = item.get("caption") or item.get("body") or item.get("text") or ""
    return {
        "id": item.get("id"),
        "type": item.get("type") or default_type,
        "title": item.get("title") or "",
        "caption": caption,
        "body": item.get("body") or caption,
        "media_url": normalize_public_media_url(item.get("media_url") or item.get("public_url") or item.get("image_url") or item.get("thumbnail_url") or item.get("video_url") or ""),
        "video_url": normalize_public_media_url(item.get("video_url") or ""),
        "image_url": normalize_public_media_url(item.get("image_url") or item.get("media_url") or item.get("thumbnail_url") or ""),
        "poster_url": normalize_public_media_url(item.get("thumbnail_url") or item.get("poster_url") or item.get("image_url") or ""),
        "creator_id": item.get("profile_id") or item.get("creator_id"),
        "creator_name": item.get("display_name") or item.get("creator_name") or item.get("username") or "",
        "creator_username": item.get("username") or item.get("creator_username") or "",
        "creator_avatar": item.get("avatar_url") or item.get("creator_avatar") or "",
        "created_at": _iso(item.get("created_at")),
        "privacy": item.get("visibility") or item.get("privacy") or "public",
        "stats": {
            "likes": _safe_int(item.get("likes_count")),
            "comments": _safe_int(item.get("comments_count")),
            "shares": _safe_int(item.get("shares_count")),
            "views": _safe_int(item.get("views_count") or item.get("view_count")),
        },
        "display_name": item.get("display_name") or item.get("creator_name") or item.get("username") or "",
        "username": item.get("username") or item.get("creator_username") or "",
        "avatar_url": item.get("avatar_url") or item.get("creator_avatar") or "",
        "profile_id": item.get("profile_id") or item.get("creator_id"),
        "verified": bool(item.get("verified") or item.get("is_verified")),
        "is_online": bool(item.get("is_online")),
        "created_label": item.get("created_label") or "",
        "likes_count": _safe_int(item.get("likes_count")),
        "comments_count": _safe_int(item.get("comments_count")),
        "shares_count": _safe_int(item.get("shares_count")),
        "views_count": _safe_int(item.get("views_count") or item.get("view_count")),
    }


def _normalize_story_item(item):
    item = dict(item or {})
    return {
        "id": item.get("id"),
        "type": "story",
        "title": "",
        "caption": item.get("caption") or item.get("text_content") or "",
        "body": item.get("text_content") or item.get("caption") or "",
        "media_url": normalize_public_media_url(item.get("media_url") or item.get("thumbnail_url") or item.get("video_url") or ""),
        "video_url": normalize_public_media_url(item.get("video_url") or ""),
        "image_url": normalize_public_media_url(item.get("thumbnail_url") or item.get("media_url") or ""),
        "poster_url": normalize_public_media_url(item.get("thumbnail_url") or item.get("poster_url") or item.get("media_url") or ""),
        "creator_id": item.get("profile_id"),
        "creator_name": item.get("display_name") or item.get("username") or "",
        "creator_username": item.get("username") or "",
        "creator_avatar": item.get("avatar_url") or "",
        "created_at": _iso(item.get("created_at")),
        "privacy": item.get("visibility") or "followers",
        "stats": {
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "views": _safe_int(item.get("views_count")),
        },
        "display_name": item.get("display_name") or item.get("username") or "",
        "username": item.get("username") or "",
        "avatar_url": item.get("avatar_url") or "",
        "profile_id": item.get("profile_id"),
        "verified": bool(item.get("verified") or item.get("is_verified")),
        "is_online": bool(item.get("is_online")),
        "created_label": item.get("created_label") or "",
        "views_count": _safe_int(item.get("views_count")),
    }


def _normalize_live_room_item(item):
    item = dict(item or {})
    return {
        "id": item.get("id"),
        "type": "live_room",
        "title": item.get("title") or item.get("creator_name") or "Live",
        "caption": "",
        "body": "",
        "media_url": normalize_public_media_url(item.get("cover_url") or ""),
        "video_url": "",
        "image_url": normalize_public_media_url(item.get("cover_url") or ""),
        "poster_url": normalize_public_media_url(item.get("cover_url") or ""),
        "creator_id": item.get("profile_id") or item.get("creator_id"),
        "creator_name": item.get("creator_name") or "",
        "creator_username": item.get("creator_username") or "",
        "creator_avatar": item.get("creator_avatar") or "",
        "created_at": _iso(item.get("created_at")),
        "privacy": "public",
        "stats": {
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "views": _safe_int(item.get("viewer_count")),
        },
        "viewer_count": _safe_int(item.get("viewer_count")),
        "watch_url": item.get("watch_url") or (("/live/" + str(item.get("id"))) if item.get("id") else "/live/"),
    }


def _normalize_profile_item(item):
    item = dict(item or {})
    return {
        "id": item.get("id"),
        "type": "profile",
        "title": "",
        "caption": item.get("bio") or "",
        "body": item.get("bio") or "",
        "media_url": normalize_public_media_url(item.get("avatar_url") or item.get("profile_photo") or ""),
        "video_url": "",
        "image_url": normalize_public_media_url(item.get("avatar_url") or item.get("profile_photo") or ""),
        "poster_url": normalize_public_media_url(item.get("avatar_url") or item.get("profile_photo") or ""),
        "creator_id": item.get("id"),
        "creator_name": item.get("display_name") or item.get("username") or "",
        "creator_username": item.get("username") or "",
        "creator_avatar": item.get("avatar_url") or item.get("profile_photo") or "",
        "created_at": _iso(item.get("created_at")),
        "privacy": "public",
        "stats": {
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "views": 0,
        },
        "followers_count": _safe_int(item.get("followers_count")),
        "verified": bool(item.get("verified") or item.get("is_verified")),
        "is_online": bool(item.get("is_online")),
        "display_name": item.get("display_name") or item.get("username") or "",
        "username": item.get("username") or "",
        "avatar_url": item.get("avatar_url") or item.get("profile_photo") or "",
        "profile_level": item.get("profile_level") or "",
        "profile_score": _safe_int(item.get("profile_score")),
    }


def _fetch_real_online_users(limit=8):
    now = datetime.now(timezone.utc)
    online_cutoff = now - timedelta(minutes=5)
    online_ids = []
    try:
        from services.redis_service import get_redis, namespaced_key
        client = get_redis()
        if client:
            for key in client.scan_iter(namespaced_key("presence", "state", "*")):
                try:
                    raw = client.get(key)
                    payload = json.loads(raw) if raw else None
                except Exception:
                    payload = None
                if not payload or str(payload.get("status") or payload.get("state") or "").lower() != "online":
                    continue
                seen_at = _parse_dt(payload.get("last_seen_at") or payload.get("updated_at"))
                if not seen_at or seen_at < online_cutoff:
                    continue
                profile_id = str(key).rsplit(":", 1)[-1]
                if profile_id and profile_id not in online_ids:
                    online_ids.append(profile_id)
                if len(online_ids) >= max(limit * 4, 20):
                    break
    except Exception:
        online_ids = []

    if online_ids:
        placeholders = ",".join(["%s"] * len(online_ids))
        rows = fast_query(
            f"""
            SELECT id, username, display_name, avatar_url
            FROM chain_profiles
            WHERE id IN ({placeholders})
              AND deleted_at IS NULL
              AND {public_profile_sql('chain_profiles')}
            LIMIT %s
            """,
            [*online_ids, limit],
            timeout_ms=2000,
            default=[],
        )
        if rows:
            by_id = {str(row.get("id")): row for row in rows if row.get("id")}
            return [
                {
                    "id": pid,
                    "username": by_id[pid].get("username"),
                    "display_name": by_id[pid].get("display_name") or by_id[pid].get("username"),
                    "avatar_url": by_id[pid].get("avatar_url") or "",
                }
                for pid in online_ids if pid in by_id
            ][:limit]

    rows = fast_query(
        f"""
        SELECT p.id, p.username, p.display_name, p.avatar_url
        FROM chain_presence cp
        JOIN chain_profiles p ON p.id = cp.profile_id
        WHERE p.deleted_at IS NULL
          AND {public_profile_sql('p')}
          AND LOWER(COALESCE(cp.status, 'offline')) = 'online'
          AND COALESCE(cp.last_seen_at, cp.updated_at) >= NOW() - interval '5 minutes'
        ORDER BY COALESCE(cp.last_seen_at, cp.updated_at) DESC
        LIMIT %s
        """,
        [limit],
        timeout_ms=2500,
        default=[],
    )
    return [
        {
            "id": row.get("id"),
            "username": row.get("username"),
            "display_name": row.get("display_name") or row.get("username"),
            "avatar_url": row.get("avatar_url") or "",
        }
        for row in rows or [] if row.get("id")
    ]


def _build_homepage_contract(viewer_id=None, limit=20, tab="for_you", include_widgets=True, cold_start=False):
    timings = {}
    fast_payload = _timed_section(
        "posts",
        timings,
        lambda: _fast_homepage_feed_payload(
            limit=limit,
            viewer_id=viewer_id,
            cold_start=cold_start,
        ) or _minimal_feed_payload(),
    )

    stories = _timed_section("stories", timings, lambda: [_normalize_story_item(item) for item in filter_content(fast_payload.get("stories") or [])])
    posts = _timed_section("posts_normalize", timings, lambda: [_normalize_content_item(item, "post") for item in filter_content(fast_payload.get("feed_items") or [])])
    reels = _timed_section(
        "reels",
        timings,
        lambda: [
            _normalize_content_item(item, "reel")
            for item in filter_content(fast_payload.get("reels") or [])
            if item.get("video_url") or item.get("media_type") == "video" or item.get("is_video")
        ],
    )

    trending_hashtags = []
    live_rooms = fast_payload.get("live_rooms") or []
    suggested_creators = fast_payload.get("suggested_creators") or []
    online_users = []
    unread_messages = 0
    coins = 0

    if include_widgets:
        widget_payload = _get_homepage_widgets(
            viewer_id=viewer_id, posts=posts, reels=reels, stories=stories,
            _prefetched_live_rooms=live_rooms,
            _prefetched_suggestions=suggested_creators,
        )
        timings.update(widget_payload.get("timings") or {})
        live_rooms = widget_payload.get("live_rooms") or live_rooms
        suggested_creators = widget_payload.get("suggested_creators") or suggested_creators
        trending_hashtags = widget_payload.get("trending_hashtags") or []
        online_users = widget_payload.get("online_users") or []
        unread_messages = _safe_int((widget_payload.get("counts") or {}).get("unread_messages"))
        coins = _safe_int((widget_payload.get("counts") or {}).get("coins"))

    feed_items = list(posts)
    if tab == "live":
        feed_items = []
    elif tab == "trending":
        feed_items = list(posts)
    elif tab == "following" and viewer_id:
        feed_items = [item for item in posts if item.get("privacy") != "public"] + [item for item in posts if item.get("privacy") == "public"]

    payload = {
        "success": True,
        "posts": posts,
        "reels": reels,
        "stories": stories,
        "live_rooms": live_rooms,
        "suggested_creators": suggested_creators,
        "trending_hashtags": trending_hashtags,
        "online_users": online_users,
        "counts": {
            "live_now": len(live_rooms),
            "unread_messages": unread_messages if viewer_id else 0,
            "coins": coins if viewer_id else 0,
        },
        "feed_items": feed_items,
        "feed_for_you": list(feed_items),
        "suggested_people": list(suggested_creators),
        "homepage_degraded": bool(fast_payload.get("homepage_degraded")),
        "timings": timings,
        "empty_states": {
            "feed": not bool(feed_items),
            "stories": not bool(stories),
            "reels": not bool(reels),
            "live": not bool(live_rooms),
            "suggested": not bool(suggested_creators),
            "hashtags": not bool(trending_hashtags),
        },
    }
    return payload

def warm_homepage_cache():
    """Populate the in-memory cache in background (called on first request)."""
    try:
        payload = _fast_homepage_feed_payload(limit=20, viewer_id=None)
        if payload and payload.get("feed_items"):
            return True
    except Exception:
        pass
    return False

def _fast_homepage_feed_payload(limit=20, viewer_id=None, cold_start=False):
    started = time.perf_counter()
    budget_seconds = 30.0

    # In-memory cache for anonymous homepage
    now = time.time()
    if not viewer_id and _HOMEPAGE_CACHE["payload"] and now < _HOMEPAGE_CACHE["expires_at"]:
        return _HOMEPAGE_CACHE["payload"]

    payload = _minimal_feed_payload()
    stage_timings = {}

    # Run all fetches in parallel via ThreadPoolExecutor
    timeout_s = 10.0 if cold_start else max(1.0, min(2.5, budget_seconds - (time.perf_counter() - started)))
    import threading
    _results = {}
    _lock = threading.Lock()

    def _fetch_stories():
        try:
            stage_started = time.perf_counter()
            s, _, _ = fetch_stories_v2(
                ["id", "profile_id", "caption", "thumbnail_url", "media_url", "video_url", "mime_type", "created_at"],
                timeout_ms=2500 if cold_start else 5000, limit=min(limit, 4 if cold_start else 8), viewer_id=viewer_id,
            )
            with _lock: _results["stories"] = s[: min(limit, 4 if cold_start else 8)] if s else []
            stage_timings["stories"] = round((time.perf_counter() - stage_started) * 1000, 2)
        except Exception:
            with _lock: _results["stories"] = []
            stage_timings["stories"] = round((time.perf_counter() - stage_started) * 1000, 2)

    def _fetch_posts():
        try:
            stage_started = time.perf_counter()
            p, _, _ = fetch_posts_v2(
                ["id", "profile_id", "caption", "content", "body", "thumbnail_url", "media_url", "video_url", "mime_type", "post_type", "likes_count", "comments_count", "views_count", "shares_count", "created_at"],
                timeout_ms=1200 if cold_start else 5000, limit=min(limit, 2 if cold_start else 12), viewer_id=viewer_id, include_ads=not cold_start, return_raw=cold_start,
            )
            with _lock:
                _results["feed_items_raw" if cold_start else "feed_items"] = p[: min(limit, 2 if cold_start else 12)] if p else []
            stage_timings["posts"] = round((time.perf_counter() - stage_started) * 1000, 2)
        except Exception:
            with _lock:
                _results["feed_items_raw" if cold_start else "feed_items"] = []
            stage_timings["posts"] = round((time.perf_counter() - stage_started) * 1000, 2)

    def _fetch_reels():
        try:
            stage_started = time.perf_counter()
            r, _, _ = fetch_reels_v2(
                ["id", "profile_id", "caption", "thumbnail_url", "media_url", "video_url", "mime_type", "likes_count", "comments_count", "views_count", "shares_count", "music_title", "created_at"],
                timeout_ms=1000 if cold_start else 5000, limit=min(limit, 1 if cold_start else 8), viewer_id=viewer_id, return_raw=cold_start,
            )
            with _lock:
                _results["reels_raw" if cold_start else "reels"] = r[: min(limit, 1 if cold_start else 8)] if r else []
            stage_timings["reels"] = round((time.perf_counter() - stage_started) * 1000, 2)
        except Exception:
            with _lock:
                _results["reels_raw" if cold_start else "reels"] = []
            stage_timings["reels"] = round((time.perf_counter() - stage_started) * 1000, 2)

    def _fetch_live():
        try:
            stage_started = time.perf_counter()
            lr, _, _ = fetch_live_rooms_v2(
                ["id", "profile_id", "category", "status", "is_live", "viewer_count", "cover_url", "thumbnail_url", "entry_fee", "created_at"],
                timeout_ms=2000 if cold_start else 5000, limit=min(limit, 4 if cold_start else 5),
            )
            with _lock: _results["live_rooms"] = lr[: min(limit, 4 if cold_start else 5)] if lr else []
            stage_timings["live_rooms"] = round((time.perf_counter() - stage_started) * 1000, 2)
        except Exception:
            with _lock: _results["live_rooms"] = []
            stage_timings["live_rooms"] = round((time.perf_counter() - stage_started) * 1000, 2)

    def _fetch_suggested():
        try:
            stage_started = time.perf_counter()
            sc, _ = fetch_suggested_people_v2(
                ["id", "username", "display_name", "avatar_url", "profile_photo", "is_verified", "verified", "followers_count", "town", "location", "is_online", "profile_score", "profile_level"],
                timeout_ms=1500 if cold_start else 5000, limit=min(limit, 4 if cold_start else 5),
            )
            with _lock:
                _results["suggested_creators"] = sc[: min(limit, 4 if cold_start else 5)] if sc else []
            stage_timings["suggested_creators"] = round((time.perf_counter() - stage_started) * 1000, 2)
        except Exception:
            with _lock: _results["suggested_creators"] = []
            stage_timings["suggested_creators"] = round((time.perf_counter() - stage_started) * 1000, 2)

    def _fetch_activity():
        if cold_start:
            with _lock:
                _results["friend_activity"] = []
            stage_timings["friend_activity"] = 0.0
            return
        try:
            stage_started = time.perf_counter()
            act = _fetch_friend_activity(viewer_id=viewer_id, limit=10)
            with _lock: _results["friend_activity"] = list(act) if act else []
            stage_timings["friend_activity"] = round((time.perf_counter() - stage_started) * 1000, 2)
        except Exception:
            with _lock: _results["friend_activity"] = []
            stage_timings["friend_activity"] = round((time.perf_counter() - stage_started) * 1000, 2)

    jobs = [_fetch_posts, _fetch_reels]
    if not cold_start:
        jobs.insert(0, _fetch_stories)
        jobs.extend([_fetch_live, _fetch_suggested, _fetch_activity])
    exe = ThreadPoolExecutor(max_workers=len(jobs))
    fs = [exe.submit(job) for job in jobs]
    try:
        try:
            for f in as_completed(fs, timeout=timeout_s):
                try:
                    f.result()
                except Exception:
                    pass
        except FuturesTimeoutError:
            for f in fs:
                if not f.done():
                    f.cancel()
            fast_payload_timeout = True
        else:
            fast_payload_timeout = False
    finally:
        exe.shutdown(wait=False, cancel_futures=True)

    payload["stories"] = _results.get("stories") or []
    if cold_start:
        raw_posts = _results.get("feed_items_raw") or []
        raw_reels = _results.get("reels_raw") or []
        shared_profile_ids = []
        seen_profile_ids = set()
        for row in list(raw_posts) + list(raw_reels):
            pid = row.get("profile_id") if isinstance(row, dict) else None
            if pid and pid not in seen_profile_ids:
                seen_profile_ids.add(pid)
                shared_profile_ids.append(pid)
        profile_batch_started = time.perf_counter()
        shared_profile_map = fetch_profiles_batch(shared_profile_ids, timeout_ms=5000) if shared_profile_ids else {}
        stage_timings["profile_batch"] = round((time.perf_counter() - profile_batch_started) * 1000, 2)
        posts = [normalize_post_v2(row, shared_profile_map) for row in raw_posts if isinstance(row, dict) and row.get("id")]
        reels = [normalize_post_v2(row, shared_profile_map) for row in raw_reels if isinstance(row, dict) and row.get("id")]
        payload["feed_items"] = [row for row in posts if row.get("id")]
        payload["reels"] = [row for row in reels if row.get("id")]
    else:
        payload["feed_items"] = _results.get("feed_items") or []
        payload["reels"] = _results.get("reels") or []
    payload["live_rooms"] = _results.get("live_rooms") or []
    suggested = _results.get("suggested_creators") or []
    payload["suggested_creators"] = list(suggested)
    payload["suggested_users"] = list(suggested)
    payload["recommended_profiles"] = list(suggested)
    payload["friend_activity"] = _results.get("friend_activity") or []

    payload["trending_posts"] = list(payload.get("feed_items") or [])
    payload = rank_homepage_sections(payload, viewer_id=viewer_id, feed_limit=limit)

    payload["homepage_degraded"] = not bool(payload.get("feed_items") or payload.get("stories") or payload.get("reels"))
    if fast_payload_timeout and not payload["homepage_degraded"]:
        payload["homepage_degraded"] = False

    # Store in in-memory cache for anonymous users
    if not viewer_id:
        _HOMEPAGE_CACHE["payload"] = payload
        _HOMEPAGE_CACHE["expires_at"] = time.time() + _HOMEPAGE_CACHE_TTL

    log_info(
        "homepage_feed_stage_timing",
        viewer_authenticated=bool(viewer_id),
        cold_start=bool(cold_start),
        stage_timings=stage_timings,
        feed_items=len(payload.get("feed_items") or []),
        reels=len(payload.get("reels") or []),
        stories=len(payload.get("stories") or []),
        live_rooms=len(payload.get("live_rooms") or []),
        suggested=len(payload.get("suggested_creators") or []),
    )

    return payload


def _get_homepage_widgets(viewer_id=None, posts=None, reels=None, stories=None,
                          _prefetched_live_rooms=None, _prefetched_suggestions=None):
    cached = _get_widget_cache(viewer_id)
    if cached is not None:
        return cached

    timings = {}
    results = {
        "live_rooms": [],
        "suggested_creators": [],
        "trending_hashtags": [],
        "online_users": [],
        "counts": {"live_now": 0, "unread_messages": 0, "coins": 0},
        "notifications": [],
        "wallet": {"coin_balance": 0, "label_balance": "0"},
        "timings": timings,
    }

    def build_hashtags():
        hashtag_counts = {}
        for collection in (posts or [], reels or [], stories or []):
            for item in collection:
                for tag, count in _extract_hashtags(item.get("caption"), item.get("body"), item.get("title")).items():
                    hashtag_counts[tag] = hashtag_counts.get(tag, 0) + count
        return [
            {"tag": tag, "hashtag": tag, "count": count, "posts_count": count}
            for tag, count in sorted(hashtag_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:8]
        ]

    def fetch_live():
        if _prefetched_live_rooms:
            results["live_rooms"] = [_normalize_live_room_item(item) for item in _prefetched_live_rooms]
            results["counts"]["live_now"] = len(results["live_rooms"])
            timings["live"] = 0
            return
        live_rows = _timed_section(
            "live",
            timings,
            lambda: fetch_live_rooms_v2(
                ["id", "profile_id", "category", "status", "is_live", "viewer_count", "cover_url", "thumbnail_url", "entry_fee", "created_at", "title"],
                timeout_ms=1200,
                limit=5,
            )[0],
        )
        results["live_rooms"] = [_normalize_live_room_item(item) for item in live_rows or []]
        results["counts"]["live_now"] = len(results["live_rooms"])

    def fetch_suggestions():
        if _prefetched_suggestions:
            results["suggested_creators"] = [_normalize_profile_item(item) for item in filter_profiles(_prefetched_suggestions)]
            timings["suggestions"] = 0
            return
        rows = _timed_section(
            "suggestions",
            timings,
            lambda: fetch_suggested_people_v2(
                ["id", "username", "display_name", "avatar_url", "profile_photo", "is_verified", "verified", "followers_count", "town", "location", "is_online", "profile_score", "profile_level", "created_at"],
                timeout_ms=800,
                limit=5,
            )[0],
        )
        results["suggested_creators"] = [_normalize_profile_item(item) for item in filter_profiles(rows or [])]

    def fetch_online():
        results["online_users"] = _timed_section("online_users", timings, lambda: _fetch_real_online_users(limit=8))

    def fetch_hashtags():
        results["trending_hashtags"] = _timed_section("hashtags", timings, build_hashtags)

    def fetch_notifications():
        if not viewer_id:
            timings["notifications"] = 0
            return
        try:
            from services.notification_engine import list_notifications
            raw = _timed_section("notifications", timings, lambda: list_notifications(viewer_id, limit=5))
            if isinstance(raw, list):
                results["notifications"] = raw
            elif isinstance(raw, dict) and raw.get("notifications"):
                results["notifications"] = raw["notifications"]
        except Exception:
            results["notifications"] = []

    def fetch_wallet():
        if not viewer_id:
            timings["wallet"] = 0
            return
        try:
            from services.wallet_service import get_wallet
            wallet = _timed_section("wallet", timings, lambda: get_wallet(viewer_id) or {})
            coin_balance = _safe_int(wallet.get("coin_balance") or wallet.get("balance_cents"))
            results["wallet"] = {"coin_balance": coin_balance, "label_balance": str(coin_balance)}
            results["counts"]["coins"] = coin_balance
        except Exception:
            results["wallet"] = {"coin_balance": 0, "label_balance": "0"}

    def fetch_unread():
        if not viewer_id:
            timings["unread_messages"] = 0
            return
        try:
            from services.message_delivery_service import get_unread_message_count
            results["counts"]["unread_messages"] = _safe_int(_timed_section("unread_messages", timings, lambda: get_unread_message_count(viewer_id)))
        except Exception:
            results["counts"]["unread_messages"] = 0

    jobs = [fetch_live, fetch_suggestions, fetch_online, fetch_hashtags, fetch_notifications, fetch_wallet, fetch_unread]
    exe = ThreadPoolExecutor(max_workers=len(jobs))
    futures = [exe.submit(job) for job in jobs]
    try:
        for future in as_completed(futures, timeout=2.0):
            try:
                future.result()
            except Exception:
                pass
    except FuturesTimeoutError:
        for future in futures:
            if not future.done():
                future.cancel()
    finally:
        exe.shutdown(wait=False, cancel_futures=True)

    _set_widget_cache(viewer_id, results)
    return results


@homepage_api_bp.route("/api/suggestions/smart")
def api_smart_suggestions():
    profile = _current_profile()
    profile_id = profile.get("id") if profile else None
    try:
        limit = min(max(int(request.args.get("limit", 10)), 1), 20)
    except (TypeError, ValueError):
        limit = 10
    try:
        from services.smart_suggestion_service import get_smart_suggestions, build_recommendation_cards
        suggestions = get_smart_suggestions(profile_id, limit=limit)
        cards = build_recommendation_cards(profile_id, limit=3)
        return _json_ok({"suggestions": suggestions, "cards": cards})
    except Exception as error:
        return _json_error(str(error), 500)


@homepage_api_bp.route("/api/video-events", methods=["POST"])
@login_required
def api_video_events():
    profile = _current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    data = request.get_json(silent=True) or {}
    try:
        from services.video_interest_service import record_video_event
        result = record_video_event(
            viewer_profile_id=profile["id"],
            video_type=data.get("video_type") or data.get("type") or "reel",
            video_id=data.get("video_id") or data.get("id"),
            creator_profile_id=data.get("creator_profile_id"),
            event_type=data.get("event_type") or "view",
            watch_ms=data.get("watch_ms") or 0,
        )
        status = 200 if result.get("ok") else 202
        return _json_ok({"result": result}, status=status)
    except Exception as error:
        return _json_error(str(error), 500)


# ================================================================
# GET /api/home/feed — Tab-filtered feed with pagination
# ================================================================
@homepage_api_bp.route("/api/home/feed")
def api_feed():
    tab = request.args.get("tab", "for_you")
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    limit = 20

    profile = _current_profile()
    profile_id = profile.get("id") if profile else None

    try:
        items, has_more = get_feed_tab(profile_id=profile_id, tab=tab, page=page, limit=limit)
    except Exception:
        items, has_more = [], False

    return _json_ok({
        "tab": tab,
        "items": items,
        "page": page,
        "next_page": page + 1 if has_more else None,
        "has_more": has_more,
    })


# ================================================================
# POST /api/home/follow/<profile_id>
# ================================================================
@homepage_api_bp.route("/api/home/follow/<profile_id>", methods=["POST"])
@login_required
def api_follow(profile_id):
    profile = _current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    if str(profile["id"]) == str(profile_id):
        return _json_error("Cannot follow yourself")
    from services.follow_request_service import send_follow_request
    result = send_follow_request(str(profile["id"]), str(profile_id))
    if result.get("ok") or result.get("success"):
        track_interaction_safe(str(profile["id"]), "profile", str(profile_id), "follow", source_surface="homepage")
    return _json_ok({"result": result})


# ================================================================
# POST /api/home/unfollow/<profile_id>
# ================================================================
@homepage_api_bp.route("/api/home/unfollow/<profile_id>", methods=["POST"])
@login_required
def api_unfollow(profile_id):
    profile = _current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    if str(profile["id"]) == str(profile_id):
        return _json_error("Cannot unfollow yourself")
    result = unfollow_profile(str(profile["id"]), str(profile_id))
    if result.get("success"):
        track_interaction_safe(str(profile["id"]), "profile", str(profile_id), "unfollow", source_surface="homepage")
    return _json_ok({"result": result})


# ================================================================
# POST /api/home/post/<post_id>/like
# ================================================================
@homepage_api_bp.route("/api/home/post/<post_id>/like", methods=["POST"])
@login_required
def api_like_post(post_id):
    profile = _current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    try:
        result = toggle_like(str(profile["id"]), "post", str(post_id))
        if not result.get("success"):
            return _json_error(result.get("error") or "Could not update like.", 503)
        liked = bool(result.get("liked"))
        likes_count = int(result.get("count") or result.get("likes_count") or result.get("like_count") or 0)
        track_interaction_safe(
            str(profile["id"]),
            "post",
            str(post_id),
            "like" if liked else "unlike",
            source_surface="homepage",
        )
        try:
            from engines.cache_engine import delete_cache, cache_key
            delete_cache(cache_key(f"homepage:v2:posts:viewer:{profile['id']}"))
        except Exception:
            pass
        return jsonify({
            "ok": True,
            "liked": liked,
            "likes_count": likes_count,
            "is_liked": liked,
            "user_liked": liked,
            "count": likes_count,
            "result": result,
        }), 200
    except Exception as e:
        return _json_error(str(e), 500)


@homepage_api_bp.route("/api/home/likes-state", methods=["GET"])
@login_required
def api_home_likes_state():
    profile = _current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    entity_type = (request.args.get("type") or "post").strip().lower()
    raw_ids = request.args.get("ids") or ""
    entity_ids = []
    for value in raw_ids.split(","):
        clean = value.strip()
        if clean and clean not in entity_ids:
            entity_ids.append(clean)
        if len(entity_ids) >= 50:
            break
    if entity_type not in {"post", "reel"}:
        return _json_error("Unsupported entity type", 400)
    if not entity_ids:
        return _json_ok({"type": entity_type, "liked_ids": [], "liked_map": {}})
    liked_ids = fetch_liked_entity_ids(entity_type, str(profile["id"]), entity_ids, timeout_ms=5000)
    liked_map = {entity_id: (entity_id in liked_ids) for entity_id in entity_ids}
    return _json_ok({
        "type": entity_type,
        "liked_ids": sorted(liked_ids),
        "liked_map": liked_map,
    })


# ================================================================
# POST /api/home/post/<post_id>/save
# ================================================================
@homepage_api_bp.route("/api/home/post/<post_id>/save", methods=["POST"])
@login_required
def api_save_post(post_id):
    profile = _current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    try:
        result = toggle_save(str(profile["id"]), "post", str(post_id))
        if result.get("success"):
            track_interaction_safe(
                str(profile["id"]),
                "post",
                str(post_id),
                "save" if result.get("saved") else "unsave",
                source_surface="homepage",
            )
        return _json_ok({"result": result})
    except Exception as e:
        return _json_error(str(e), 500)


# ================================================================
# POST /api/home/post/<post_id>/share
# ================================================================
@homepage_api_bp.route("/api/home/post/<post_id>/share", methods=["POST"])
@login_required
def api_share_post(post_id):
    profile = _current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    try:
        from services.engagement_service import _first
        post = _first("chain_posts", {"id": str(post_id)})
        new_count = (post.get("shares_count") or 0) + 1 if post else 1
        from services.supabase_safe import safe_update
        safe_update("chain_posts", {"shares_count": new_count}, {"id": str(post_id)})
        track_interaction_safe(str(profile["id"]), "post", str(post_id), "share", source_surface="homepage")
        return _json_ok({"shares_count": new_count})
    except Exception as e:
        return _json_error(str(e), 500)


# ================================================================
# POST /api/home/post/<post_id>/comment
# GET  /api/home/post/<post_id>/comments
# ================================================================
@homepage_api_bp.route("/api/home/post/<post_id>/comment", methods=["POST"])
@login_required
def api_comment_post(post_id):
    profile = _current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    try:
        body = request.get_json(silent=True) or {}
        text = body.get("body") or request.form.get("body") or ""
        if not text.strip():
            return _json_error("Comment cannot be empty", 400)
        from services.engagement_service import add_comment
        result = add_comment(str(profile["id"]), "post", str(post_id), text.strip())
        if result.get("success"):
            track_interaction_safe(str(profile["id"]), "post", str(post_id), "comment", source_surface="homepage")
        return _json_ok({"result": result})
    except Exception as e:
        return _json_error(str(e), 500)


@homepage_api_bp.route("/api/home/post/<post_id>/comments", methods=["GET"])
@login_required
def api_list_comments(post_id):
    profile = _current_profile()
    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), 50)
    except (TypeError, ValueError):
        limit = 20
    try:
        from services.engagement_service import list_comments
        comments = list_comments("post", str(post_id), limit=limit)
        return _json_ok({"comments": comments or []})
    except Exception as e:
        return _json_error(str(e), 500)


# ================================================================
# POST /api/home/post/<post_id>/react
# ================================================================
@homepage_api_bp.route("/api/home/post/<post_id>/react", methods=["POST"])
@login_required
def api_react_post(post_id):
    profile = _current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    try:
        body = request.get_json(silent=True) or {}
        reaction = body.get("reaction") or "like"
        from services.engagement_service import react_to_post
        result = react_to_post(str(profile["id"]), str(post_id), reaction)
        return _json_ok({"result": result})
    except Exception as e:
        return _json_error(str(e), 500)


# ================================================================
# Phase 120 — Premium Homepage JSON Endpoints
# ================================================================

@homepage_api_bp.route("/api/homepage/feed")
def api_homepage_feed():
    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), 50)
    except (TypeError, ValueError):
        limit = 20
    tab = (request.args.get("tab") or "for_you").strip().lower()
    profile = _current_profile()
    viewer_id = profile.get("id") if profile else None
    try:
        if not viewer_id:
            snapshot = _cached_public_homepage_snapshot()
            payload = _homepage_response_from_snapshot(snapshot, viewer_id=None, limit=limit, tab=tab)
        else:
            payload = None
        if payload is None:
            payload = _build_homepage_contract(viewer_id=viewer_id, limit=limit, tab=tab, include_widgets=False)
        has_data = bool(payload.get("posts") or payload.get("reels") or payload.get("stories") or payload.get("live_rooms"))
        if not has_data:
            payload = _safe_degraded_homepage_payload()
        return jsonify({
            "ok": True,
            "success": True,
            "degraded": not has_data,
            "payload": payload,
            **payload,
        }), 200
    except Exception as e:
        payload = _safe_degraded_homepage_payload()
        return jsonify({
            "ok": True,
            "success": True,
            "degraded": True,
            "payload": payload,
            **payload,
            "warning": str(e),
        }), 200


@homepage_api_bp.route("/api/homepage/sidebar")
def api_homepage_sidebar():
    profile = _current_profile()
    profile_id = profile.get("id") if profile else None
    try:
        if not profile_id:
            snapshot = _cached_public_homepage_snapshot()
            contract = _homepage_response_from_snapshot(snapshot, viewer_id=None, limit=12, tab="for_you") or {}
        else:
            contract = _build_homepage_contract(viewer_id=profile_id, limit=12)
        payload = get_homepage_sidebar_payload(profile_id=profile_id)
        payload["live_rooms"] = contract.get("live_rooms") or payload.get("live_rooms", [])
        payload["suggested_creators"] = contract.get("suggested_creators") or payload.get("suggested_creators", [])
        payload["suggested_users"] = payload["suggested_creators"]
        payload["trending_hashtags"] = contract.get("trending_hashtags") or []
        payload["online_users"] = contract.get("online_users") or []
        payload["counts"] = contract.get("counts") or {}
        payload["timings"] = contract.get("timings") or {}
        return _json_ok(payload)
    except Exception as e:
        return _json_error(str(e), 500)


@homepage_api_bp.route("/api/homepage/widgets")
def api_homepage_widgets():
    profile = _current_profile()
    viewer_id = profile.get("id") if profile else None
    try:
        if not viewer_id:
            snapshot = _cached_public_homepage_snapshot()
            contract = _homepage_response_from_snapshot(snapshot, viewer_id=None, limit=12, tab="for_you") or {}
            widget_payload = {"notifications": [], "wallet": {"coin_balance": 0, "label_balance": "0"}}
        else:
            contract = _build_homepage_contract(viewer_id=viewer_id, limit=12)
            widget_payload = _get_homepage_widgets(viewer_id=viewer_id)
        return _json_ok({
            "live_rooms": contract.get("live_rooms") or [],
            "suggested_creators": contract.get("suggested_creators") or [],
            "suggested_people": contract.get("suggested_people") or [],
            "trending_hashtags": contract.get("trending_hashtags") or [],
            "online_users": contract.get("online_users") or [],
            "counts": contract.get("counts") or {},
            "notifications": widget_payload.get("notifications") or [],
            "wallet": widget_payload.get("wallet") or {"coin_balance": 0, "label_balance": "0"},
            "timings": contract.get("timings") or {},
        })
    except Exception as e:
        return _json_error(str(e), 500)


@homepage_api_bp.route("/api/homepage/stories")
def api_homepage_stories():
    profile = _current_profile()
    profile_id = profile.get("id") if profile else None
    try:
        stories, _, _ = fetch_stories_v2(
            ["id", "profile_id", "caption", "thumbnail_url", "media_url", "video_url", "mime_type", "created_at", "duration_seconds", "background_color", "text_content", "views_count", "visibility"],
            timeout_ms=1200,
            limit=12,
            viewer_id=profile_id,
        )
        return _json_ok({"stories": stories or []})
    except Exception as e:
        return _json_error(str(e), 500)


@homepage_api_bp.route("/api/homepage/reels")
def api_homepage_reels():
    profile = _current_profile()
    profile_id = profile.get("id") if profile else None
    try:
        reels, _, _ = fetch_reels_v2(
            ["id", "profile_id", "caption", "thumbnail_url", "media_url", "video_url", "mime_type", "created_at", "likes_count", "comments_count", "visibility"],
            timeout_ms=1200,
            limit=8,
            viewer_id=profile_id,
        )
        return _json_ok({"reels": reels or []})
    except Exception as e:
        return _json_error(str(e), 500)


# ================================================================
# GET /api/feed — Smart feed preload (feed_preload_service)
# ================================================================
@feed_preload_bp.route("/api/feed")
def api_feed_preload():
    cursor = request.args.get("cursor") or None
    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), 50)
    except (TypeError, ValueError):
        limit = 20
    profile = _current_profile()
    profile_id = profile.get("id") if profile else None
    try:
        from services.feed_preload_service import get_mixed_feed
        payload = get_mixed_feed(profile_id=profile_id, cursor=cursor, limit=limit)
        return _json_ok({
            "degraded": False,
            "payload": payload,
        })
    except Exception as e:
        return _json_ok({
            "degraded": True,
            "payload": {
                "stories": [],
                "feed_items": [],
                "reels": [],
                "ads": [],
                "next_cursor": None,
                "has_more": False,
            },
            "warning": str(e),
        })
