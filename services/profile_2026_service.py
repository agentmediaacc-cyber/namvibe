import time
import uuid
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps

from engines.cache_engine import cache_key, get_cache, set_cache, delete_cache
from services.profile_service import get_profile_by_id, get_profile_by_username, get_profile_stats, get_profile_bundle, get_mutual_friends_summary, get_recently_active_friends, build_profile_strength, get_wallet_snapshot, get_creator_tools, get_profile_counts
from services.presence_service import get_presence, presence_label, get_many_presence
from services.relationship_cache_service import get_relationship_state
from services.relationship_gate_service import can_message, can_call
from services.profile_view_service import build_profile_view_model
from services.profile_dashboard_service import build_profile_dashboard
from services.gallery_service import get_profile_gallery, get_profile_media_stats
from services.reels_engine import get_creator_reel_stats
from services.stories_engine import get_stories_by_creator, get_highlights, get_creator_story_stats
from services.live_engine import get_live_room, get_creator_live_analytics
from services.creator_studio_service import get_studio_dashboard
from services.friend_service import get_mutual_friends, list_friends
from services.activity_engine import get_recent_activity, emit_activity
from services.performance_monitor import track_timing
from services.neon_service import fast_query

PROFILE_CACHE_TTL = 30
CONTENT_CACHE_TTL = 20


def _track_op(name):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                track_timing(f"profile.{name}.ms", round((time.perf_counter() - start) * 1000, 2))
                return result
            except Exception as e:
                track_timing(f"profile.{name}.error.ms", round((time.perf_counter() - start) * 1000, 2))
                return {"ok": False, "error": str(e)}
        return wrapper
    return decorator


def _uuid_or_none(val):
    if not val:
        return None
    try:
        return str(uuid.UUID(str(val)))
    except (TypeError, ValueError):
        return None


def _resolve_target(target):
    """Resolve a username or ID to a profile dict."""
    if not target:
        return None
    uid = _uuid_or_none(target)
    if uid:
        return get_profile_by_id(uid)
    uname = str(target).lstrip("@").lower()
    return get_profile_by_username(uname)


def _initials(name):
    if not name:
        return "?"
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return (name[0] + "?").upper() if len(name) >= 1 else "?"


def _relative_time(dt):
    if not dt:
        return "offline"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return "offline"
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    secs = int(diff.total_seconds())
    if secs < 0:
        return "now"
    if secs < 60:
        return "active now"
    mins = secs // 60
    if mins < 60:
        return f"active {mins}m ago"
    hrs = mins // 60
    if hrs < 24:
        return f"active {hrs}h ago"
    days = hrs // 24
    return f"active {days}d ago"


def _joined_date(profile):
    created = profile.get("created_at") or profile.get("date_joined")
    if not created:
        return "Recently"
    try:
        if isinstance(created, str):
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        else:
            dt = created
        return dt.strftime("%b %Y")
    except (ValueError, TypeError):
        return "Recently"


def _location(profile):
    parts = []
    for key in ("town", "city", "region", "country", "location"):
        val = profile.get(key)
        if val and isinstance(val, str) and val.strip():
            parts.append(val.strip())
    return ", ".join(parts) if parts else ""


def _safe_int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


# ─── Main profile view model ───

