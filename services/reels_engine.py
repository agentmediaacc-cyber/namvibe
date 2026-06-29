import uuid
import time
import threading
import os
import math
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.media_storage_service import upload_media_file
from services.media_pipeline import extract_video_duration, queue_reel_processing, validate_upload
from services.request_cache import build_request_key, request_memoize
from services.content_service import create_reel_record, invalidate_content_caches, local_content

def list_reels(limit=20):
    """Lists published reels."""
    sql = """
        SELECT r.*, p.username, p.avatar_url
        FROM chain_reels r
        JOIN chain_profiles p ON r.profile_id = p.id
        WHERE r.status = 'published' AND r.visibility = 'public' 
        AND r.processing_status = 'ready' AND r.deleted_at IS NULL
        ORDER BY r.created_at DESC
        LIMIT %s
    """
    rows = request_memoize(
        build_request_key("reels_list", limit),
        lambda: fast_query(sql, (limit,), timeout_ms=1000, default=[]),
    )
    return rows or local_content()["reels"][:limit]

def get_reel(reel_id):
    """Gets a single reel by ID."""
    sql = """
        SELECT r.*, p.username, p.avatar_url
        FROM chain_reels r
        JOIN chain_profiles p ON r.profile_id = p.id
        WHERE r.id = %s AND r.deleted_at IS NULL
    """
    rows = fast_query(sql, (reel_id,), timeout_ms=1000, default=[])
    return rows[0] if rows else None

def create_reel(profile_id, caption, file=None, thumbnail=None, music_title="", visibility="public",
               music_url="", music_artist="", music_start_seconds=0, music_duration_seconds=0):
    """Uploads video and triggers async processing. Returns (id, error)."""
    if not file:
        return None, "Video file is required"
    reel, error = create_reel_record(profile_id, file, caption=caption, music_title=music_title, visibility=visibility,
                                     music_url=music_url, music_artist=music_artist,
                                     music_start_seconds=music_start_seconds, music_duration_seconds=music_duration_seconds)
    if error:
        return None, error
    return reel.get("id"), None


def create_reel_full(profile_id, caption, file=None, thumbnail=None, music_title="", visibility="public",
                     music_url="", music_artist="", music_start_seconds=0, music_duration_seconds=0):
    """Uploads video and returns full record dict. Returns (record_dict, error)."""
    if not file:
        return None, "Video file is required"
    return create_reel_record(profile_id, file, caption=caption, music_title=music_title, visibility=visibility,
                              music_url=music_url, music_artist=music_artist,
                              music_start_seconds=music_start_seconds, music_duration_seconds=music_duration_seconds)


def create_reel_legacy(profile_id, caption, file=None, thumbnail=None):
    """Legacy Supabase upload path retained for rollback/debug use."""
    if not file:
        return None, "Video file is required"
    valid, error = validate_upload(
        file,
        allowed_types={"video/mp4", "video/quicktime", "video/webm"},
        max_mb=150,
    )
    if not valid:
        return None, error

    # 1. Upload Video (uploaded state)
    video_res, error = upload_media_file(file, bucket_name='chain-reels', profile_id=profile_id, upload_type='reel_video')
    if error:
        return None, error

    metadata = extract_video_duration(file)
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)

    # 2. Save to Neon with 'uploaded' status
    reel_id = str(uuid.uuid4())
    sql = """
        INSERT INTO chain_reels (
            id, profile_id, caption, video_url, storage_bucket, storage_path, duration_seconds, width, height, mime_type, file_size, processing_status, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploaded', now())
        RETURNING id
    """
    params = (
        reel_id, profile_id, caption, video_res['public_url'], 
        video_res['bucket'], video_res['file_path'], metadata.get("duration_seconds"), metadata.get("width"), metadata.get("height"), metadata.get("mime_type"), file_size
    )
    try:
        write_query(sql, params)
        # 3. Trigger processing
        queue_reel_processing(reel_id)
        return reel_id, None
    except Exception as e:
        print(f"[reels_engine] Failed to save reel: {e}")
        return None, str(e)


# ── Debounce & Flush Infrastructure ──

_REEL_VIEW_QUEUE = {}
_REEL_VIEW_LOCK = threading.Lock()
_REEL_VIEW_LAST_FLUSH = 0
_REEL_VIEW_FLUSH_INTERVAL = 60
_REEL_VIEW_DEBOUNCE_SECONDS = 1800

