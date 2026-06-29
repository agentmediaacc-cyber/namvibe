"""Phase 157 — Premium Status System with viewer tracking, expiry, and locked-media metadata."""

from datetime import datetime, timezone, timedelta
import uuid
from services.neon_service import fast_query, write_query
from services.socketio_service import emit_to_profile
from services.content_service import invalidate_content_caches, local_content, local_fallback_allowed, sanitize_text
from services.supabase_storage_service import upload_media_to_supabase, BUCKET_MAPPING, SUPABASE_MEDIA_BUCKET
from engines.cache_engine import cache_key, get_cache, set_cache

MAX_STATUS_DURATION_SECONDS = 120
STATUS_ALLOWED_VISIBILITY = {"followers", "private", "subscribers", "locked"}

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _utcnow():
    return datetime.now(timezone.utc)


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


def _relative_label(value):
    parsed = _parse_dt(value)
    if not parsed:
        return ""
    delta = _utcnow() - parsed.astimezone(timezone.utc)
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return f"uploaded {seconds}s ago"
    if seconds < 3600:
        return f"uploaded {seconds // 60}m ago"
    if seconds < 86400:
        return f"uploaded {seconds // 3600}h ago"
    return f"uploaded {seconds // 86400}d ago"


def _expires_in_label(value):
    parsed = _parse_dt(value)
    if not parsed:
        return ""
    seconds = int((parsed.astimezone(timezone.utc) - _utcnow()).total_seconds())
    if seconds <= 0:
        return "expired"
    if seconds < 3600:
        minutes = max(1, seconds // 60)
        return f"expires in {minutes}m"
    return f"expires in {max(1, seconds // 3600)}h"


def _is_active_subscription(viewer_profile_id, owner_id):
    if not viewer_profile_id or not owner_id:
        return False
    rows = fast_query(
        """SELECT 1
           FROM chain_creator_subscriptions
           WHERE subscriber_profile_id = %s AND creator_profile_id = %s AND status = 'active'
           LIMIT 1""",
        (viewer_profile_id, owner_id),
        timeout_ms=500,
        default=[],
    )
    return bool(rows)


def _is_follower(viewer_profile_id, owner_id):
    if not viewer_profile_id or not owner_id:
        return False
    rows = fast_query(
        """SELECT 1
           FROM chain_follows
           WHERE follower_profile_id = %s AND following_profile_id = %s
           LIMIT 1""",
        (viewer_profile_id, owner_id),
        timeout_ms=500,
        default=[],
    )
    return bool(rows)


def _status_access_flags(status, viewer_profile_id=None):
    if not status:
        return {
            "is_owner": False,
            "can_view": False,
            "is_locked": True,
            "locked_reason": "not_found",
            "subscribe_url": "/wallet",
            "preview_url": "",
        }
    owner_id = str(status.get("profile_id") or status.get("owner_id") or "")
    viewer_id = str(viewer_profile_id or "")
    visibility = str(status.get("visibility") or "followers").lower()
    is_owner = bool(viewer_id and owner_id and viewer_id == owner_id)
    can_view = False
    locked_reason = None
    if is_owner:
        can_view = True
    elif visibility == "private":
        locked_reason = "private"
    elif visibility == "followers":
        can_view = _is_follower(viewer_profile_id, owner_id)
        if not can_view:
            locked_reason = "followers_only"
    elif visibility in {"subscribers", "locked"}:
        can_view = _is_active_subscription(viewer_profile_id, owner_id)
        if not can_view:
            locked_reason = "subscriber_only"
    else:
        locked_reason = "private"
    preview_url = status.get("thumbnail_url") or status.get("media_url") or status.get("video_url") or ""
    return {
        "is_owner": is_owner,
        "can_view": can_view,
        "is_locked": not can_view,
        "locked_reason": locked_reason,
        "subscribe_url": f"/wallet?creator_id={owner_id}" if owner_id else "/wallet",
        "preview_url": preview_url if not can_view else "",
    }


def serialize_status(status, viewer_profile_id=None):
    if not status:
        return None
    row = dict(status)
    row["visibility"] = str(row.get("visibility") or "followers").lower()
    row["uploaded_label"] = _relative_label(row.get("created_at"))
    row["expires_in_label"] = _expires_in_label(row.get("expires_at"))
    row["owner_id"] = row.get("owner_id") or row.get("profile_id")
    row["views_count"] = int(row.get("views_count") or 0)
    row["duration_seconds"] = int(row.get("duration_seconds") or 0)
    row.update(_status_access_flags(row, viewer_profile_id=viewer_profile_id))
    return row

def validate_status_duration(duration_seconds):
    if duration_seconds and duration_seconds > MAX_STATUS_DURATION_SECONDS:
        return False, f"Status video cannot exceed {MAX_STATUS_DURATION_SECONDS} seconds"
    return True, None

def create_status(profile_id, caption="", media_file=None, visibility="followers",
                  media_type="image", duration_seconds=0, background_color=None,
                  text_content=None, music_url="", music_title="", music_artist="",
                  music_start_seconds=0, music_duration_seconds=0):
    """Create a story/status with optional media.

    Status rules:
    - Default visibility is 'followers' (not public)
    - Video max 120 seconds
    - Expires after 24 hours
    """
    if visibility not in STATUS_ALLOWED_VISIBILITY:
        visibility = "followers"
    duration_seconds = int(duration_seconds or 0)
    ok, error = validate_status_duration(duration_seconds)
    if not ok:
        return None, error

    music_title = sanitize_text(music_title, max_len=160) if music_title else ""
    music_artist = sanitize_text(music_artist, max_len=120) if music_artist else ""
    music_duration_seconds = int(music_duration_seconds or 0)
    music_start_seconds = int(music_start_seconds or 0)
    if music_duration_seconds > 90:
        music_duration_seconds = 90
    if music_start_seconds < 0:
        music_start_seconds = 0

    media_url = None
    video_url = None
    storage_bucket = None
    storage_path = None
    mime_type = None
    size_bytes = None

    if media_file:
        folder = "status" if media_type == "text" else "stories"
        result = upload_media_to_supabase(media_file, folder, profile_id)
        if not result.get("ok"):
            return None, result.get("error", "Upload failed")
        media_url = result.get("url")
        video_url = result.get("url") if media_type == "video" else None
        storage_path = result.get("path")
        mime_type = result.get("mime_type")
        size_bytes = result.get("size")
        storage_bucket = "supabase"

    if not caption and not media_file and not text_content:
        return None, "Status cannot be empty."

    status_id = str(uuid.uuid4())
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    now = _utcnow_iso()

    sql = """
        INSERT INTO chain_status_posts
            (id, profile_id, caption, media_url, video_url, media_type, storage_bucket, storage_path,
             mime_type, size_bytes, visibility, expires_at, duration_seconds, background_color,
             text_content, music_url, music_title, music_artist, music_start_seconds, music_duration_seconds,
             views_count, created_at, owner_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
    """
    try:
        write_query(sql, (
            status_id, profile_id, caption, media_url, video_url, media_type,
            storage_bucket, storage_path, mime_type, size_bytes, visibility,
            expires_at, duration_seconds, background_color, text_content,
            music_url or None, music_title or None, music_artist or None,
            int(music_start_seconds) if music_start_seconds else 0,
            int(music_duration_seconds) if music_duration_seconds else 0,
            now, profile_id
        ))
        record = serialize_status({
            "id": status_id,
            "profile_id": profile_id,
            "owner_id": profile_id,
            "caption": caption,
            "media_url": media_url,
            "video_url": video_url,
            "media_type": media_type,
            "visibility": visibility,
            "expires_at": expires_at,
            "duration_seconds": duration_seconds,
            "background_color": background_color,
            "text_content": text_content,
            "music_url": music_url or None,
            "music_title": music_title or None,
            "music_artist": music_artist or None,
            "music_start_seconds": int(music_start_seconds) if music_start_seconds else 0,
            "music_duration_seconds": int(music_duration_seconds) if music_duration_seconds else 0,
            "views_count": 0,
            "created_at": now,
        }, viewer_profile_id=profile_id)
        invalidate_content_caches()
        return record, None
    except Exception as e:
        if local_fallback_allowed():
            record = serialize_status({
                "id": status_id,
                "profile_id": profile_id,
                "owner_id": profile_id,
                "caption": caption,
                "media_url": media_url,
                "video_url": video_url,
                "media_type": media_type,
                "visibility": visibility,
                "expires_at": expires_at,
                "duration_seconds": duration_seconds,
                "background_color": background_color,
                "text_content": text_content,
                "views_count": 0,
                "created_at": now,
            }, viewer_profile_id=profile_id)
            local_content()["stories"].insert(0, record)
            invalidate_content_caches()
            return record, None
        return None, str(e)

def record_view(status_id, viewer_profile_id, reaction=None, reply_message=None):
    """Record a status view. Uses chain_status_views with UNIQUE(status_id, viewer_profile_id)."""
    try:
        status = get_status(status_id, viewer_profile_id=viewer_profile_id)
        if not status:
            return False
        if str(status.get("profile_id")) == str(viewer_profile_id):
            return True
        write_query(
            """INSERT INTO chain_status_views (status_id, viewer_profile_id, viewed_at, reaction, reply_message)
               VALUES (%s, %s, now(), %s, %s)
               ON CONFLICT (status_id, viewer_profile_id) DO UPDATE SET viewed_at = now()""",
            (status_id, viewer_profile_id, reaction, reply_message)
        )
        # Increment views_count on the status
        write_query(
            "UPDATE chain_status_posts SET views_count = (SELECT COUNT(*) FROM chain_status_views WHERE status_id = %s) WHERE id = %s",
            (status_id, status_id)
        )
        # Notify status owner
        if status:
            emit_to_profile(status['profile_id'], "status:viewed", {
                "status_id": status_id,
                "viewer_id": viewer_profile_id,
                "reaction": reaction,
            })
        return True
    except Exception:
        return False

def list_viewers(status_id, requesting_profile_id=None):
    """List viewers for a status. Only owner can see viewer list."""
    if not requesting_profile_id:
        return []
    status = get_status(status_id, viewer_profile_id=requesting_profile_id)
    if not status:
        return []
    if str(status.get("profile_id")) != str(requesting_profile_id):
        return []
    rows = fast_query(
        """SELECT v.viewed_at, v.reaction, v.reply_message,
                  p.id, p.username, p.avatar_url, p.display_name, p.is_verified
           FROM chain_status_views v
           JOIN chain_profiles p ON v.viewer_profile_id = p.id
           WHERE v.status_id = %s
           ORDER BY v.viewed_at DESC LIMIT 100""",
        (status_id,)
    )
    result = []
    for r in rows:
        result.append({
            "viewer_id": r.get("id"),
            "username": r.get("username"),
            "avatar_url": r.get("avatar_url"),
            "display_name": r.get("display_name"),
            "verified": bool(r.get("is_verified")),
            "viewed_at": str(r.get("viewed_at") or ""),
            "reaction": r.get("reaction"),
            "reply_message": r.get("reply_message"),
        })
    return result

def list_active_statuses(profile_id=None, viewer_profile_id=None, limit=None, offset=None):
    """List active (non-expired) statuses with visibility filtering.

    Performance optimized: uses CTE to batch-follow lookups for the viewer,
    selects only required columns, and uses 30s cache.
    """
    now = _utcnow_iso()
    cache_key_str = cache_key(f"status:active:{profile_id or 'all'}:viewer:{viewer_profile_id or 'anon'}:{limit or 50}:{offset or 0}")
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached

    row_limit = min(int(limit or 50), 100)
    row_offset = max(int(offset or 0), 0)

    # Select only columns actually needed by serialize_status instead of s.*
    story_cols = """
        s.id, s.profile_id, s.body, s.media_url, s.video_url, s.media_type,
        s.visibility, s.expires_at, s.created_at, s.updated_at,
        s.duration_seconds, s.background_color, s.text_content,
        s.music_url, s.music_title, s.music_artist,
        s.music_start_seconds, s.music_duration_seconds,
        s.thumbnail_url, s.views_count, s.comments_count,
        s.likes_count, s.owner_id
    """

    # Build optimized query based on view context
    if profile_id:
        # Single profile view - simpler query
        params = [now, profile_id]
        sql = f"""
            SELECT {story_cols}, p.username, p.avatar_url, p.display_name, p.is_verified,
                   COALESCE(s.views_count, 0) as views_count
            FROM chain_status_posts s
            JOIN chain_profiles p ON s.profile_id = p.id
            WHERE s.expires_at > %s AND s.deleted_at IS NULL
              AND s.profile_id = %s
        """
        if viewer_profile_id and str(profile_id) != str(viewer_profile_id):
            viewer = str(viewer_profile_id)
            params.append(viewer)
            params.append(viewer)
            params.append(viewer_profile_id)
            sql += """ AND (
                s.visibility = 'followers' AND EXISTS (
                    SELECT 1 FROM chain_follows
                    WHERE follower_profile_id = %s AND following_profile_id = s.profile_id
                )
                OR s.visibility IN ('subscribers','locked') AND EXISTS (
                    SELECT 1 FROM chain_creator_subscriptions
                    WHERE subscriber_profile_id = %s AND creator_profile_id = s.profile_id AND status = 'active'
                )
                OR s.visibility = 'private' AND s.profile_id = %s
            )"""
        elif viewer_profile_id and str(profile_id) == str(viewer_profile_id):
            pass
        else:
            sql += """ AND s.visibility IN ('public', 'followers')"""
    else:
        # Feed view - optimized with follow_map CTE
        if viewer_profile_id:
            viewer = str(viewer_profile_id)
            params = [viewer, now, viewer, viewer, viewer]
            sql = f"""
                WITH follow_map AS (
                    SELECT following_profile_id FROM chain_follows
                    WHERE follower_profile_id = %s AND deleted_at IS NULL
                ),
                subscription_map AS (
                    SELECT creator_profile_id FROM chain_creator_subscriptions
                    WHERE subscriber_profile_id = %s AND status = 'active'
                )
                SELECT {story_cols}, p.username, p.avatar_url, p.display_name, p.is_verified,
                       COALESCE(s.views_count, 0) as views_count
                FROM chain_status_posts s
                JOIN chain_profiles p ON s.profile_id = p.id
                WHERE s.expires_at > %s AND s.deleted_at IS NULL
                  AND (
                      s.profile_id = %s
                      OR s.visibility = 'public'
                      OR (s.visibility = 'followers' AND s.profile_id IN (SELECT following_profile_id FROM follow_map))
                      OR (s.visibility IN ('subscribers','locked') AND s.profile_id IN (SELECT creator_profile_id FROM subscription_map))
                  )
            """
            params = [viewer, viewer, now, viewer]
        else:
            sql = f"""
                SELECT {story_cols}, p.username, p.avatar_url, p.display_name, p.is_verified,
                       COALESCE(s.views_count, 0) as views_count
                FROM chain_status_posts s
                JOIN chain_profiles p ON s.profile_id = p.id
                WHERE s.expires_at > %s AND s.deleted_at IS NULL AND 1 = 0
            """
            params = [now]

    sql += " ORDER BY s.created_at DESC LIMIT %s OFFSET %s"
    params.extend([row_limit, row_offset])
    rows = fast_query(sql, tuple(params), timeout_ms=2000, default=[])
    serialized = [serialize_status(row, viewer_profile_id=viewer_profile_id) for row in rows]
    # Cache for 30 seconds (stories are time-sensitive but 30s is safe)
    set_cache(cache_key_str, serialized, ttl=30)
    return serialized

def get_status(status_id, viewer_profile_id=None):
    rows = fast_query("SELECT * FROM chain_status_posts WHERE id = %s", (status_id,), default=[])
    if rows:
        return serialize_status(rows[0], viewer_profile_id=viewer_profile_id)
    for story in local_content()["stories"]:
        if story.get("id") == status_id:
            return serialize_status(story, viewer_profile_id=viewer_profile_id)
    return None

def can_view_status(status_id, viewer_profile_id=None):
    """Check if a viewer can view a specific status. Returns (allowed, reason)."""
    status = get_status(status_id, viewer_profile_id=viewer_profile_id)
    if not status:
        return False, "not_found"
    flags = _status_access_flags(status, viewer_profile_id=viewer_profile_id)
    return bool(flags["can_view"]), flags["locked_reason"]

def delete_status(status_id, profile_id):
    status = get_status(status_id, viewer_profile_id=profile_id)
    if status and status.get("storage_path"):
        try:
            from utils.supabase_client import get_supabase_admin
            bucket = status.get("storage_bucket") or SUPABASE_MEDIA_BUCKET
            get_supabase_admin().storage.from_(bucket).remove([status["storage_path"]])
        except Exception:
            pass
    sql = "UPDATE chain_status_posts SET deleted_at = now() WHERE id = %s AND profile_id = %s"
    write_query(sql, (status_id, profile_id))
    local_content()["stories"][:] = [s for s in local_content()["stories"]
                                      if not (s.get("id") == status_id and s.get("profile_id") == profile_id)]
    invalidate_content_caches()
    return True

def expire_old_statuses():
    """Mark expired statuses as deleted and remove their Supabase files."""
    rows = fast_query(
        "SELECT id, storage_bucket, storage_path FROM chain_status_posts WHERE expires_at < now() AND deleted_at IS NULL",
        timeout_ms=5000,
        default=[],
    )
    for row in rows:
        path = row.get("storage_path")
        if path:
            folder = path.split("/", 1)[0] if "/" in path else None
            bucket = BUCKET_MAPPING.get(folder, SUPABASE_MEDIA_BUCKET) if folder else SUPABASE_MEDIA_BUCKET
            try:
                from utils.supabase_client import get_supabase_admin
                supabase = get_supabase_admin()
                supabase.storage.from_(bucket).remove([path])
            except Exception:
                pass
    write_query("UPDATE chain_status_posts SET deleted_at = now() WHERE expires_at < now() AND deleted_at IS NULL")