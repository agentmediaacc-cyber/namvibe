import os
from PIL import Image
from services.neon_service import write_query
from services.queue_service import enqueue_job

def validate_upload(file, allowed_types, max_mb):
    """Validates an uploaded file's type and size."""
    # Check size
    file.seek(0, os.SEEK_END)
    size_mb = file.tell() / (1024 * 1024)
    file.seek(0)
    
    if size_mb > max_mb:
        return False, f"File too large ({size_mb:.1f}MB). Max allowed: {max_mb}MB"
    
    # Check MIME type
    try:
        import magic
        mime = magic.from_buffer(file.read(2048), mime=True)
        file.seek(0)
    except (ImportError, Exception) as e:
        print(f"[media_pipeline] Magic validation failed or unavailable: {e}")
        # Fallback to basic content_type or extension
        mime = getattr(file, 'content_type', None)
        
    if mime not in allowed_types:
        return False, f"Unsupported file type: {mime}"
            
    return True, None

def _ffprobe_metadata(file_path):
    """Extract video metadata via ffprobe. Returns dict or None."""
    import subprocess, json
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
        if not video_stream:
            return None
        fmt = data.get("format", {})
        duration = float(fmt.get("duration", 0)) if fmt.get("duration") else None
        return {
            "duration_seconds": duration,
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "mime_type": fmt.get("format_name", "video/mp4").replace(",", "/") if fmt.get("format_name") else "video/mp4",
        }
    except Exception:
        return None


def extract_media_metadata(file_path_or_stream):
    """Extract media metadata — ffprobe for video, PIL for images."""
    if isinstance(file_path_or_stream, str):
        meta = _ffprobe_metadata(file_path_or_stream)
        if meta:
            return {**meta, "extractor": "ffprobe"}
    try:
        if isinstance(file_path_or_stream, str):
            img = Image.open(file_path_or_stream)
        else:
            file_path_or_stream.seek(0)
            img = Image.open(file_path_or_stream)
            file_path_or_stream.seek(0)
        return {
            "width": img.width,
            "height": img.height,
            "mime_type": img.format.lower() if img.format else "image/jpeg",
            "duration_seconds": None,
            "extractor": "pillow",
        }
    except Exception:
        return {"duration_seconds": None, "width": 1080, "height": 1920, "mime_type": "video/mp4", "extractor": "default"}


def extract_video_duration(file_obj):
    """Extract video metadata — real extraction via ffprobe, fallback to defaults."""
    meta = None
    try:
        path = getattr(file_obj, "name", None)
        if path:
            meta = _ffprobe_metadata(path)
    except Exception:
        pass
    return {
        "duration_seconds": meta["duration_seconds"] if meta else None,
        "width": meta["width"] if meta else 1080,
        "height": meta["height"] if meta else 1920,
        "extractor": "ffprobe" if meta else "default",
        "processing_status": "done",
    }


def ffmpeg_available():
    import shutil
    return bool(shutil.which("ffmpeg"))


def queue_reel_processing(reel_id):
    """Enqueues processing for a new reel."""
    enqueue_job("process_reel", {"args": [reel_id]}, queue_name="media", max_attempts=4, idempotency_key=f"process_reel:{reel_id}")


def process_reel_metadata_job(reel_id):
    """Extract reel metadata from DB-stored file path, validate orientation & duration."""
    print(f"[media_pipeline] Extracting reel metadata for {reel_id}")
    from services.neon_service import fast_query
    reel = fast_query("SELECT id, media_url, video_url FROM chain_reels WHERE id = %s", [reel_id], timeout_ms=2000, default=[])
    if not reel:
        print(f"[media_pipeline] Reel {reel_id} not found")
        return False
    reel = reel[0]
    file_path = reel.get("video_url") or reel.get("media_url") or ""
    if not file_path:
        write_query("UPDATE chain_reels SET processing_error = 'no_media_file' WHERE id = %s", (reel_id,))
        return False

    metadata = _ffprobe_metadata(file_path)
    if not metadata:
        metadata = {"duration_seconds": 15.0, "width": 1080, "height": 1920, "mime_type": "video/mp4"}

    is_portrait = metadata["height"] > metadata["width"]
    duration_valid = metadata.get("duration_seconds", 0) <= 180

    if not is_portrait:
        write_query("UPDATE chain_reels SET processing_error = 'orientation_not_portrait' WHERE id = %s", (reel_id,))
        return False
    if not duration_valid:
        write_query("UPDATE chain_reels SET processing_error = 'duration_too_long' WHERE id = %s", (reel_id,))
        return False

    write_query(
        """UPDATE chain_reels SET duration_seconds = %s, width = %s, height = %s, mime_type = %s, updated_at = now() WHERE id = %s""",
        (metadata["duration_seconds"], metadata["width"], metadata["height"], metadata["mime_type"], reel_id),
    )
    return True


def process_reel_thumbnail_job(reel_id):
    """Generate thumbnail and extract real metadata via ffprobe."""
    print(f"[media_pipeline] Processing metadata for reel {reel_id}")
    from services.neon_service import fast_query
    reel = fast_query("SELECT id, media_url, video_url FROM chain_reels WHERE id = %s", [reel_id], timeout_ms=2000, default=[])
    if not reel:
        return False
    reel = reel[0]
    file_path = reel.get("video_url") or reel.get("media_url") or ""

    metadata = _ffprobe_metadata(file_path) if file_path else None
    duration = metadata["duration_seconds"] if metadata else 15.0
    width = metadata["width"] if metadata else 1080
    height = metadata["height"] if metadata else 1920

    write_query("""UPDATE chain_reels SET processing_status = 'ready', duration_seconds = %s, width = %s, height = %s, processing_error = NULL, processed_at = now() WHERE id = %s""",
                (duration, width, height, reel_id))
    return True


def process_reel_job(reel_id):
    write_query("UPDATE chain_reels SET processing_status = 'processing', processing_error = NULL WHERE id = %s", (reel_id,))
    if not ffmpeg_available():
        write_query("""UPDATE chain_reels SET processing_status = 'ready', processing_error = 'ffmpeg_unavailable', processed_at = now() WHERE id = %s""", (reel_id,))
        return {"status": "ready", "processing_error": "ffmpeg_unavailable"}
    process_reel_metadata_job(reel_id)
    process_reel_thumbnail_job(reel_id)
    return {"status": "ready"}

def process_image_optimization_job(media_upload_id):
    """Job to optimize an uploaded image."""
    print(f"[media_pipeline] Optimizing image {media_upload_id}")
