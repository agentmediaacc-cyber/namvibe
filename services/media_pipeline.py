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

def extract_media_metadata(file_path_or_stream):
    """Placeholder for metadata extraction (width, height, duration)."""
    try:
        img = Image.open(file_path_or_stream)
        return {
            "width": img.width,
            "height": img.height,
            "mime_type": img.format.lower() if img.format else None,
            "duration_seconds": None,
            "extractor": "image-placeholder",
        }
    except:
        return {"duration_seconds": None, "extractor": "ffmpeg-placeholder"}


def extract_video_duration_placeholder(file_obj):
    return {
        "duration_seconds": None,
        "width": None,
        "height": None,
        "extractor": "ffmpeg-placeholder",
        "processing_status": "queued",
    }


def ffmpeg_available():
    return bool(getattr(__import__("shutil"), "which")("ffmpeg"))

def queue_reel_processing(reel_id):
    """Enqueues processing for a new reel."""
    enqueue_job("process_reel", {"args": [reel_id]}, queue_name="media", max_attempts=4, idempotency_key=f"process_reel:{reel_id}")


def process_reel_metadata_job(reel_id):
    """Job to extract metadata and validate portrait orientation and duration."""
    print(f"[media_pipeline] Extracting reel metadata for {reel_id}")
    
    # Real implementations should use ffprobe
    metadata = {
        "duration_seconds": 15.0,
        "width": 1080,
        "height": 1920,
        "mime_type": "video/mp4"
    }
    
    # 1. Validation
    is_portrait = metadata["height"] > metadata["width"]
    duration_valid = metadata["duration_seconds"] <= 180
    
    if not is_portrait:
        write_query("UPDATE chain_reels SET processing_error = 'orientation_not_portrait' WHERE id = %s", (reel_id,))
        return False
        
    if not duration_valid:
        write_query("UPDATE chain_reels SET processing_error = 'duration_too_long' WHERE id = %s", (reel_id,))
        return False

    write_query(
        """
        UPDATE chain_reels
        SET duration_seconds = %s,
            width = %s,
            height = %s,
            mime_type = %s,
            updated_at = now()
        WHERE id = %s
        """,
        (
            metadata["duration_seconds"],
            metadata["width"],
            metadata["height"],
            metadata["mime_type"],
            reel_id
        ),
    )
    return True

def process_reel_thumbnail_job(reel_id):
    """Job to generate a thumbnail and extract video metadata (Stub)."""
    # In production, this should switch to ffmpeg-python / ffprobe for accurate metadata extraction.
    print(f"[media_pipeline] Processing metadata for reel {reel_id}")
    
    # Simulate metadata extraction
    duration = 15.5
    width = 1080
    height = 1920
    
    write_query("""
        UPDATE chain_reels 
        SET processing_status = 'ready', 
            duration_seconds = %s, 
            width = %s, 
            height = %s, 
            processing_error = NULL,
            processed_at = now() 
        WHERE id = %s
    """, (duration, width, height, reel_id))
    return True


def process_reel_job(reel_id):
    write_query("UPDATE chain_reels SET processing_status = 'processing', processing_error = NULL WHERE id = %s", (reel_id,))
    if not ffmpeg_available():
        write_query(
            """
            UPDATE chain_reels
            SET processing_status = 'ready',
                processing_error = 'ffmpeg_unavailable',
                processed_at = now()
            WHERE id = %s
            """,
            (reel_id,),
        )
        return {"status": "ready", "processing_error": "ffmpeg_unavailable"}
    process_reel_metadata_job(reel_id)
    process_reel_thumbnail_job(reel_id)
    return {"status": "ready"}

def process_image_optimization_job(media_upload_id):
    """Job to optimize an uploaded image."""
    print(f"[media_pipeline] Optimizing image {media_upload_id}")