_DEBOUNCE_CACHE = {}
_DEBOUNCE_LOCK = threading.Lock()

try:
    from services.redis_service import RedisManager, cache_set, cache_get
    _redis_available = RedisManager._check_ping() if hasattr(RedisManager, '_check_ping') else False
except Exception:
    _redis_available = False

_CHAIN_TEST_MODE = os.environ.get("CHAIN_TEST_MODE") == "1"

def _view_debounce_key(reel_id, viewer_id):
    return f"reel_view:{reel_id}:{viewer_id or 'anon'}"

def _check_debounce(reel_id, viewer_id):
    if _CHAIN_TEST_MODE:
        return False
    key = _view_debounce_key(reel_id, viewer_id)
    if _redis_available:
        try:
            val = cache_get(key)
            return val is not None
        except Exception:
            pass
    with _DEBOUNCE_LOCK:
        last = _DEBOUNCE_CACHE.get(key)
        if last and (time.time() - last) < _REEL_VIEW_DEBOUNCE_SECONDS:
            return True
        _DEBOUNCE_CACHE[key] = time.time()
        if len(_DEBOUNCE_CACHE) > 10000:
            now = time.time()
            _DEBOUNCE_CACHE = {k: v for k, v in _DEBOUNCE_CACHE.items() if (now - v) < _REEL_VIEW_DEBOUNCE_SECONDS}
        return False

def _mark_debounce(reel_id, viewer_id):
    if _CHAIN_TEST_MODE:
        return
    key = _view_debounce_key(reel_id, viewer_id)
    if _redis_available:
        try:
            cache_set(key, "1", ttl=_REEL_VIEW_DEBOUNCE_SECONDS)
        except Exception:
            pass

def _flush_reel_views():
    global _REEL_VIEW_LAST_FLUSH
    now = time.time()
    if now - _REEL_VIEW_LAST_FLUSH < _REEL_VIEW_FLUSH_INTERVAL:
        return
    with _REEL_VIEW_LOCK:
        if now - _REEL_VIEW_LAST_FLUSH < _REEL_VIEW_FLUSH_INTERVAL:
            return
        batch = dict(_REEL_VIEW_QUEUE)
        _REEL_VIEW_QUEUE.clear()
        _REEL_VIEW_LAST_FLUSH = now
    if not batch:
        return
    def _do_flush():
        for reel_id, count in batch.items():
            try:
                write_query(
                    "UPDATE chain_reels SET views_count = COALESCE(views_count, 0) + %s WHERE id = %s",
                    (count, reel_id),
                )
            except Exception:
                pass
    threading.Thread(target=_do_flush, daemon=True).start()

def record_reel_view(reel_id, viewer_profile_id=None):
    """Records a view for a reel. Debounces to once per 30 min per user. Returns quickly."""
    if _check_debounce(reel_id, viewer_profile_id):
        return True
    _mark_debounce(reel_id, viewer_profile_id)
    with _REEL_VIEW_LOCK:
        _REEL_VIEW_QUEUE[reel_id] = _REEL_VIEW_QUEUE.get(reel_id, 0) + 1
    _flush_reel_views()
    try:
        from services.analytics_engine import track_reel_view
        track_reel_view(reel_id, viewer_profile_id)
    except Exception:
        pass
    return True

def like_reel(reel_id, profile_id):
    """Toggles like on a reel."""
    from services.engagement_service import toggle_like
    return toggle_like(profile_id, "reel", reel_id)

def share_reel(reel_id, profile_id=None):
    """Increments share count for a reel."""
    sql = "UPDATE chain_reels SET shares_count = shares_count + 1 WHERE id = %s"
    write_query(sql, (reel_id,))
    from services.analytics_engine import track_event
    track_event("reel_share", profile_id=profile_id, entity_type="reel", entity_id=reel_id)
    return True

def delete_reel(reel_id, profile_id):
    """Soft deletes a reel if owned by profile_id."""
    sql = "UPDATE chain_reels SET deleted_at = now() WHERE id = %s AND profile_id = %s"
    result = write_query(sql, (reel_id, profile_id))
    invalidate_content_caches()
    return result


# ── Feed & Ranking ──

