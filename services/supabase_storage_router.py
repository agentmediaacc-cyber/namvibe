import os
import uuid
from pathlib import Path

from werkzeug.utils import secure_filename

from utils.supabase_client import SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL, get_supabase_admin


BUCKET_MAPPING = {
    "avatars": "avatars",
    "covers": "covers",
    "posts": "post-media",
    "reels": "reels",
    "stories": "stories",
    "messages": "message-media",
    "voice_notes": "voice-notes",
    "documents": "documents",
    "live": "live-media",
    "marketplace": "marketplace-media",
}

MEDIA_TYPE_BY_UPLOAD = {
    "avatars": "image",
    "covers": "image",
    "posts": "image",
    "reels": "video",
    "stories": "image",
    "messages": "image",
    "voice_notes": "audio",
    "documents": "document",
    "live": "image",
    "marketplace": "image",
}

ALLOWED_EXTENSIONS = {
    "image": {"jpg", "jpeg", "png", "webp", "gif"},
    "video": {"mp4", "mov", "webm"},
    "audio": {"mp3", "m4a", "wav", "webm", "ogg"},
    "document": {"pdf", "doc", "docx", "txt", "rtf"},
}

ALLOWED_MIME_PREFIXES = {
    "image": ("image/",),
    "video": ("video/",),
    "audio": ("audio/",),
    "document": ("application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument", "text/plain", "application/rtf"),
}

MAX_SIZE_BYTES = {
    "avatars": 5 * 1024 * 1024,
    "covers": 10 * 1024 * 1024,
    "posts": 25 * 1024 * 1024,
    "reels": 250 * 1024 * 1024,
    "stories": 50 * 1024 * 1024,
    "messages": 25 * 1024 * 1024,
    "voice_notes": 10 * 1024 * 1024,
    "documents": 25 * 1024 * 1024,
    "live": 10 * 1024 * 1024,
    "marketplace": 50 * 1024 * 1024,
}


def is_production():
    return os.getenv("FLASK_ENV") == "production" or os.getenv("ENV") == "production"


def supabase_storage_configured():
    return bool(SUPABASE_URL and (SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY))


def local_uploads_allowed():
    return not is_production() and os.getenv("CHAIN_ALLOW_LOCAL_UPLOADS") == "1"


def _size(file_obj):
    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    file_obj.seek(0)
    return size


def _extension(filename):
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def _mime_allowed(mime_type, media_type):
    prefixes = ALLOWED_MIME_PREFIXES.get(media_type, ())
    return any((mime_type or "").lower().startswith(prefix) for prefix in prefixes)


def validate_upload(file_obj, upload_type):
    if upload_type not in BUCKET_MAPPING:
        return False, f"Unsupported upload type: {upload_type}", None
    if not file_obj or not getattr(file_obj, "filename", ""):
        return False, "No file provided", None

    filename = secure_filename(file_obj.filename)
    ext = _extension(filename)
    media_type = MEDIA_TYPE_BY_UPLOAD[upload_type]
    mime_type = (getattr(file_obj, "content_type", None) or "application/octet-stream").lower()
    size_bytes = _size(file_obj)

    if ext not in ALLOWED_EXTENSIONS[media_type]:
        return False, f"File extension not allowed for {media_type}", None
    if not _mime_allowed(mime_type, media_type):
        return False, f"MIME type not allowed for {media_type}: {mime_type}", None
    if size_bytes > MAX_SIZE_BYTES[upload_type]:
        limit_mb = MAX_SIZE_BYTES[upload_type] // (1024 * 1024)
        return False, f"File too large. Max allowed: {limit_mb}MB", None

    return True, None, {
        "filename": filename,
        "extension": ext,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "media_type": media_type,
    }


def build_storage_path(profile_id, upload_type, filename):
    ext = _extension(filename)
    unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    return f"{profile_id}/{upload_type}/{unique_name}"


def _public_url(bucket, path):
    return f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{bucket}/{path}"


def _save_local(file_obj, bucket, path, meta):
    root = Path("static/uploads/local-dev")
    destination = root / bucket / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_obj.save(destination)
    url = "/" + str(destination).replace(os.sep, "/")
    return _payload(url, bucket, str(destination), meta)


def _payload(url, bucket, path, meta):
    return {
        "url": url,
        "bucket": bucket,
        "path": path,
        "mime_type": meta["mime_type"],
        "size_bytes": meta["size_bytes"],
        "media_type": meta["media_type"],
        "public_url": url,
        "file_path": path,
        "file_size": meta["size_bytes"],
    }


def upload_file(file_obj, upload_type, profile_id, public=True):
    valid, error, meta = validate_upload(file_obj, upload_type)
    if not valid:
        return None, error

    bucket = BUCKET_MAPPING[upload_type]
    path = build_storage_path(profile_id, upload_type, meta["filename"])

    if not supabase_storage_configured():
        if local_uploads_allowed():
            return _save_local(file_obj, bucket, path, meta), None
        return None, "Supabase Storage is not configured; local uploads are disabled."

    try:
        file_data = file_obj.read()
        file_obj.seek(0)
        get_supabase_admin().storage.from_(bucket).upload(
            path=path,
            file=file_data,
            file_options={"content-type": meta["mime_type"]},
        )
        url = _public_url(bucket, path) if public else None
        return _payload(url, bucket, path, meta), None
    except Exception as error:
        if local_uploads_allowed():
            file_obj.seek(0)
            return _save_local(file_obj, bucket, path, meta), None
        return None, f"Supabase upload failed: {error}"


def upload_avatar(file_obj, profile_id):
    return upload_file(file_obj, "avatars", profile_id, public=True)


def upload_cover(file_obj, profile_id):
    return upload_file(file_obj, "covers", profile_id, public=True)


def upload_post_media(file_obj, profile_id):
    return upload_file(file_obj, "posts", profile_id, public=True)


def upload_reel(file_obj, profile_id):
    return upload_file(file_obj, "reels", profile_id, public=True)


def upload_story_media(file_obj, profile_id):
    return upload_file(file_obj, "stories", profile_id, public=True)


def upload_message_attachment(file_obj, profile_id):
    upload_type = "voice_notes" if (getattr(file_obj, "content_type", "") or "").startswith("audio/") else "messages"
    return upload_file(file_obj, upload_type, profile_id, public=True)


def upload_document(file_obj, profile_id):
    return upload_file(file_obj, "documents", profile_id, public=True)


def upload_live_thumbnail(file_obj, profile_id):
    return upload_file(file_obj, "live", profile_id, public=True)


def upload_marketplace_image(file_obj, profile_id):
    return upload_file(file_obj, "marketplace", profile_id, public=True)
