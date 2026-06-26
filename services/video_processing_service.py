import uuid
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from services.neon_service import write_query, fast_query
from services.logging_service import log_info, log_error

MAX_VIDEO_DURATION_SECONDS = 120
MAX_VIDEO_SIZE_MB = 500
TARGET_RESOLUTIONS = [
    {"label": "1080p", "width": 1920, "height": 1080, "bitrate": "4M"},
    {"label": "720p",  "width": 1280, "height": 720,  "bitrate": "2.5M"},
    {"label": "480p",  "width": 854,  "height": 480,  "bitrate": "1M"},
]


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def validate_video(file_path):
    errors = []
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > MAX_VIDEO_SIZE_MB:
        errors.append(f"Video exceeds {MAX_VIDEO_SIZE_MB}MB ({size_mb:.1f}MB)")
    try:
        duration = _get_duration(file_path)
        if duration is not None and duration > MAX_VIDEO_DURATION_SECONDS:
            errors.append(f"Video exceeds {MAX_VIDEO_DURATION_SECONDS}s ({duration:.0f}s)")
    except Exception as e:
        log_error("video_validation_failed", error=str(e))
    return errors


def _get_duration(file_path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def compress_video(input_path, output_dir=None, target_label="720p"):
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="nv_compress_")
    os.makedirs(output_dir, exist_ok=True)
    resolution = None
    for r in TARGET_RESOLUTIONS:
        if r["label"] == target_label:
            resolution = r
            break
    if resolution is None:
        resolution = TARGET_RESOLUTIONS[1]
    output_path = os.path.join(output_dir, f"{uuid.uuid4().hex}.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", f"scale={resolution['width']}:{resolution['height']}:force_original_aspect_ratio=decrease,pad={resolution['width']}:{resolution['height']}:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264",
        "-preset", "fast",
        "-b:v", resolution["bitrate"],
        "-maxrate", resolution["bitrate"],
        "-bufsize", f"{int(resolution['bitrate'].rstrip('M')) * 2}M",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
        log_info("video_compressed", input=input_path, output=output_path, target=target_label)
        return output_path
    except subprocess.CalledProcessError as e:
        log_error("video_compression_failed", error=e.stderr)
        raise
    except FileNotFoundError:
        log_error("ffmpeg_not_found")
        raise


def create_processing_job(entity_type, entity_id, profile_id, input_url):
    job_id = str(uuid.uuid4())
    sql = """
        INSERT INTO chain_media_processing_jobs
            (id, entity_type, entity_id, profile_id, input_url, status,
             target_resolution, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    now = _utcnow_iso()
    params = (job_id, entity_type, entity_id, profile_id, input_url,
              "pending", "720p", now, now)
    try:
        write_query(sql, params)
        return job_id
    except Exception as e:
        log_error("create_processing_job_failed", error=str(e))
        return None


def update_job_status(job_id, status, output_url=None, error_message=None):
    sql = "UPDATE chain_media_processing_jobs SET status = %s, updated_at = %s"
    params = [status, _utcnow_iso()]
    if output_url:
        sql += ", output_url = %s"
        params.append(output_url)
    if error_message:
        sql += ", error_message = %s"
        params.append(error_message)
    sql += " WHERE id = %s"
    params.append(job_id)
    try:
        write_query(sql, tuple(params))
        return True
    except Exception as e:
        log_error("update_job_status_failed", error=str(e))
        return False


def get_pending_jobs(limit=5):
    rows = fast_query(
        """SELECT * FROM chain_media_processing_jobs
           WHERE status IN ('pending','processing')
           ORDER BY created_at ASC LIMIT %s""",
        (limit,), default=[]
    )
    return rows or []


def process_job(job_id):
    rows = fast_query(
        "SELECT * FROM chain_media_processing_jobs WHERE id = %s",
        (job_id,), default=[]
    )
    if not rows:
        return False
    job = rows[0]
    update_job_status(job_id, "processing")
    try:
        input_url = job.get("input_url")
        if not input_url:
            update_job_status(job_id, "failed", error_message="No input URL")
            return False
        target = job.get("target_resolution") or "720p"
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            import urllib.request
            urllib.request.urlretrieve(input_url, tmp_path)
            output_path = compress_video(tmp_path, target_label=target)
            from services.supabase_storage_service import upload_media_to_supabase
            with open(output_path, "rb") as f:
                import io
                file_obj = io.BytesIO(f.read())
                file_obj.name = os.path.basename(output_path)
                from werkzeug.datastructures import FileStorage
                upload_file = FileStorage(
                    stream=file_obj,
                    filename=file_obj.name,
                    content_type="video/mp4",
                )
                result = upload_media_to_supabase(
                    upload_file, "compressed", job.get("profile_id")
                )
                if result.get("ok"):
                    update_job_status(job_id, "completed", output_url=result["url"])
                    return True
                else:
                    update_job_status(job_id, "failed",
                                      error_message=result.get("error", "Upload failed"))
                    return False
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
            try:
                if os.path.exists(output_path):
                    os.unlink(output_path)
            except Exception:
                pass
    except Exception as e:
        update_job_status(job_id, "failed", error_message=str(e))
        return False


def ensure_processing_jobs_table():
    write_query("""
        CREATE TABLE IF NOT EXISTS chain_media_processing_jobs (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            profile_id TEXT NOT NULL,
            input_url TEXT NOT NULL,
            output_url TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            target_resolution TEXT DEFAULT '720p',
            error_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    write_query("""
        CREATE INDEX IF NOT EXISTS idx_media_processing_jobs_status
        ON chain_media_processing_jobs(status)
    """)