_REEL_RANKING_SIGNALS = {
    "watch_time": 0.25,
    "completion_rate": 0.20,
    "likes": 0.15,
    "comments": 0.10,
    "shares": 0.10,
    "saves": 0.08,
    "recency": 0.07,
    "following": 0.05,
}


def _normalize(values):
    if not values:
        return values
    mn, mx = min(values), max(values)
    span = mx - mn or 1
    return [(v - mn) / span for v in values]


def rank_reels_for_viewer(viewer_id, reels):
    """Rank a list of reel dicts by engagement signals + viewer affinity."""
    if not reels:
        return reels

    now = datetime.now(timezone.utc)
    ws = [r.get("watch_time", 0) for r in reels]
    crs = [r.get("completion_rate", 0) for r in reels]
    ls = [r.get("likes_count", 0) for r in reels]
    cs = [r.get("comments_count", 0) for r in reels]
    ss = [r.get("shares_count", 0) for r in reels]
    svs = [r.get("saves_count", 0) for r in reels]
    ages = []
    following_ids = set()

    if viewer_id:
        try:
            from services.reels_service import batch_is_following
            following_ids = batch_is_following(
                viewer_id, [r.get("profile_id") for r in reels if r.get("profile_id")]
            )
        except Exception:
            pass

    for r in reels:
        raw = r.get("created_at")
        if raw:
            if isinstance(raw, str):
                try:
                    raw = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except Exception:
                    raw = now
            age_hours = (now - raw).total_seconds() / 3600
        else:
            age_hours = 24
        ages.append(max(age_hours, 0.01))

    n_ws = _normalize(ws)
    n_crs = _normalize(crs)
    n_ls = _normalize(ls)
    n_cs = _normalize(cs)
    n_ss = _normalize(ss)
    n_svs = _normalize(svs)
    n_rec = _normalize([max(48 - a, 0) / 48 for a in ages])

    scores = []
    for i, r in enumerate(reels):
        score = (
            n_ws[i] * _REEL_RANKING_SIGNALS["watch_time"]
            + n_crs[i] * _REEL_RANKING_SIGNALS["completion_rate"]
            + n_ls[i] * _REEL_RANKING_SIGNALS["likes"]
            + n_cs[i] * _REEL_RANKING_SIGNALS["comments"]
            + n_ss[i] * _REEL_RANKING_SIGNALS["shares"]
            + n_svs[i] * _REEL_RANKING_SIGNALS["saves"]
            + n_rec[i] * _REEL_RANKING_SIGNALS["recency"]
        )
        pid = r.get("profile_id")
        if pid and pid in following_ids:
            score += _REEL_RANKING_SIGNALS["following"]
        scores.append(score)

    ranked = sorted(zip(reels, scores), key=lambda x: x[1], reverse=True)
    return [r for r, _ in ranked]


def get_reels_feed(viewer_id, feed_type="for_you", cursor=None, limit=10):
    """Cursor-based reels feed with ranking. Returns (reels, next_cursor)."""
    t0 = time.time()
    try:
        from services.feed_cursor_service import decode_cursor, encode_cursor
    except Exception:
        decode_cursor = None
        encode_cursor = None

    offset = 0
    if cursor and decode_cursor:
        try:
            decoded = decode_cursor(cursor)
            offset = decoded.get("offset", 0) if isinstance(decoded, dict) else int(decoded)
        except Exception:
            offset = 0

    base_sql = """
        SELECT r.*, p.display_name, p.avatar_url
        FROM chain_reels r
        JOIN chain_profiles p ON p.id = r.profile_id
        WHERE r.deleted_at IS NULL AND r.status = 'published'
    """
    params = []

    if feed_type == "following" and viewer_id:
        base_sql += " AND r.profile_id IN (SELECT followed_id FROM chain_follows WHERE follower_id = %s)"
        params.append(viewer_id)

    base_sql += " ORDER BY r.created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit + 1, offset])

    rows = fast_query(base_sql, tuple(params))
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    reels = [_reel_row_to_dict(r) for r in rows]

    if feed_type == "for_you" and len(reels) > 1:
        reels = rank_reels_for_viewer(viewer_id, reels)

    next_offset = offset + limit
    next_cursor = None
    if has_more and encode_cursor:
        try:
            next_cursor = encode_cursor({"offset": next_offset})
        except Exception:
            next_cursor = str(next_offset)

    try:
        from services.performance_monitor import track_timing
        track_timing("reels.feed.ms", (time.time() - t0) * 1000)
    except Exception:
        pass

    return reels, next_cursor


