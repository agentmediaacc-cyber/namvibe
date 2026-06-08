import time

from services.cache_service import delete, get, remember, set, status


HOMEPAGE_TTL_SECONDS = 30
SECTION_KEYS = {
    "stories": "phase51:homepage:stories",
    "reels": "phase51:homepage:reels",
    "live_rooms": "phase51:homepage:live_rooms",
    "trending_posts": "phase51:homepage:trending_posts",
    "creator_profiles": "phase51:homepage:creator_profiles",
    "dating_previews": "phase51:homepage:dating_previews",
    "nearby_users": "phase51:homepage:nearby_users",
    "payload": "phase51:homepage:payload",
    "full": "homepage:full",
    "meta": "homepage:meta",
}


def get_section(name, default=None):
    return get(SECTION_KEYS[name], default=default)


def set_section(name, value, ttl=HOMEPAGE_TTL_SECONDS):
    return set(SECTION_KEYS[name], value, ttl=ttl)


def remember_section(name, loader, ttl=HOMEPAGE_TTL_SECONDS):
    return remember(SECTION_KEYS[name], loader, ttl=ttl, default=[])


def get_payload():
    return get(SECTION_KEYS["payload"])


def set_payload(value, ttl=HOMEPAGE_TTL_SECONDS):
    return set(SECTION_KEYS["payload"], value, ttl=ttl)


def get_full(key_suffix="public"):
    return get(f"{SECTION_KEYS['full']}:{key_suffix}")


def set_full(key_suffix, value, ttl=HOMEPAGE_TTL_SECONDS):
    mark_homepage_cached()
    return set(f"{SECTION_KEYS['full']}:{key_suffix}", value, ttl=ttl)


def mark_homepage_cached():
    return set(SECTION_KEYS["meta"], {"cached_at": time.time()}, ttl=HOMEPAGE_TTL_SECONDS * 4)


def homepage_cache_info():
    meta = get(SECTION_KEYS["meta"], default={}) or {}
    full = get_full("public")
    payload = get_payload()
    cached_at = meta.get("cached_at")
    age = (time.time() - float(cached_at)) if cached_at else None
    return {
        "homepage_cached": bool(full or payload),
        "homepage_age_seconds": round(age, 2) if age is not None else None,
        "full_cached": full is not None,
        "payload_cached": payload is not None,
        "cache_backend": cache_status(),
    }


def invalidate_homepage_cache():
    for key in SECTION_KEYS.values():
        delete(key)
    delete(f"{SECTION_KEYS['full']}:public_local_cache")
    delete(f"{SECTION_KEYS['full']}:public")


def cache_status():
    return {"ttl_seconds": HOMEPAGE_TTL_SECONDS, **status()}
