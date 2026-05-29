import os
import time
import uuid

from utils.supabase_client import SUPABASE_URL, get_supabase_admin
from services.circuit_breaker import CircuitBreaker
from services.neon_service import insert_row

SUPPORTED_BUCKETS = {
    "chain-avatars",
    "chain-covers",
    "chain-posts",
    "chain-stories",
    "chain-reels",
    "chain-live",
    "chain-verification",
}

_STORAGE_HEALTH_CACHE = {"expires_at": 0.0, "payload": None}
_STORAGE_HEALTH_TTL_SECONDS = 60
_STORAGE_BREAKER = CircuitBreaker("supabase_storage", failure_threshold=3, recovery_seconds=30)


def _log(message):
    print(f"[media_storage_service] {message}")


def build_storage_path(profile_id, upload_type, filename):
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    object_name = f"{uuid.uuid4()}.{ext}" if ext else str(uuid.uuid4())
    return f"{profile_id}/{upload_type}/{object_name}"


def record_media_upload_metadata(
    *,
    profile_id,
    upload_type,
    bucket_name,
    file_path,
    public_url,
    mime_type,
    file_size,
    original_filename,
):
    payload = {
        "profile_id": profile_id,
        "upload_type": upload_type,
        "storage_bucket": bucket_name,
        "storage_path": file_path,
        "media_url": public_url,
        "mime_type": mime_type,
        "file_size": file_size,
        "original_filename": original_filename,
    }
    try:
        row = insert_row("chain_media_uploads", payload, returning="id", timeout_ms=900)
        return (row or {}).get("id")
    except Exception as error:
        _log(f"metadata insert failed: {error}")
        return None


def get_storage_health():
    now = time.monotonic()
    if _STORAGE_HEALTH_CACHE["payload"] and _STORAGE_HEALTH_CACHE["expires_at"] > now:
        return _STORAGE_HEALTH_CACHE["payload"]

    health = {
        "connected": False,
        "buckets": {},
        "error": None,
        "latency_ms": None,
        "circuit_state": _STORAGE_BREAKER.get_state(),
    }
    if not _STORAGE_BREAKER.allow():
        health["error"] = "storage_circuit_open"
        return health
    
    started = time.perf_counter()
    try:
        storage = get_supabase_admin().storage
        all_buckets = storage.list_buckets()
        bucket_names = {b.name for b in all_buckets}
        
        for name in SUPPORTED_BUCKETS:
            health["buckets"][name] = name in bucket_names
            
        health["connected"] = True
        _STORAGE_BREAKER.success()
    except Exception as error:
        health["error"] = str(error)
        _STORAGE_BREAKER.failure(error)
        _log(f"Storage health check failed: {error}")

    health["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
    _STORAGE_HEALTH_CACHE["payload"] = health
    _STORAGE_HEALTH_CACHE["expires_at"] = now + _STORAGE_HEALTH_TTL_SECONDS
    return health


def upload_media_file(file_obj, *, bucket_name, profile_id, upload_type, public=True):
    if not file_obj:
        return None, "No file provided"
    
    if bucket_name not in SUPPORTED_BUCKETS:
        return None, f"Unsupported storage category: {bucket_name}"
    if not _STORAGE_BREAKER.allow():
        return None, "Media storage is temporarily unavailable. Please try again in a few minutes."

    # Quick health check
    health = get_storage_health()
    if not health["connected"]:
        return None, "Media storage is temporarily unavailable. Please try again in a few minutes."
    
    if not health["buckets"].get(bucket_name):
        return None, f"Storage setup required for {bucket_name}. Please contact support."

    filename = os.path.basename(file_obj.filename or "").strip()
    if not filename:
        return None, "Missing filename"

    file_obj.seek(0, os.SEEK_END)
    file_size = file_obj.tell()
    file_obj.seek(0)
    file_data = file_obj.read()
    file_obj.seek(0)

    file_path = build_storage_path(profile_id, upload_type, filename)
    mime_type = getattr(file_obj, "content_type", None) or "application/octet-stream"
    public_url = None

    try:
        storage = get_supabase_admin().storage
        storage.from_(bucket_name).upload(
            path=file_path,
            file=file_data,
            file_options={"content-type": mime_type},
        )
        if public and SUPABASE_URL:
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{file_path}"

        upload_id = record_media_upload_metadata(
            profile_id=profile_id,
            upload_type=upload_type,
            bucket_name=bucket_name,
            file_path=file_path,
            public_url=public_url,
            mime_type=mime_type,
            file_size=file_size,
            original_filename=filename,
        )
        return {
            "upload_id": upload_id,
            "public_url": public_url,
            "file_path": file_path,
            "bucket": bucket_name,
        }, None
    except Exception as error:
        _STORAGE_BREAKER.failure(error)
        _log(f"upload failed: {error}")
        return None, str(error)
