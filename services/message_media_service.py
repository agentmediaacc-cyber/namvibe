from services.storage_service import safe_upload_file


MAX_MESSAGE_FILE_SIZE = 50 * 1024 * 1024
MAX_VOICE_FILE_SIZE = 10 * 1024 * 1024

ALLOWED_MIME_PREFIXES = ("image/", "video/", "audio/")
ALLOWED_DOCUMENT_MIMES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


def file_size(file_obj):
    pos = file_obj.tell()
    file_obj.seek(0, 2)
    size = file_obj.tell()
    file_obj.seek(pos)
    return size


def classify_mime(mime_type):
    mime_type = (mime_type or "").lower()
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("audio/"):
        return "voice"
    if mime_type in ALLOWED_DOCUMENT_MIMES:
        return "document"
    return None


def validate_message_attachment(file_obj, voice=False):
    if not file_obj or not getattr(file_obj, "filename", ""):
        return {"ok": False, "error": "file_required"}
    mime_type = (getattr(file_obj, "content_type", "") or "").lower()
    if not (mime_type.startswith(ALLOWED_MIME_PREFIXES) or mime_type in ALLOWED_DOCUMENT_MIMES):
        return {"ok": False, "error": "invalid_mime_type"}
    size = file_size(file_obj)
    limit = MAX_VOICE_FILE_SIZE if voice or mime_type.startswith("audio/") else MAX_MESSAGE_FILE_SIZE
    if size > limit:
        return {"ok": False, "error": "file_too_large"}
    return {
        "ok": True,
        "mime_type": mime_type,
        "file_size": size,
        "media_type": classify_mime(mime_type),
    }


def upload_message_media(file_obj, profile_id, voice=False):
    validation = validate_message_attachment(file_obj, voice=voice)
    if not validation.get("ok"):
        return validation
    result = safe_upload_file(file_obj, "message", profile_id=profile_id)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "upload_failed")}
    meta = result.get("meta") or {}
    return {
        "ok": True,
        "url": result.get("url"),
        "storage": result.get("storage"),
        "media_type": validation["media_type"],
        "mime_type": validation["mime_type"],
        "file_size": validation["file_size"],
        "storage_bucket": meta.get("bucket"),
        "storage_path": meta.get("path") or meta.get("file_path"),
    }
