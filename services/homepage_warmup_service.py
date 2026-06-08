import time

from flask import current_app, has_app_context

from engines.cache_engine import cache_key, set_cache
from services.homepage_cache_service import (
    HOMEPAGE_TTL_SECONDS,
    homepage_cache_info,
    mark_homepage_cached,
    set_full,
)
from services.homepage_service import build_homepage_payload, get_homepage_data
from services.logging_service import log_info, log_warning


def warm_homepage_cache():
    started = time.perf_counter()
    ok = True
    error = None
    try:
        payload = build_homepage_payload(async_warm=True)
        full_context = None
        if has_app_context():
            with current_app.test_request_context("/"):
                full_context = get_homepage_data()
        if full_context is None:
            full_context = {
                "current": None,
                **payload,
                "wallet": {"coin_balance": 0, "gift_earnings": 0, "label_balance": "0"},
                "hero_story_count": len(payload.get("stories", [])),
                "hero_live_count": len(payload.get("live_rooms", [])),
                "hero_profile_count": len(payload.get("recommended_profiles", [])),
                "hero_post_count": len(payload.get("trending_posts", [])),
                "missing_sources": payload.get("issues", []),
            }
            set_cache(cache_key("homepage", "full", "public"), full_context, ttl=HOMEPAGE_TTL_SECONDS)
            set_full("public", full_context, ttl=HOMEPAGE_TTL_SECONDS)
        mark_homepage_cached()
    except Exception as exc:
        ok = False
        error = str(exc)
        log_warning("homepage_cache_warmup_failed", error=error)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    result = {"ok": ok, "duration_ms": duration_ms, "cache": homepage_cache_info()}
    if error:
        result["error"] = error
    log_info("homepage_cache_warmup", **result)
    return result