def get_reel_detail(viewer_id, reel_id):
    """Return reel with viewer interaction states (liked, saved, following creator)."""
    sql = """
        SELECT r.*, p.display_name, p.avatar_url
        FROM chain_reels r
        JOIN chain_profiles p ON p.id = r.profile_id
        WHERE r.id = %s AND r.deleted_at IS NULL
    """
    rows = fast_query(sql, (reel_id,))
    if not rows:
        return None

    reel = _reel_row_to_dict(rows[0])
    reel["viewer_has_liked"] = False
    reel["viewer_has_saved"] = False
    reel["viewer_follows_creator"] = False

    if viewer_id:
        pid = viewer_id
        cid = reel["profile_id"]
        try:
            likes = fast_query(
                "SELECT 1 FROM chain_likes WHERE profile_id = %s AND entity_type = 'reel' AND entity_id = %s",
                (pid, reel_id)
            )
            reel["viewer_has_liked"] = bool(likes)
        except Exception:
            pass
        try:
            saves = fast_query(
                "SELECT 1 FROM chain_reel_saves WHERE profile_id = %s AND reel_id = %s",
                (pid, reel_id)
            )
            reel["viewer_has_saved"] = bool(saves)
        except Exception:
            pass
        try:
            follows = fast_query(
                "SELECT 1 FROM chain_follows WHERE follower_id = %s AND followed_id = %s",
                (pid, cid)
            )
            reel["viewer_follows_creator"] = bool(follows)
        except Exception:
            pass

    return reel


def get_next_reels(viewer_id, current_reel_id, limit=5):
    """Fetch next reels after current for continuous play."""
    sql = """
        SELECT r.*, p.display_name, p.avatar_url
        FROM chain_reels r
        JOIN chain_profiles p ON p.id = r.profile_id
        LEFT JOIN chain_reel_watch_events w ON w.reel_id = r.id AND w.profile_id = %s
        WHERE r.deleted_at IS NULL AND r.status = 'published' AND r.id != %s
        GROUP BY r.id, p.display_name, p.avatar_url
        ORDER BY COUNT(w.id) ASC, r.created_at DESC
        LIMIT %s
    """
    rows = fast_query(sql, (viewer_id or 0, current_reel_id, limit))
    reels = [_reel_row_to_dict(r) for r in rows]

    if viewer_id and len(reels) > 1:
        reels = rank_reels_for_viewer(viewer_id, reels)

    return reels


def _reel_row_to_dict(row):
    """Convert a reel DB row (named tuple or dict) to a clean dict."""
    if hasattr(row, "_mapping"):
        row = dict(row._mapping)
    elif not isinstance(row, dict):
        row = dict(row)

    reel = {
        "id": row.get("id"),
        "profile_id": row.get("profile_id"),
        "display_name": row.get("display_name", ""),
        "avatar_url": row.get("avatar_url", ""),
        "caption": row.get("caption", ""),
        "video_url": row.get("video_url", ""),
        "thumbnail_url": row.get("thumbnail_url", ""),
        "music_title": row.get("music_title", ""),
        "music_artist": row.get("music_artist", ""),
        "likes_count": row.get("likes_count", 0) or 0,
        "comments_count": row.get("comments_count", 0) or 0,
        "views_count": row.get("views_count", 0) or 0,
        "shares_count": row.get("shares_count", 0) or 0,
        "saves_count": row.get("saves_count", 0) or 0,
        "duration_seconds": row.get("duration_seconds", 0) or 0,
        "hashtags": row.get("hashtags"),
        "location": row.get("location"),
        "created_at": row.get("created_at"),
        "visibility": row.get("visibility", "public"),
        "status": row.get("status", "published"),
    }
    return reel


# ── Enhanced Watch Tracking ──

