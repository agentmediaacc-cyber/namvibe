import os
import time
import threading

_PRESENCE_CACHE = {}
_PRESENCE_LOCK = threading.Lock()
_PRESENCE_TTL = 90

def _redis_available():
    try:
        from services.redis_service import redis_manager
        if redis_manager and redis_manager.available:
            return True
    except Exception:
        pass
    return False

def _redis():
    from services.redis_service import redis_manager
    return redis_manager

def set_presence_cache(profile_id, status, ttl=None):
    if ttl is None:
        ttl = _PRESENCE_TTL
    profile_id = str(profile_id)
    if _redis_available():
        try:
            key = f"chain:presence:{profile_id}"
            _redis().set_json(key, {"status": status, "updated_at": time.time()}, ex=ttl)
            return
        except Exception:
            pass
    with _PRESENCE_LOCK:
        _PRESENCE_CACHE[profile_id] = {"status": status, "updated_at": time.time()}

def get_presence_cache(profile_id):
    profile_id = str(profile_id)
    if _redis_available():
        try:
            key = f"chain:presence:{profile_id}"
            val = _redis().get_json(key)
            if val:
                elapsed = time.time() - val.get("updated_at", 0)
                if elapsed < _PRESENCE_TTL:
                    return val.get("status")
        except Exception:
            pass
    with _PRESENCE_LOCK:
        entry = _PRESENCE_CACHE.get(profile_id)
        if entry:
            elapsed = time.time() - entry.get("updated_at", 0)
            if elapsed < _PRESENCE_TTL:
                return entry.get("status")
            del _PRESENCE_CACHE[profile_id]
    return None

def delete_presence_cache(profile_id):
    profile_id = str(profile_id)
    if _redis_available():
        try:
            key = f"chain:presence:{profile_id}"
            _redis().delete(key)
        except Exception:
            pass
    with _PRESENCE_LOCK:
        _PRESENCE_CACHE.pop(profile_id, None)

def bulk_get_presence_cache(profile_ids):
    result = {}
    remaining = []
    for pid in profile_ids:
        pid = str(pid)
        cached = get_presence_cache(pid)
        if cached is not None:
            result[pid] = cached
        else:
            remaining.append(pid)
    if remaining and _redis_available():
        try:
            pipe = _redis().pipeline() if hasattr(_redis(), 'pipeline') else None
            if pipe:
                for pid in remaining:
                    pipe.get(f"chain:presence:{pid}")
                responses = pipe.execute()
                for pid, val in zip(remaining, responses):
                    if val:
                        result[pid] = val
        except Exception:
            pass
    return result