@_track_op("overview")
def get_profile_2026(viewer_id, target):
    """Build a complete profile view model.

    Args:
        viewer_id: str or None (unauthenticated)
        target: str (username with or without @) or UUID string

    Returns:
        dict with ok, data (profile view model) or error
    """
    start = time.perf_counter()

    # Resolve target
    profile = _resolve_target(target)
    if not profile:
        return {"ok": False, "error": "Profile not found"}

    pid = profile.get("id")
    if not pid:
        return {"ok": False, "error": "Invalid profile"}

    viewer_id = _uuid_or_none(viewer_id) if viewer_id else None
    is_self = viewer_id and viewer_id == pid

    # Batch-load in parallel
    executor = ThreadPoolExecutor(max_workers=8)
    futures = {}

    # Profile basics
    futures["stats"] = executor.submit(get_profile_counts, pid)
    futures["presence"] = executor.submit(get_presence, pid)

    if is_self:
        futures["wallet"] = executor.submit(get_wallet_snapshot, pid)
        futures["creator_tools"] = executor.submit(get_creator_tools, pid)
        futures["studio"] = executor.submit(get_studio_dashboard, pid)

    if viewer_id and not is_self:
        futures["relationship"] = executor.submit(get_relationship_state, viewer_id, pid)
        futures["mutual_friends"] = executor.submit(get_mutual_friends, viewer_id, pid, 6, 0)
        futures["recently_active"] = executor.submit(get_recently_active_friends, pid, 6)

    # Content previews
    futures["gallery"] = executor.submit(get_profile_gallery, pid, viewer_id or pid, None, None, 1, 6)
    futures["reel_stats"] = executor.submit(get_creator_reel_stats, pid, viewer_id or pid)
    futures["story_stats"] = executor.submit(get_creator_story_stats, pid, viewer_id or pid)
    futures["highlights"] = executor.submit(get_highlights, pid, viewer_id or pid)

    if viewer_id:
        futures["stories"] = executor.submit(get_stories_by_creator, pid, viewer_id, 6)
    else:
        futures["stories"] = executor.submit(get_stories_by_creator, pid, pid, 6)

    futures["live_analytics"] = executor.submit(get_creator_live_analytics, pid, 3)

    # Activity
    futures["activity"] = executor.submit(get_recent_activity, pid, 10)

    # Collect results
    results = {}
    for key, future in futures.items():
        try:
            results[key] = future.result(timeout=5)
        except Exception:
            results[key] = None

    executor.shutdown(wait=False)

    # ─── Build view model ───

    stats = results.get("stats") or {}
    presence = results.get("presence") or {}
    relationship = results.get("relationship") or {}
    mutual_friends = results.get("mutual_friends") or []
    recently_active = results.get("recently_active") or []
    wallet = results.get("wallet") or {}
    creator_tools = results.get("creator_tools") or {}
    studio = results.get("studio") or {}
    gallery_result = results.get("gallery") or ([], 0)
    gallery_items = gallery_result[0] if isinstance(gallery_result, tuple) else []
    reel_stats = results.get("reel_stats") or {}
    story_stats = results.get("story_stats") or {}
    highlights = results.get("highlights") or []
    stories = results.get("stories") or []
    live_analytics = results.get("live_analytics") or {}
    activity = results.get("activity") or []

    # Online state
    is_online = bool(presence and presence.get("state") == "online")
    last_active_raw = presence.get("updated_at") if presence else None
    state_label = presence_label(pid) if presence else "offline"

    # Stats
    posts_count = _safe_int(profile.get("posts_count", stats.get("posts", 0)))
    reels_count = _safe_int(reel_stats.get("total_reels", stats.get("reels", 0)))
    stories_count = _safe_int(story_stats.get("total_stories", stats.get("stories", 0)))
    followers_count = _safe_int(profile.get("followers_count", stats.get("followers", 0)))
    following_count = _safe_int(profile.get("following_count", stats.get("following", 0)))
    friends_count = _safe_int(stats.get("friends", 0))
    likes_count = _safe_int(profile.get("likes_count", stats.get("likes", 0)))
    views_count = _safe_int(profile.get("views_count", stats.get("views", 0)))

    # Verification
    verified = bool(profile.get("is_verified") or profile.get("verified"))
    badge_type = "verified"
    if profile.get("is_business"):
        badge_type = "business"
    elif profile.get("is_government"):
        badge_type = "government"
    elif profile.get("is_creator") or creator_tools.get("creator_enabled"):
        badge_type = "creator" if verified else badge_type

    creator_enabled = bool(profile.get("is_creator") or creator_tools.get("creator_enabled"))

    # Profile strength
    profile_strength = 0
    if is_self:
        profile_strength = _safe_int(build_profile_strength(profile, stats))

    # Permissions
    rel = relationship.get("relationship", "stranger") if relationship else "stranger"
    is_friend = bool(relationship.get("is_friend")) if relationship else False
    is_following = bool(relationship.get("is_following")) if relationship else False
    follows_viewer = bool(relationship.get("follow_request_received")) if relationship else False
    request_sent = bool(relationship.get("friend_request_sent")) if relationship else False
    request_received = bool(relationship.get("friend_request_received")) if relationship else False
    blocked = bool(relationship.get("blocked")) if relationship else False
    restricted = False

    msg_check = can_message(viewer_id, pid) if viewer_id else {"ok": False}
    call_check = can_call(viewer_id, pid) if viewer_id else {"ok": False}

    can_message_flag = bool(msg_check.get("ok")) if isinstance(msg_check, dict) else True
    can_call_flag = bool(call_check.get("ok")) if isinstance(call_check, dict) else True

    # Gallery preview
    gallery_preview = []
    for item in gallery_items[:6]:
        if isinstance(item, dict):
            gallery_preview.append({
                "id": item.get("id"),
                "media_url": item.get("media_url") or item.get("url") or "",
                "media_type": item.get("media_type") or "image",
                "thumbnail": item.get("thumbnail") or item.get("media_url") or "",
            })

    # Live
    live_rooms = []
    live_data = live_analytics.get("analytics") if isinstance(live_analytics, dict) else {}
    if live_data and isinstance(live_data, list):
        live_rooms = [{
            "id": r.get("room_id") or r.get("id"),
            "title": r.get("title", "Live"),
            "status": r.get("status", "ended"),
            "started_at": r.get("started_at") or r.get("created_at"),
        } for r in live_data[:3] if r.get("status") == "live"]

    # Reel preview
    reels_preview = []
    reel_stats_data = reel_stats if isinstance(reel_stats, dict) else {}
    if reel_stats_data.get("total_reels", 0) > 0:
        reels_preview.append({
            "count": reel_stats_data.get("total_reels", 0),
            "total_views": reel_stats_data.get("total_views", 0),
            "total_likes": reel_stats_data.get("total_likes", 0),
        })

    # Activity
    activity_list = []
    for act in (activity or []):
        if isinstance(act, dict):
            activity_list.append({
                "event_type": act.get("event_type", ""),
                "created_at": act.get("created_at", ""),
                "metadata": act.get("metadata"),
            })
    activity_list = activity_list[:10]

    # Studio overview (self only)
    studio_overview = None
    if is_self and studio.get("ok"):
        studio_overview = studio.get("overview")

    # Builder result
    model = {
        "ok": True,

        # Identity
        "id": pid,
        "username": profile.get("username", ""),
        "display_name": profile.get("display_name", profile.get("full_name", "")),
        "initials": _initials(profile.get("display_name") or profile.get("full_name")),
        "avatar_url": profile.get("avatar_url", ""),
        "cover_url": profile.get("cover_url", ""),
        "bio": profile.get("bio", ""),
        "location": _location(profile),
        "website": profile.get("website", ""),
        "category": profile.get("category", profile.get("creator_category", "")),
        "joined": _joined_date(profile),

        # Verification
        "verified": verified,
        "badge_type": badge_type,
        "badge_label": badge_type.capitalize() if verified else "",

        # Presence
        "is_online": is_online,
        "last_active": _relative_time(last_active_raw),
        "state_label": state_label,

        # Relationship
        "is_self": is_self,
        "is_friend": is_friend,
        "is_following": is_following,
        "follows_viewer": follows_viewer,
        "request_sent": request_sent,
        "request_received": request_received,
        "blocked": blocked,
        "restricted": restricted,
        "relationship": rel,

        # Permissions
        "can_message": can_message_flag,
        "can_call": can_call_flag,
        "can_video_call": can_call_flag,

        # Counters
        "posts_count": posts_count,
        "reels_count": reels_count,
        "stories_count": stories_count,
        "followers_count": followers_count,
        "following_count": following_count,
        "friends_count": friends_count,
        "likes_count": likes_count,
        "views_count": views_count,

        # Social proof
        "mutual_friends_count": len(mutual_friends),
        "mutual_friends": [
            {
                "id": m.get("id"),
                "username": m.get("username"),
                "display_name": m.get("display_name"),
                "avatar_url": m.get("avatar_url"),
            }
            for m in mutual_friends[:6] if isinstance(m, dict)
        ],
        "recently_active_friends": [
            {
                "id": f.get("id") or f.get("profile_id"),
                "username": f.get("username"),
                "display_name": f.get("display_name"),
                "avatar_url": f.get("avatar_url"),
            }
            for f in recently_active[:6] if isinstance(f, dict)
        ],

        # Content previews
        "gallery_preview": gallery_preview,
        "gallery_count": len(gallery_preview),
        "reels_preview": reels_preview,
        "reel_count": reels_count,
        "stories": stories[:6] if stories else [],
        "stories_count": len(stories),
        "has_active_stories": bool(stories),
        "highlights": highlights[:8] if highlights else [],
        "highlights_count": len(highlights),
        "live_rooms": live_rooms,
        "is_live": bool(live_rooms),

        # Creator
        "creator_enabled": creator_enabled,
        "profile_strength": profile_strength if is_self else None,
        "studio_overview": studio_overview,

        # Activity
        "activity": activity_list,

        # Safety
        "report_url": f"/profile/{pid}/report" if not is_self else None,
        "block_state": "blocked" if blocked else ("none" if not is_self else None),

        # Metadata
        "timing_ms": round((time.perf_counter() - start) * 1000, 2),
    }

    return model


