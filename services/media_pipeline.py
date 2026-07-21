import os
import shutil
import subprocess
from pathlib import Path
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
    return bool(shutil.which("ffmpeg"))


def ffprobe_available():
    return bool(shutil.which("ffprobe"))


def resolve_local_media_path(media_url):
    if not media_url:
        return None
    path = str(media_url).split("?", 1)[0].split("#", 1)[0]
    if "/static/uploads/" in path:
        path = path[path.index("/static/uploads/") + 1 :]
    if path.startswith("http://127.0.0.1") or path.startswith("https://namvibe.com") or path.startswith("http://namvibe.com"):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(path)
            path = parsed.path or ""
        except Exception:
            return None
    if path.startswith("/static/uploads/"):
        return Path(path.lstrip("/"))
    if path.startswith("static/uploads/"):
        return Path(path)
    return None


def normalize_public_media_url(media_url):
    """Return a public-facing media URL/path without filesystem prefixes."""
    if not media_url:
        return ""
    value = str(media_url).strip()
    if not value:
        return ""
    if value.startswith("file://"):
        return ""
    if "/static/uploads/" in value:
        idx = value.index("/static/uploads/")
        candidate = value[idx:]
        local_path = resolve_local_media_path(candidate)
        if local_path is not None and not Path(local_path).exists():
            return ""
        return candidate
    if value.startswith("static/uploads/"):
        candidate = "/" + value.lstrip("/")
        local_path = resolve_local_media_path(candidate)
        if local_path is not None and not Path(local_path).exists():
            return ""
        return candidate
    local_path = resolve_local_media_path(value)
    if local_path:
        if not local_path.exists():
            return ""
        public = "/" + local_path.as_posix().lstrip("/")
        return public if public.startswith("/static/uploads/") else ""
    return value


def probe_video_metadata(file_path):
    if not ffprobe_available():
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=index,codec_type,codec_name,profile,pix_fmt,width,height,r_frame_rate,avg_frame_rate,bit_rate",
                "-show_entries",
                "format=format_name,duration,size,bit_rate,start_time",
                "-of",
                "json",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        import json

        return json.loads(result.stdout)
    except Exception:
        return None


