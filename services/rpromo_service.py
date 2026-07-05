from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.supabase_safe import safe_select, safe_insert, safe_delete, table_exists
from services.logging_service import log_info, log_error

_RPROMO_TABLE = "chain_rpromo_videos"
_LIKES_TABLE = "chain_rpromo_likes"
_MAX_VIDEOS = 20


def _utcnow():
    return datetime.now(timezone.utc).isoformat()


def _table_available(name):
    try:
        return table_exists(name, timeout_ms=5000)
    except Exception:
        return False


def get_promo_videos(profile_id, viewer_id=None):
    if not profile_id:
        return []
    try:
        rows = fast_query(
            "SELECT id, profile_id, title, description, video_url, thumbnail_url, "
            "views_count, likes_count, sort_order, created_at "
            "FROM {} WHERE profile_id = %s ORDER BY sort_order ASC, created_at ASC LIMIT %s".format(_RPROMO_TABLE),
            (profile_id, _MAX_VIDEOS), default=[]
        )
        if viewer_id:
            for row in rows:
                row["is_liked"] = _has_liked(row["id"], viewer_id)
                row["is_owner"] = str(row["profile_id"]) == str(viewer_id)
        else:
            for row in rows:
                row["is_liked"] = False
                row["is_owner"] = False
        return rows
    except Exception as e:
        log_error("rpromo_get_videos", str(e))
        return []


def get_promo_video(video_id):
    if not video_id:
        return None
    try:
        rows = fast_query(
            "SELECT id, profile_id, title, description, video_url, thumbnail_url, "
            "views_count, likes_count, sort_order, created_at "
            "FROM {} WHERE id = %s LIMIT 1".format(_RPROMO_TABLE),
            (video_id,), default=[]
        )
        return rows[0] if rows else None
    except Exception as e:
        log_error("rpromo_get_video", str(e))
        return None


def count_promo_videos(profile_id):
    if not profile_id:
        return 0
    try:
        rows = fast_query(
            "SELECT COUNT(*) as count FROM {} WHERE profile_id = %s".format(_RPROMO_TABLE),
            (profile_id,), default=[{"count": 0}]
        )
        return rows[0]["count"] if rows else 0
    except Exception as e:
        log_error("rpromo_count", str(e))
        return 0


def upload_promo_video(profile_id, title, description, video_url, thumbnail_url=""):
    if not profile_id or not video_url:
        return {"success": False, "error": "Missing required fields."}
    if not _table_available(_RPROMO_TABLE):
        return {"success": False, "error": "Database not available."}
    try:
        current_count = count_promo_videos(profile_id)
        if current_count >= _MAX_VIDEOS:
            return {"success": False, "error": "Maximum {} promo videos reached.".format(_MAX_VIDEOS)}
        sort_order = current_count
        inserted = safe_insert(_RPROMO_TABLE, {
            "profile_id": profile_id,
            "title": (title or "").strip()[:200],
            "description": (description or "").strip()[:1000],
            "video_url": video_url,
            "thumbnail_url": thumbnail_url or "",
            "sort_order": sort_order,
            "views_count": 0,
            "likes_count": 0,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
        })
        if inserted is None:
            return {"success": False, "error": "Could not save promo video."}
        return {"success": True, "video": inserted}
    except Exception as e:
        log_error("rpromo_upload", str(e))
        return {"success": False, "error": str(e)}


def delete_promo_video(video_id, profile_id):
    if not video_id or not profile_id:
        return {"success": False, "error": "Missing params."}
    try:
        video = get_promo_video(video_id)
        if not video:
            return {"success": False, "error": "Video not found."}
        if str(video["profile_id"]) != str(profile_id):
            return {"success": False, "error": "Not authorized."}
        safe_delete(_LIKES_TABLE, eq={"video_id": video_id})
        safe_delete(_RPROMO_TABLE, eq={"id": video_id})
        _reorder_videos(profile_id)
        return {"success": True}
    except Exception as e:
        log_error("rpromo_delete", str(e))
        return {"success": False, "error": str(e)}


def record_view(video_id, profile_id=None):
    if not video_id:
        return False
    try:
        write_query(
            "UPDATE {} SET views_count = views_count + 1 WHERE id = %s".format(_RPROMO_TABLE),
            (video_id,)
        )
        return True
    except Exception as e:
        log_error("rpromo_record_view", str(e))
        return False


def toggle_like(video_id, profile_id):
    if not video_id or not profile_id:
        return {"success": False, "error": "Missing params."}
    if not _table_available(_LIKES_TABLE):
        return {"success": False, "error": "Database not available."}
    try:
        video = get_promo_video(video_id)
        if not video:
            return {"success": False, "error": "Video not found."}
        if str(video["profile_id"]) == str(profile_id):
            return {"success": False, "error": "Cannot like your own promo."}
        existing = fast_query(
            "SELECT id FROM {} WHERE video_id = %s AND profile_id = %s LIMIT 1".format(_LIKES_TABLE),
            (video_id, profile_id), default=[]
        )
        if existing:
            safe_delete(_LIKES_TABLE, eq={"id": existing[0]["id"]})
            write_query(
                "UPDATE {} SET likes_count = GREATEST(0, likes_count - 1) WHERE id = %s".format(_RPROMO_TABLE),
                (video_id,)
            )
            liked = False
        else:
            safe_insert(_LIKES_TABLE, {
                "video_id": video_id,
                "profile_id": profile_id,
                "created_at": _utcnow(),
            })
            write_query(
                "UPDATE {} SET likes_count = likes_count + 1 WHERE id = %s".format(_RPROMO_TABLE),
                (video_id,)
            )
            liked = True
        updated = get_promo_video(video_id)
        return {"success": True, "liked": liked, "likes_count": updated.get("likes_count", 0) if updated else 0}
    except Exception as e:
        log_error("rpromo_toggle_like", str(e))
        return {"success": False, "error": str(e)}


def _has_liked(video_id, profile_id):
    if not video_id or not profile_id:
        return False
    try:
        rows = fast_query(
            "SELECT id FROM {} WHERE video_id = %s AND profile_id = %s LIMIT 1".format(_LIKES_TABLE),
            (video_id, profile_id), default=[]
        )
        return len(rows) > 0
    except Exception:
        return False


def _reorder_videos(profile_id):
    try:
        rows = fast_query(
            "SELECT id FROM {} WHERE profile_id = %s ORDER BY sort_order ASC, created_at ASC".format(_RPROMO_TABLE),
            (profile_id,), default=[]
        )
        for i, row in enumerate(rows):
            write_query(
                "UPDATE {} SET sort_order = %s WHERE id = %s".format(_RPROMO_TABLE),
                (i, row["id"])
            )
    except Exception as e:
        log_error("rpromo_reorder", str(e))