# ─── Section loaders (for lazy tabs) ───

@_track_op("content")
def get_profile_content_section(viewer_id, target, section, page=1, per_page=12):
    """Load a specific content section for the profile."""
    profile = _resolve_target(target)
    if not profile:
        return {"ok": False, "error": "Profile not found"}
    pid = profile.get("id")
    viewer_id = _uuid_or_none(viewer_id) if viewer_id else None
    is_self = viewer_id and viewer_id == pid

    if section == "reels":
        return _get_profile_reels(pid, viewer_id or pid, page, per_page)
    elif section == "stories":
        return _get_profile_stories(pid, viewer_id or pid, page, per_page)
    elif section == "gallery":
        return _get_profile_gallery_section(pid, viewer_id or pid, page, per_page)
    elif section == "live":
        return _get_profile_live(pid)
    elif section == "friends":
        return _get_profile_friends(pid, viewer_id, page, per_page)
    elif section == "activity":
        return _get_profile_activity_section(pid, page, per_page)
    elif section == "about":
        return _get_profile_about(profile)
    elif section == "highlights":
        return _get_profile_highlights(pid, viewer_id or pid)
    return {"ok": False, "error": "Unknown section"}


def _get_profile_reels(pid, viewer_id, page, per_page):
    from services.reels_engine import get_reels_feed
    try:
        offset = (page - 1) * per_page
        reels, next_cursor = get_reels_feed(viewer_id, feed_type="profile", cursor=str(offset) if offset else None, limit=per_page)
        items = []
        for r in (reels or []):
            items.append({
                "id": r.get("id"),
                "caption": r.get("caption", ""),
                "thumbnail": r.get("thumbnail_url") or r.get("media_url", ""),
                "media_url": r.get("media_url", ""),
                "views": r.get("views", 0),
                "likes": r.get("likes", 0),
                "comments": r.get("comments", 0),
                "created_at": r.get("created_at"),
            })
        return {"ok": True, "items": items, "has_more": bool(next_cursor), "next_cursor": next_cursor}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_profile_stories(pid, viewer_id, page, per_page):
    try:
        stories = get_stories_by_creator(pid, viewer_id, limit=per_page)
        items = []
        for s in (stories or []):
            items.append({
                "id": s.get("id"),
                "media_url": s.get("media_url", ""),
                "media_type": s.get("media_type", "image"),
                "caption": s.get("caption", ""),
                "created_at": s.get("created_at"),
                "viewed": s.get("viewed", False),
                "view_count": s.get("view_count", 0),
            })
        return {"ok": True, "items": items, "has_more": False}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_profile_gallery_section(pid, viewer_id, page, per_page):
    try:
        items, total = get_profile_gallery(pid, viewer_id, None, None, page, per_page)
        gallery = []
        for item in (items or []):
            gallery.append({
                "id": item.get("id"),
                "media_url": item.get("media_url") or item.get("url", ""),
                "media_type": item.get("media_type", "image"),
                "thumbnail": item.get("thumbnail") or item.get("media_url", ""),
                "caption": item.get("caption", ""),
                "created_at": item.get("created_at"),
            })
        return {"ok": True, "items": gallery, "total": total, "has_more": len(gallery) >= per_page}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_profile_live(pid):
    try:
        analytics = get_creator_live_analytics(pid, 10)
        rooms_data = analytics.get("analytics") if isinstance(analytics, dict) else []
        items = []
        for r in (rooms_data or []):
            rid = r.get("room_id") or r.get("id")
            room_detail = None
            if rid:
                room_detail = get_live_room(rid) if rid else None
            rd = room_detail.get("room") if room_detail and isinstance(room_detail, dict) else {}
            items.append({
                "id": rid,
                "title": rd.get("title", r.get("title", "Live Stream")),
                "status": rd.get("status", r.get("status", "ended")),
                "started_at": r.get("started_at") or r.get("created_at"),
                "viewer_count": rd.get("viewer_count", 0),
                "thumbnail": rd.get("thumbnail_url", ""),
            })
        return {"ok": True, "items": items, "is_live": any(i.get("status") == "live" for i in items)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_profile_friends(pid, viewer_id, page, per_page):
    try:
        result = list_friends(pid, limit=per_page, cursor=str((page - 1) * per_page) if page > 1 else None)
        friends = result.get("friends", []) if isinstance(result, dict) else []
        items = []
        for f in friends:
            items.append({
                "id": f.get("id"),
                "username": f.get("username"),
                "display_name": f.get("display_name"),
                "avatar_url": f.get("avatar_url"),
                "is_online": f.get("is_online", False),
            })
        return {"ok": True, "items": items, "has_more": result.get("has_more", False) if isinstance(result, dict) else False}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_profile_activity_section(pid, page, per_page):
    try:
        activity = get_recent_activity(pid, per_page)
        items = []
        for a in (activity or []):
            items.append({
                "id": a.get("id"),
                "event_type": a.get("event_type", ""),
                "created_at": a.get("created_at", ""),
                "metadata": a.get("metadata"),
            })
        return {"ok": True, "items": items, "has_more": False}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_profile_about(profile):
    interests = profile.get("interests") or []
    if isinstance(interests, str):
        try:
            import json
            interests = json.loads(interests)
        except (json.JSONDecodeError, TypeError):
            interests = []
    skills = profile.get("skills") or []
    if isinstance(skills, str):
        try:
            import json
            skills = json.loads(skills)
        except (json.JSONDecodeError, TypeError):
            skills = []
    return {
        "ok": True,
        "joined": _joined_date(profile),
        "location": _location(profile),
        "category": profile.get("category", profile.get("creator_category", "")),
        "bio": profile.get("bio", ""),
        "website": profile.get("website", ""),
        "interests": interests if isinstance(interests, list) else [],
        "skills": skills if isinstance(skills, list) else [],
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "verified": bool(profile.get("is_verified")),
        "badge_type": "verified" if profile.get("is_verified") else "",
    }


def _get_profile_highlights(pid, viewer_id):
    try:
        highlights = get_highlights(pid, viewer_id)
        items = []
        for h in (highlights or []):
            items.append({
                "id": h.get("id"),
                "title": h.get("title", ""),
                "cover_url": h.get("cover_url", ""),
                "story_count": h.get("story_count", 0),
            })
        return {"ok": True, "items": items}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── Emit profile events ───

def emit_profile_viewed(viewer_id, target_profile_id):
    if not viewer_id or not target_profile_id or viewer_id == target_profile_id:
        return
    try:
        emit_activity(
            actor_profile_id=viewer_id,
            event_type="profile_viewed",
            target_type="profile",
            target_id=target_profile_id,
            recipient_profile_id=target_profile_id,
            visibility="private",
        )
    except Exception:
        pass


def emit_profile_followed(actor_id, target_id):
    if not actor_id or not target_id or actor_id == target_id:
        return
    try:
        emit_activity(
            actor_profile_id=actor_id,
            event_type="profile_followed",
            target_type="profile",
            target_id=target_id,
            recipient_profile_id=target_id,
            visibility="public",
        )
    except Exception:
        pass


def emit_profile_shared(actor_id, target_id):
    if not actor_id or not target_id:
        return
    try:
        emit_activity(
            actor_profile_id=actor_id,
            event_type="profile_shared",
            target_type="profile",
            target_id=target_id,
            recipient_profile_id=target_id if target_id != actor_id else None,
            visibility="public",
        )
    except Exception:
        pass


# ─── Cache helpers ───

def cache_profile_overview(pid, data):
    key = cache_key("profile_2026", "overview", pid)
    set_cache(key, data, PROFILE_CACHE_TTL)


def get_cached_profile_overview(pid):
    key = cache_key("profile_2026", "overview", pid)
    return get_cache(key)


def invalidate_profile_cache(pid):
    for prefix in ("profile_2026", "profile_2026_content"):
        for suffix in ("overview", "reels", "gallery", "activity"):
            delete_cache(cache_key(prefix, suffix, pid))
    from services.profile_service import invalidate_profile_cache as inv_svc
    try:
        inv_svc(pid)
    except Exception:
        pass