def build_reel_thumbnail(source_path, output_path=None, *, at_seconds=0.5, max_width=720):
    if not ffmpeg_available():
        return None, "ffmpeg_unavailable"
    source_path = Path(source_path)
    if not source_path.exists():
        return None, "source_missing"
    output_path = Path(output_path) if output_path else source_path.with_suffix(".jpg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(at_seconds),
        "-i", str(source_path),
        "-frames:v", "1",
        "-vf", f"scale='min({max_width},iw)':-2",
        "-q:v", "3",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0 or not output_path.exists():
        return None, "thumbnail_failed"
    return str(output_path), None


def ensure_faststart_copy(source_path, output_path=None):
    if not ffmpeg_available():
        return None, "ffmpeg_unavailable"
    source_path = Path(source_path)
    if not source_path.exists():
        return None, "source_missing"
    output_path = Path(output_path) if output_path else source_path.with_name(f"{source_path.stem}.faststart{source_path.suffix}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 or not output_path.exists():
        return None, "faststart_failed"
    return str(output_path), None


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
    file_path = normalize_public_media_url(reel.get("video_url") or reel.get("media_url") or "")
    local_path = resolve_local_media_path(file_path)
    if not file_path:
        write_query("UPDATE chain_reels SET processing_error = 'no_media_file' WHERE id = %s", (reel_id,))
        return False

    raw_metadata = probe_video_metadata(local_path) if local_path else _ffprobe_metadata(file_path)
    if not raw_metadata:
        write_query(
            """UPDATE chain_reels SET processing_status = 'failed', processing_error = 'invalid_video_metadata', processed_at = now() WHERE id = %s""",
            (reel_id,),
        )
        return False

    streams = raw_metadata.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None) if isinstance(streams, list) else None
    if local_path and (not video_stream or video_stream.get("codec_name") in {"svg", None}):
        write_query(
            """UPDATE chain_reels SET processing_status = 'failed', processing_error = 'unsupported_video_codec', processed_at = now() WHERE id = %s""",
            (reel_id,),
        )
        return False

    fmt = raw_metadata.get("format", {}) if isinstance(raw_metadata, dict) else {}
    duration = None
    width = None
    height = None
    mime_type = "video/mp4"
    if local_path:
        duration = float(fmt.get("duration") or 0) if fmt.get("duration") else 0
        width = int(video_stream.get("width") or 0) if video_stream else 0
        height = int(video_stream.get("height") or 0) if video_stream else 0
        mime_type = "video/mp4"
        if duration <= 0 or width <= 0 or height <= 0:
            write_query(
                """UPDATE chain_reels SET processing_status = 'failed', processing_error = 'invalid_video_dimensions_or_duration', processed_at = now() WHERE id = %s""",
                (reel_id,),
            )
            return False
    else:
        duration = float(fmt.get("duration") or 15.0) if fmt.get("duration") else 15.0
        width = int(video_stream.get("width") or 1080) if video_stream else 1080
        height = int(video_stream.get("height") or 1920) if video_stream else 1920
        mime_type = "video/mp4"

    is_portrait = height > width
    duration_valid = duration <= 180

    if not is_portrait:
        write_query("UPDATE chain_reels SET processing_error = 'orientation_not_portrait' WHERE id = %s", (reel_id,))
        return False
    if not duration_valid:
        write_query("UPDATE chain_reels SET processing_error = 'duration_too_long' WHERE id = %s", (reel_id,))
        return False

    write_query(
        """UPDATE chain_reels SET duration_seconds = %s, width = %s, height = %s, mime_type = %s, updated_at = now() WHERE id = %s""",
        (duration, width, height, mime_type, reel_id),
    )
    return True


def process_reel_thumbnail_job(reel_id):
    """Generate thumbnail and extract real metadata via ffprobe."""
    print(f"[media_pipeline] Processing metadata for reel {reel_id}")
    from services.neon_service import fast_query
    reel = fast_query("SELECT id, media_url, video_url, thumbnail_url FROM chain_reels WHERE id = %s", [reel_id], timeout_ms=2000, default=[])
    if not reel:
        return False
    reel = reel[0]
    file_path = normalize_public_media_url(reel.get("video_url") or reel.get("media_url") or "")
    local_path = resolve_local_media_path(file_path)
    thumbnail_url = normalize_public_media_url(reel.get("thumbnail_url") or reel.get("poster_url") or "")

    metadata = _ffprobe_metadata(file_path) if file_path else None
    duration = metadata["duration_seconds"] if metadata else 15.0
    width = metadata["width"] if metadata else 1080
    height = metadata["height"] if metadata else 1920

    if local_path and not thumbnail_url:
        thumb_path = local_path.with_suffix(".jpg")
        thumb_url, _ = build_reel_thumbnail(local_path, thumb_path)
        if thumb_url:
            thumbnail_url = normalize_public_media_url(thumb_url)

    if thumbnail_url:
        write_query(
            """UPDATE chain_reels SET processing_status = 'ready', duration_seconds = %s, width = %s, height = %s, thumbnail_url = %s, processing_error = NULL, processed_at = now() WHERE id = %s""",
            (duration, width, height, thumbnail_url, reel_id),
        )
    else:
        if local_path and (not local_path.exists()):
            write_query(
                """UPDATE chain_reels SET processing_status = 'failed', processing_error = 'missing_video_file', processed_at = now() WHERE id = %s""",
                (reel_id,),
            )
            return False
        write_query(
            """UPDATE chain_reels SET processing_status = 'ready', duration_seconds = %s, width = %s, height = %s, processing_error = NULL, processed_at = now() WHERE id = %s""",
            (duration, width, height, reel_id),
        )
    return True


def process_reel_job(reel_id):
    write_query("UPDATE chain_reels SET processing_status = 'processing', processing_error = NULL WHERE id = %s", (reel_id,))
    if not ffmpeg_available():
        write_query("""UPDATE chain_reels SET processing_status = 'ready', processing_error = 'ffmpeg_unavailable', processed_at = now() WHERE id = %s""", (reel_id,))
        return {"status": "ready", "processing_error": "ffmpeg_unavailable"}
    meta_ok = process_reel_metadata_job(reel_id)
    thumb_ok = process_reel_thumbnail_job(reel_id) if meta_ok else False
    if not meta_ok or not thumb_ok:
        write_query("""UPDATE chain_reels SET processing_status = 'failed', processed_at = now() WHERE id = %s""", (reel_id,))
        return {"status": "failed"}
    return {"status": "ready"}

def process_image_optimization_job(media_upload_id):
    """Job to optimize an uploaded image."""
    print(f"[media_pipeline] Optimizing image {media_upload_id}")
