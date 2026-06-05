import uuid
from services.neon_service import fast_query, write_query
from services.media_storage_service import upload_media_file
from services.media_pipeline import extract_video_duration_placeholder, queue_reel_processing, validate_upload
from services.request_cache import build_request_key, request_memoize
from services.content_service import create_reel_record, local_content

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

def create_reel(profile_id, caption, file=None, thumbnail=None, music_title="", visibility="public"):
    """Uploads video and triggers async processing."""
    if not file:
        return None, "Video file is required"
    reel, error = create_reel_record(profile_id, file, caption=caption, music_title=music_title, visibility=visibility)
    if error:
        return None, error
    return reel.get("id"), None


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

    metadata = extract_ffmpeg_metadata_placeholder(file)
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)

    # 2. Save to Neon with 'uploaded' status
    reel_id = str(uuid.uuid4())
    sql = """
        INSERT INTO chain_reels (
            id, profile_id, caption, video_url, storage_bucket, storage_path, duration_seconds, mime_type, file_size, processing_status, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploaded', now())
        RETURNING id
    """
    params = (
        reel_id, profile_id, caption, video_res['public_url'], 
        video_res['bucket'], video_res['file_path'], metadata.get("duration_seconds"), metadata.get("mime_type"), file_size
    )
    try:
        write_query(sql, params)
        # 3. Trigger processing
        queue_reel_processing(reel_id)
        return reel_id, None
    except Exception as e:
        print(f"[reels_engine] Failed to save reel: {e}")
        return None, str(e)

def record_reel_view(reel_id, viewer_profile_id=None):
    """Records a view for a reel."""
    write_query("UPDATE chain_reels SET views_count = views_count + 1 WHERE id = %s", (reel_id,))
    from services.analytics_engine import track_reel_view
    track_reel_view(reel_id, viewer_profile_id)
    return True

def like_reel(reel_id, profile_id):
    """Likes a reel."""
    sql = "UPDATE chain_reels SET likes_count = likes_count + 1 WHERE id = %s"
    write_query(sql, (reel_id,))
    from services.analytics_engine import track_event
    track_event("reel_like", profile_id=profile_id, entity_type="reel", entity_id=reel_id)
    return True

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
    return write_query(sql, (reel_id, profile_id))


def extract_ffmpeg_metadata_placeholder(file_obj):
    content_type = getattr(file_obj, "content_type", "") or ""
    return {
        **extract_video_duration_placeholder(file_obj),
        "mime_type": content_type,
    }