def track_reel_watch(viewer_id, reel_id, watch_ms, completed=False, replayed=False):
    """Record detailed watch event with completion/replay signals. Debounced to 5s per user per reel."""
    if not viewer_id or not reel_id:
        return False

    debounce_key = f"rw:{viewer_id}:{reel_id}"
    now = time.time()
    with _DEBOUNCE_LOCK:
        last = _DEBOUNCE_CACHE.get(debounce_key)
        if last and (now - last) < 5:
            return False
        _DEBOUNCE_CACHE[debounce_key] = now

    try:
        write_query(
            """INSERT INTO chain_reel_watch_events
               (profile_id, reel_id, watch_ms, completed, replayed, watched_at)
               VALUES (%s, %s, %s, %s, %s, now())""",
            (viewer_id, reel_id, watch_ms, completed, replayed),
        )
        if completed:
            write_query(
                "UPDATE chain_reels SET views_count = COALESCE(views_count, 0) + 1 WHERE id = %s",
                (reel_id,),
            )
        try:
            from services.activity_engine import emit_activity
            emit_activity(
                actor_id=viewer_id,
                verb="reel_watched",
                entity_type="reel",
                entity_id=reel_id,
                metadata={"watch_ms": watch_ms, "completed": completed, "replayed": replayed},
            )
        except Exception:
            pass
        return True
    except Exception as e:
        _log_error("track_reel_watch", e)
        return False


# ── Like / Unlike ──

def like_reel_v2(viewer_id, reel_id):
    """Like a reel. Returns (success, new_state)."""
    try:
        from services.engagement_service import toggle_like
        result = toggle_like(viewer_id, "reel", reel_id)
        liked = True
        sql = "UPDATE chain_reels SET likes_count = COALESCE(likes_count, 0) + 1 WHERE id = %s"
        write_query(sql, (reel_id,))
        _emit_reel_activity(viewer_id, reel_id, "reel_liked")
        _notify_creator("reel_liked", viewer_id, reel_id)
        return True, liked
    except Exception as e:
        _log_error("like_reel", e)
        return False, False


def unlike_reel(viewer_id, reel_id):
    """Unlike a reel. Returns (success, new_state)."""
    try:
        from services.engagement_service import toggle_like
        result = toggle_like(viewer_id, "reel", reel_id)
        liked = False
        sql = "UPDATE chain_reels SET likes_count = GREATEST(COALESCE(likes_count, 1) - 1, 0) WHERE id = %s"
        write_query(sql, (reel_id,))
        return True, liked
    except Exception as e:
        _log_error("unlike_reel", e)
        return False, False


# ── Save / Unsave ──

def save_reel(viewer_id, reel_id):
    """Save a reel. Returns (success, new_state)."""
    try:
        from services.engagement_service import toggle_save
        result = toggle_save(viewer_id, "reel", reel_id)
        saved = True
        sql = "UPDATE chain_reels SET saves_count = COALESCE(saves_count, 0) + 1 WHERE id = %s"
        write_query(sql, (reel_id,))
        _emit_reel_activity(viewer_id, reel_id, "reel_saved")
        return True, saved
    except Exception as e:
        _log_error("save_reel", e)
        return False, False


def unsave_reel(viewer_id, reel_id):
    """Unsave a reel. Returns (success, new_state)."""
    try:
        write_query(
            "DELETE FROM chain_reel_saves WHERE profile_id = %s AND reel_id = %s",
            (viewer_id, reel_id),
        )
        sql = "UPDATE chain_reels SET saves_count = GREATEST(COALESCE(saves_count, 1) - 1, 0) WHERE id = %s"
        write_query(sql, (reel_id,))
        return True, False
    except Exception as e:
        _log_error("unsave_reel", e)
        return False, False


# ── Enhanced Share ──

def share_reel_v2(reel_id, profile_id, target=None):
    """Increment share count + emit activity + notify creator."""
    try:
        sql = "UPDATE chain_reels SET shares_count = COALESCE(shares_count, 0) + 1 WHERE id = %s"
        write_query(sql, (reel_id,))
        _emit_reel_activity(profile_id, reel_id, "reel_shared", {"target": target})
        if profile_id:
            _notify_creator("reel_shared", profile_id, reel_id)
        try:
            from services.analytics_engine import track_event
            track_event("reel_share", profile_id=profile_id, entity_type="reel", entity_id=reel_id)
        except Exception:
            pass
        return True
    except Exception as e:
        _log_error("share_reel", e)
        return False


# ── Comment Activity ──

def note_reel_comment(profile_id, reel_id):
    """Called after a comment is added — emits activity + notifies creator."""
    try:
        _emit_reel_activity(profile_id, reel_id, "reel_commented")
        _notify_creator("reel_commented", profile_id, reel_id)
        return True
    except Exception:
        return False


