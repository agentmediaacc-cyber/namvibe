"""Storage Health Service — safe Supabase storage operations with graceful fallback.

Never crashes the page if a bucket is missing or Supabase is slow.
Returns clear JSON error codes for the frontend.
"""

import os
from typing import Optional

from services.logging_service import log_warning
from utils.supabase_client import SUPABASE_URL

_REQUIRED_BUCKETS = [
    "avatars", "covers", "posts", "reels", "stories",
    "voice-notes", "messages", "documents", "thumbnails",
]

_PUBLIC_BUCKETS = {"avatars", "covers", "posts", "reels", "stories", "thumbnails"}
_PRIVATE_BUCKETS = {"voice-notes", "messages", "documents"}

_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

_ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "video/mp4", "video/quicktime", "video/x-msvideo",
    "audio/mpeg", "audio/ogg", "audio/wav", "audio/webm",
    "application/pdf", "text/plain",
}


def _get_supabase():
    try:
        from utils.supabase_client import get_supabase_admin
        return get_supabase_admin()
    except Exception:
        return None


def check_supabase_storage() -> dict:
    """Check Supabase storage status. Returns dict with {ok, buckets, errors}."""
    sb = _get_supabase()
    if not sb:
        return {"ok": False, "error": "supabase_client_unavailable"}
    try:
        resp = sb.storage.list_buckets()
        existing = set()
        for b in (resp or []):
            if isinstance(b, dict):
                existing.add(b.get("name") or b.get("id"))
            else:
                existing.add(getattr(b, "name", None) or getattr(b, "id", None) or str(b))
        existing.discard(None)
        missing = [b for b in _REQUIRED_BUCKETS if b not in existing]
        return {
            "ok": len(missing) == 0,
            "bucket_count": len(existing),
            "expected_buckets": list(_REQUIRED_BUCKETS),
            "existing_buckets": sorted(existing),
            "missing_buckets": missing,
            "error": None if len(missing) == 0 else "buckets_missing",
        }
    except Exception as e:
        log_warning("storage_health_check_failed", error=str(e)[:200])
        return {"ok": False, "error": "storage_check_failed"}


def ensure_required_buckets() -> dict:
    """Create missing required buckets. Returns {ok, created, errors}."""
    sb = _get_supabase()
    if not sb:
        return {"ok": False, "error": "supabase_client_unavailable"}
    created = []
    errors = []
    try:
        resp = sb.storage.list_buckets()
        existing = set()
        for b in (resp or []):
            if isinstance(b, dict):
                existing.add(b.get("name") or b.get("id"))
            else:
                existing.add(getattr(b, "name", None) or getattr(b, "id", None) or str(b))
        existing.discard(None)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    for bucket in _REQUIRED_BUCKETS:
        if bucket not in existing:
            try:
                is_public = bucket in _PUBLIC_BUCKETS
                sb.storage.create_bucket(bucket, options={"public": is_public})
                created.append(bucket)
            except Exception as e:
                errors.append({"bucket": bucket, "error": str(e)[:100]})
    return {"ok": len(errors) == 0, "created": created, "errors": errors}


def get_storage_status() -> dict:
    """Get full storage health status for the /system/storage-status route."""
    health = check_supabase_storage()
    return {
        "supabase": health,
        "local_fallback": os.path.isdir("static/uploads") if os.path.exists("static/uploads") else False,
        "max_file_size": _MAX_FILE_SIZE,
        "allowed_mime_types": list(_ALLOWED_MIME_TYPES),
    }


def safe_upload_file(bucket: str, file_path: str, file_data: bytes, content_type: Optional[str] = None) -> dict:
    """Upload a file to Supabase storage with safety checks.

    Returns dict with {ok, url, error} or {ok: False, error: code}.
    """
    if bucket not in _REQUIRED_BUCKETS:
        return {"ok": False, "error": "invalid_bucket"}
    if len(file_data) > _MAX_FILE_SIZE:
        return {"ok": False, "error": "upload_too_large"}
    if content_type and content_type not in _ALLOWED_MIME_TYPES:
        return {"ok": False, "error": "unsupported_file_type"}
    sb = _get_supabase()
    if not sb:
        return {"ok": False, "error": "storage_unavailable"}
    try:
        sb.storage.from_(bucket).upload(file_path, file_data, {"content-type": content_type or "application/octet-stream"})
        if bucket in _PUBLIC_BUCKETS:
            url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{bucket}/{file_path}"
        else:
            url = f"{bucket}/{file_path}"
        return {"ok": True, "url": url}
    except Exception as e:
        err = str(e).lower()
        if "bucket" in err and "not found" in err:
            ensure_required_buckets()
            return {"ok": False, "error": "bucket_missing", "fixed": True}
        log_warning("storage_upload_failed", bucket=bucket, path=file_path, error=str(e)[:200])
        return {"ok": False, "error": "storage_unavailable"}


def safe_delete_file(bucket: str, file_path: str) -> dict:
    """Delete a file from Supabase storage safely."""
    if bucket not in _REQUIRED_BUCKETS:
        return {"ok": False, "error": "invalid_bucket"}
    sb = _get_supabase()
    if not sb:
        return {"ok": False, "error": "storage_unavailable"}
    try:
        sb.storage.from_(bucket).remove([file_path])
        return {"ok": True}
    except Exception as e:
        log_warning("storage_delete_failed", bucket=bucket, path=file_path, error=str(e)[:200])
        return {"ok": False, "error": "delete_failed"}
