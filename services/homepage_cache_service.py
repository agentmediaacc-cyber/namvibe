import time

from engines.cache_engine import get_cache as _get_local_cache, set_cache as _set_local_cache
from services.cache_service import delete, get, remember, set, status


HOMEPAGE_TTL_SECONDS = 60
HOMEPAGE_STALE_TTL_SECONDS = HOMEPAGE_TTL_SECONDS * 5
SECTION_KEYS = {
    "stories": "phase51:homepage:stories",
    "reels": "phase51:homepage:reels",
    "live_rooms": "phase51:homepage:live_rooms",
    "trending_posts": "phase51:homepage:trending_posts",
    "creator_profiles": "phase51:homepage:creator_profiles",
    "dating_previews": "phase51:homepage:dating_previews",
    "nearby_users": "phase51:homepage:nearby_users",
    "suggested_people": "phase51:homepage:suggested_people",
    "payload": "phase51:homepage:payload",
    "full": "homepage:full",
    "full_stale": "homepage:full:stale",
    "meta": "homepage:meta",
}


def get_section(name, default=None):
    return get(SECTION_KEYS[name], default=default)


def set_section(name, value, ttl=HOMEPAGE_TTL_SECONDS):
    return set(SECTION_KEYS[name], value, ttl=ttl)


def remember_section(name, loader, ttl=HOMEPAGE_TTL_SECONDS):
    return remember(SECTION_KEYS[name], loader, ttl=ttl, default=[])


def get_payload():
    local = _get_local_cache(SECTION_KEYS["payload"])
    if local is not None:
        return local
    value = get(SECTION_KEYS["payload"])
    if value is not None:
        _set_local_cache(SECTION_KEYS["payload"], value, ttl=HOMEPAGE_TTL_SECONDS)
    return value


def get_payload_with_stale():
    payload = get_payload()
    if payload is not None:
        return payload, False
    key = SECTION_KEYS["payload"]
    stale_key = f"{key}:stale"
    local = _get_local_cache(stale_key)
    if local is not None:
        return local, True
    value = get(stale_key)
    if value is not None:
        _set_local_cache(stale_key, value, ttl=HOMEPAGE_STALE_TTL_SECONDS)
        return value, True
    return None, False


def set_payload(value, ttl=HOMEPAGE_TTL_SECONDS):
    _set_local_cache(SECTION_KEYS["payload"], value, ttl=ttl)
    set(SECTION_KEYS["payload"], value, ttl=ttl)
    _set_local_cache(f"{SECTION_KEYS['payload']}:stale", value, ttl=HOMEPAGE_STALE_TTL_SECONDS)
    return set(f"{SECTION_KEYS['payload']}:stale", value, ttl=HOMEPAGE_STALE_TTL_SECONDS)


def get_full(key_suffix="public"):
    key = f"{SECTION_KEYS['full']}:{key_suffix}"
    local = _get_local_cache(key)
    if local is not None:
        return local
    value = get(key)
    if value is not None:
        _set_local_cache(key, value, ttl=HOMEPAGE_TTL_SECONDS)
    return value


def get_full_with_stale(key_suffix="public"):
    fresh = get_full(key_suffix)
    if fresh is not None:
        return fresh, False
    key = f"{SECTION_KEYS['full']}:{key_suffix}:stale"
    local = _get_local_cache(key)
    if local is not None:
        return local, True
    value = get(key)
    if value is not None:
        _set_local_cache(key, value, ttl=HOMEPAGE_STALE_TTL_SECONDS)
        return value, True
    return None, False


def set_full(key_suffix, value, ttl=HOMEPAGE_TTL_SECONDS):
    mark_homepage_cached()
    _set_local_cache(f"{SECTION_KEYS['full']}:{key_suffix}", value, ttl=ttl)
    set(f"{SECTION_KEYS['full']}:{key_suffix}", value, ttl=ttl)
    stale_key = f"{SECTION_KEYS['full']}:{key_suffix}:stale"
    _set_local_cache(stale_key, value, ttl=HOMEPAGE_STALE_TTL_SECONDS)
    return set(stale_key, value, ttl=HOMEPAGE_STALE_TTL_SECONDS)


def mark_homepage_cached():
    return set(SECTION_KEYS["meta"], {"cached_at": time.time()}, ttl=HOMEPAGE_TTL_SECONDS * 4)


def homepage_cache_info():
    meta = get(SECTION_KEYS["meta"], default={}) or {}
    full, full_stale = get_full_with_stale("public")
    payload, payload_stale = get_payload_with_stale()
    cached_at = meta.get("cached_at")
    age = (time.time() - float(cached_at)) if cached_at else None
    return {
        "homepage_cached": bool(full or payload),
        "homepage_age_seconds": round(age, 2) if age is not None else None,
        "full_cached": full is not None,
        "full_stale_cached": bool(full_stale),
        "payload_cached": payload is not None,
        "payload_stale_cached": bool(payload_stale),
        "cache_backend": cache_status(),
    }


def invalidate_homepage_cache():
    for key in SECTION_KEYS.values():
        delete(key)
    delete(f"{SECTION_KEYS['full']}:public_local_cache")
    delete(f"{SECTION_KEYS['full']}:public")
    delete(f"{SECTION_KEYS['full']}:public:stale")
    delete(f"{SECTION_KEYS['payload']}:stale")


def cache_status():
    return {"ttl_seconds": HOMEPAGE_TTL_SECONDS, **status()}
