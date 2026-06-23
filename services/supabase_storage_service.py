"""
Supabase Storage Service - Dedicated service for media uploads to Supabase Storage.
This service handles all large file uploads (images, videos) for stories, posts, and reels.
"""
import os
import uuid
from datetime import datetime, timezone

from werkzeug.utils import secure_filename
from utils.supabase_client import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, get_supabase_admin


# Configuration - Use existing bucket names from supabase_storage_router
# These buckets already exist in Supabase
BUCKET_MAPPING = {
    "stories": "stories",
    "posts": "post-media",
    "reels": "reels",
}

# Default bucket for new uploads (stories)
SUPABASE_MEDIA_BUCKET = os.getenv("SUPABASE_MEDIA_BUCKET", "stories")

# Allowed file types
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "webm"}

# Max file sizes (in bytes)
MAX_IMAGE_SIZE = 100 * 1024 * 1024  # 100MB for images
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB for videos


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _extension(filename):
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def _is_allowed_image(filename):
    return _extension(filename) in ALLOWED_IMAGE_EXTENSIONS


def _is_allowed_video(filename):
    return _extension(filename) in ALLOWED_VIDEO_EXTENSIONS


def _build_storage_path(folder, owner_id, ext):
    """Generate unique storage path: {folder}/{owner_id}/{uuid}.{ext}"""
    unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else str(uuid.uuid4())
    return f"{folder}/{owner_id}/{unique_name}"


def _get_public_url(bucket, path):
    """Construct public URL for Supabase Storage."""
    return f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{bucket}/{path}"


def upload_media_to_supabase(file, folder, owner_id):
    """
    Upload media file to Supabase Storage.
    
    Args:
        file: Werkzeug FileStorage object
        folder: Storage folder (e.g., 'stories', 'posts', 'reels')
        owner_id: Profile ID of the owner
        
    Returns:
        {
            "ok": True,
            "url": public_url,
            "path": storage_path,
            "media_type": "image" or "video",
            "mime_type": file.content_type,
            "size": file_size
        }
        or
        {
            "ok": False,
            "error": error_message
        }
    """
    if not file or not getattr(file, "filename", ""):
        return {"ok": False, "error": "No file provided"}
    
    filename = secure_filename(file.filename)
    if not filename:
        return {"ok": False, "error": "Invalid filename"}
    
    ext = _extension(filename)
    mime_type = file.content_type or "application/octet-stream"
    
    # Determine media type and validate
    is_image = _is_allowed_image(filename)
    is_video = _is_allowed_video(filename)
    
    if not is_image and not is_video:
        return {"ok": False, "error": f"Unsupported file type: {ext}. Allowed: jpg, jpeg, png, webp, gif, mp4, mov, webm"}
    
    media_type = "video" if is_video else "image"
    
    # Check file size
    file_obj = file
    file_obj.seek(0, 2)  # Seek to end
    file_size = file_obj.tell()
    file_obj.seek(0)  # Reset to beginning
    
    max_size = MAX_VIDEO_SIZE if is_video else MAX_IMAGE_SIZE
    if file_size > max_size:
        return {"ok": False, "error": f"File too large. Max allowed: {max_size // (1024*1024)}MB"}
    
    # Check if Supabase is configured
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return {"ok": False, "error": "Supabase Storage is not configured"}
    
    # Build storage path
    storage_path = _build_storage_path(folder, owner_id, ext)
    # Map folder to bucket name
    bucket = BUCKET_MAPPING.get(folder, SUPABASE_MEDIA_BUCKET)
    
    try:
        # Get Supabase admin client
        supabase = get_supabase_admin()
        
        # Read file content
        file_data = file_obj.read()
        file_obj.seek(0)
        
        # Upload to Supabase Storage
        supabase.storage.from_(bucket).upload(
            path=storage_path,
            file=file_data,
            file_options={"content-type": mime_type}
        )
        
        # Generate public URL
        public_url = _get_public_url(bucket, storage_path)
        
        return {
            "ok": True,
            "url": public_url,
            "path": storage_path,
            "media_type": media_type,
            "mime_type": mime_type,
            "size": file_size
        }
        
    except Exception as e:
        error_msg = str(e)
        # Check if bucket not found
        if "bucket" in error_msg.lower() or "not found" in error_msg.lower():
            return {"ok": False, "error": f"Supabase bucket not found: {bucket}"}
        return {"ok": False, "error": f"Supabase upload failed: {error_msg}"}


def check_bucket_exists(bucket_name=None):
    """Check if the Supabase bucket exists and is accessible."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False, "Supabase Storage is not configured"
    
    try:
        supabase = get_supabase_admin()
        # Try to list buckets or access the specific bucket
        buckets = supabase.storage.list_buckets()
        bucket_names = [b.name for b in buckets]
        
        # Check all buckets in mapping
        missing_buckets = []
        for folder, bucket in BUCKET_MAPPING.items():
            if bucket not in bucket_names:
                missing_buckets.append(bucket)
        
        if missing_buckets:
            return False, f"Supabase bucket(s) not found: {', '.join(missing_buckets)}"
        
        return True, f"All buckets exist: {', '.join(BUCKET_MAPPING.values())}"
    except Exception as e:
        return False, f"Failed to check bucket: {str(e)}"


def create_buckets_if_missing():
    """Create missing buckets in Supabase Storage."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False, "Supabase Storage is not configured"
    
    try:
        supabase = get_supabase_admin()
        buckets = supabase.storage.list_buckets()
        bucket_names = [b.name for b in buckets]
        
        created = []
        for folder, bucket in BUCKET_MAPPING.items():
            if bucket not in bucket_names:
                try:
                    supabase.storage.create_bucket(bucket)
                    created.append(bucket)
                except Exception:
                    pass
        
        return True, f"Created buckets: {created}" if created else "All buckets already exist"
    except Exception as e:
        return False, f"Failed to create buckets: {str(e)}"