def get_reel_comments_summary(reel_id):
    """Return comment count + latest 3 commenters."""
    try:
        count_row = fast_query(
            "SELECT COUNT(*) AS cnt FROM chain_comments WHERE entity_type = 'reel' AND entity_id = %s",
            (reel_id,),
        )
        count = count_row[0][0] if count_row else 0
        commenters = fast_query(
            """SELECT DISTINCT c.profile_id, p.display_name, p.avatar_url
               FROM chain_comments c
               JOIN chain_profiles p ON p.id = c.profile_id
               WHERE c.entity_type = 'reel' AND c.entity_id = %s
               ORDER BY c.created_at DESC LIMIT 3""",
            (reel_id,),
        )
        return {
            "count": count,
            "commenters": [
                {"profile_id": r[0], "display_name": r[1], "avatar_url": r[2]}
                for r in commenters
            ],
        }
    except Exception as e:
        _log_error("get_reel_comments_summary", e)
        return {"count": 0, "commenters": []}


# ── Creator Analytics ──

def get_creator_reel_stats(profile_id, requesting_profile_id=None):
    """Aggregate reel stats for a creator. Respects privacy if requesting user is not the creator."""
    if requesting_profile_id and requesting_profile_id != profile_id:
        return {
            "total_reels": 0,
            "total_views": 0,
            "total_likes": 0,
            "total_comments": 0,
            "total_shares": 0,
            "total_saves": 0,
            "avg_watch_ms": 0,
            "completion_rate": 0,
        }

    try:
        stats = fast_query(
            """SELECT
                 COUNT(*) AS total_reels,
                 COALESCE(SUM(views_count), 0) AS total_views,
                 COALESCE(SUM(likes_count), 0) AS total_likes,
                 COALESCE(SUM(comments_count), 0) AS total_comments,
                 COALESCE(SUM(shares_count), 0) AS total_shares,
                 COALESCE(SUM(saves_count), 0) AS total_saves
               FROM chain_reels
               WHERE profile_id = %s AND deleted_at IS NULL AND status = 'published'""",
            (profile_id,),
        )
        if not stats:
            return {}

        r = stats[0]
        total_reels = r[0] if r[0] else 0

        watch = fast_query(
            """SELECT
                 COALESCE(AVG(watch_ms), 0) AS avg_watch_ms,
                 COALESCE(SUM(CASE WHEN completed THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0), 0) AS completion_rate
               FROM chain_reel_watch_events
               WHERE reel_id IN (SELECT id FROM chain_reels WHERE profile_id = %s AND deleted_at IS NULL)""",
            (profile_id,),
        )
        avg_watch_ms = watch[0][0] if watch else 0
        completion_rate = watch[0][1] if watch else 0

        return {
            "total_reels": total_reels,
            "total_views": r[1] or 0,
            "total_likes": r[2] or 0,
            "total_comments": r[3] or 0,
            "total_shares": r[4] or 0,
            "total_saves": r[5] or 0,
            "avg_watch_ms": round(avg_watch_ms, 1),
            "completion_rate": round(completion_rate, 4),
        }
    except Exception as e:
        _log_error("get_creator_reel_stats", e)
        return {}


# ── Helpers ──

def _emit_reel_activity(actor_id, reel_id, verb, extra_meta=None):
    """Emit reel-related activity event."""
    if not actor_id:
        return
    try:
        from services.activity_engine import emit_activity
        meta = {"reel_id": reel_id}
        if extra_meta:
            meta.update(extra_meta)
        emit_activity(
            actor_id=actor_id,
            verb=verb,
            entity_type="reel",
            entity_id=reel_id,
            metadata=meta,
        )
    except Exception:
        pass


def _notify_creator(verb, actor_id, reel_id):
    """Notify reel creator about engagement."""
    from services.notification_center_service import create_notification
    try:
        reel = fast_query("SELECT profile_id FROM chain_reels WHERE id = %s", (reel_id,))
        if reel and reel[0][0] and reel[0][0] != actor_id:
            notification_type = verb.replace("reel_", "reel_")
            create_notification(
                profile_id=reel[0][0],
                notification_type=notification_type,
                actor_id=actor_id,
                entity_type="reel",
                entity_id=reel_id,
                grouped=True,
            )
    except Exception:
        pass


def _log_error(context, exc):
    """Log an error without raising."""
    import logging
    logging.getLogger("reels_engine").exception("[%s] %s", context, exc)



