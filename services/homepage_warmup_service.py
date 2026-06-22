import time

from services.homepage_cache_service import (
    HOMEPAGE_TTL_SECONDS,
    homepage_cache_info,
    mark_homepage_cached,
    set_full,
    get_full,
    get_payload,
)
from services.homepage_service import build_homepage_payload, get_homepage_data
from services.logging_service import log_info, log_warning
from engines.cache_engine import cache_key, set_cache

from flask import has_app_context, current_app


def warm_homepage_cache():
    started = time.perf_counter()
    ok = True
    error = None

    # ── Fast path: cache already exists, just refresh meta ──
    info = homepage_cache_info()
    if info.get("homepage_cached"):
        mark_homepage_cached()
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        log_info(
            "homepage_cache_warmup_skipped",
            reason="cache_already_exists",
            duration_ms=duration_ms,
            cache_age_seconds=info.get("homepage_age_seconds"),
        )
        return {
            "ok": True,
            "duration_ms": duration_ms,
            "skipped": True,
            "cache": info,
        }

    # ── Cold start: lightweight payload warmup only (no full context) ──
    try:
        payload = build_homepage_payload(async_warm=True)

        # Store a minimal full context from the payload (avoids duplicate
        # expensive calls to get_homepage_data on cold start)
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
        set_cache(
            cache_key("homepage", "full", "public"),
            full_context,
            ttl=HOMEPAGE_TTL_SECONDS,
        )
        set_full("public", full_context, ttl=HOMEPAGE_TTL_SECONDS)

        if has_app_context() and (payload.get("stories") or payload.get("reels")):
            with current_app.test_request_context("/"):
                try:
                    full_context = get_homepage_data()
                    set_cache(
                        cache_key("homepage", "full", "public"),
                        full_context,
                        ttl=HOMEPAGE_TTL_SECONDS,
                    )
                    set_full("public", full_context, ttl=HOMEPAGE_TTL_SECONDS)
                except Exception:
                    pass  # non-blocking — payload cache is already populated

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
