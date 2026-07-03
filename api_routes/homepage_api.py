"""Phase 59 — Real Feed API + Follow + Like/Save/Share actions.
   Phase 120 — Premium Homepage JSON endpoints."""

import os
import time
from flask import Blueprint, jsonify, request, session
from services.profile_service import get_current_profile
from services.homepage_service import (
    get_feed_tab,
    get_homepage_payload,
    get_homepage_sidebar_payload,
    rank_homepage_sections,
    _fetch_friend_activity,
)
from services.homepage_phase141_service import (
    fetch_posts_v2,
    fetch_reels_v2,
    fetch_stories_v2,
    fetch_live_rooms_v2,
    fetch_suggested_people_v2,
)
from services.engagement_service import follow_profile, unfollow_profile, toggle_like, toggle_save
from services.neon_service import fast_query, is_circuit_open
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
        "homepage_degraded": True,
        "feed_items": [],
        "feed_for_you": [],
        "posts": [],
        "reels": [],
        "stories": [],
        "live_rooms": [],
        "suggested_people": [],
        "suggested_creators": [],
        "trending_hashtags": [],
        "friend_activity": [],
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


def _fast_homepage_feed_payload(limit=20, viewer_id=None):
    started = time.perf_counter()
    budget_seconds = 60.0
    payload = _minimal_feed_payload()

    def budget_left():
        return budget_seconds - (time.perf_counter() - started)

    try:
        stories, _, _ = fetch_stories_v2(
            ["id", "profile_id", "caption", "thumbnail_url", "media_url", "video_url", "mime_type", "created_at"],
            timeout_ms=20000,
            limit=min(limit, 8),
            viewer_id=viewer_id,
        )
        if budget_left() > 0:
            payload["stories"] = stories[: min(limit, 8)]
    except Exception:
        return _safe_degraded_homepage_payload()

    if budget_left() <= 0:
        return _safe_degraded_homepage_payload()

    try:
        posts, _, _ = fetch_posts_v2(
            ["id", "profile_id", "caption", "content", "body", "thumbnail_url", "media_url", "video_url", "mime_type", "post_type", "likes_count", "comments_count", "views_count", "shares_count", "created_at"],
            timeout_ms=20000,
            limit=min(limit, 12),
            viewer_id=viewer_id,
        )
        if budget_left() > 0:
            payload["feed_items"] = posts[: min(limit, 12)]
    except Exception:
        return _safe_degraded_homepage_payload()

    if budget_left() <= 0:
        return _safe_degraded_homepage_payload()

    try:
        reels, _, _ = fetch_reels_v2(
            ["id", "profile_id", "caption", "thumbnail_url", "media_url", "video_url", "mime_type", "likes_count", "comments_count", "views_count", "shares_count", "music_title", "created_at"],
            timeout_ms=20000,
            limit=min(limit, 8),
            viewer_id=viewer_id,
        )
        if budget_left() > 0:
            payload["reels"] = reels[: min(limit, 8)]
    except Exception:
        return _safe_degraded_homepage_payload()

    try:
        live_rooms, _, _ = fetch_live_rooms_v2(
            ["id", "profile_id", "category", "status", "is_live", "viewer_count", "cover_url", "thumbnail_url", "entry_fee", "created_at"],
            timeout_ms=20000,
            limit=min(limit, 5),
        )
        if budget_left() > 0:
            payload["live_rooms"] = live_rooms[: min(limit, 5)]
    except Exception:
        payload["live_rooms"] = []

    try:
        suggested_creators, _ = fetch_suggested_people_v2(
            ["id", "username", "display_name", "avatar_url", "profile_photo", "is_verified", "verified", "followers_count", "town", "location"],
            timeout_ms=20000,
            limit=min(limit, 5),
        )
        if budget_left() > 0:
            payload["suggested_creators"] = suggested_creators[: min(limit, 5)]
            payload["suggested_users"] = list(payload["suggested_creators"])
            payload["recommended_profiles"] = list(payload["suggested_creators"])
    except Exception:
        payload["suggested_creators"] = []

    # ── Friend activity ──
    try:
        activity = _fetch_friend_activity(viewer_id=viewer_id, limit=10)
        if activity:
            payload["friend_activity"] = activity
    except Exception:
        payload["friend_activity"] = []

    payload["trending_posts"] = list(payload.get("feed_items") or [])
    payload = rank_homepage_sections(payload, viewer_id=viewer_id, feed_limit=limit)

    payload["homepage_degraded"] = not bool(payload.get("feed_items") or payload.get("stories") or payload.get("reels"))
    return payload


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
        return _json_ok({"result": result})
    except Exception as e:
        return _json_error(str(e), 500)


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
        return _json_ok({"shares_count": new_count})
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
    profile = _current_profile()
    viewer_id = profile.get("id") if profile else None
    try:
        started = time.perf_counter()
        payload = _fast_homepage_feed_payload(limit=limit, viewer_id=viewer_id)
        elapsed = time.perf_counter() - started
        has_data = bool(payload.get("feed_items") or payload.get("stories") or payload.get("reels"))
        if not has_data:
            payload = _safe_degraded_homepage_payload()
        return _json_ok({
            "degraded": not has_data,
            "payload": payload,
        })
    except Exception as e:
        return _json_ok({
            "degraded": True,
            "payload": _safe_degraded_homepage_payload(),
            "warning": str(e),
        })


@homepage_api_bp.route("/api/homepage/sidebar")
def api_homepage_sidebar():
    profile = _current_profile()
    profile_id = profile.get("id") if profile else None
    try:
        live_rooms, _, _ = fetch_live_rooms_v2(
            ["id", "profile_id", "category", "status", "is_live", "viewer_count", "cover_url", "thumbnail_url", "entry_fee", "created_at"],
            timeout_ms=1200,
            limit=5,
        )
        suggested_creators, _ = fetch_suggested_people_v2(
            ["id", "username", "display_name", "avatar_url", "profile_photo", "is_verified", "verified", "followers_count", "town", "location"],
            timeout_ms=800,
            limit=5,
        )
        payload = get_homepage_sidebar_payload(profile_id=profile_id)
        payload["live_rooms"] = live_rooms or payload.get("live_rooms", [])
        payload["suggested_creators"] = suggested_creators or payload.get("suggested_creators", [])
        payload["suggested_users"] = payload["suggested_creators"]
        return _json_ok(payload)
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
