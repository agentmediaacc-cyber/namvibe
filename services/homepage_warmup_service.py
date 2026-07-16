import time
import threading

from services.homepage_cache_service import (
    HOMEPAGE_TTL_SECONDS,
    homepage_cache_info,
    mark_homepage_cached,
    set_full,
    get_full,
    get_payload,
)
from services.logging_service import log_info, log_warning
from engines.cache_engine import cache_key, set_cache

_REFRESH_LOCK = threading.Lock()
_REFRESH_IN_FLIGHT = False
_REFRESH_EVENT = threading.Event()
_REFRESH_EVENT.set()


def is_homepage_refresh_in_flight():
    with _REFRESH_LOCK:
        return _REFRESH_IN_FLIGHT


def wait_for_homepage_refresh(timeout_seconds=0.0):
    if timeout_seconds <= 0:
        return is_homepage_refresh_in_flight()
    if not is_homepage_refresh_in_flight():
        return False
    return _REFRESH_EVENT.wait(timeout_seconds)


def _refresh_worker():
    global _REFRESH_IN_FLIGHT
    try:
        warm_homepage_cache()
    except Exception as exc:
        log_warning("homepage_cache_warmup_uncaught", error=str(exc))
    finally:
        with _REFRESH_LOCK:
            _REFRESH_IN_FLIGHT = False
            _REFRESH_EVENT.set()


def schedule_homepage_refresh():
    global _REFRESH_IN_FLIGHT
    with _REFRESH_LOCK:
        if _REFRESH_IN_FLIGHT:
            return False
        _REFRESH_IN_FLIGHT = True
        _REFRESH_EVENT.clear()
    threading.Thread(target=_refresh_worker, daemon=True).start()
    return True


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
        from api_routes.homepage_api import _build_homepage_contract

        payload = _build_homepage_contract(
            viewer_id=None,
            limit=6,
            include_widgets=False,
            cold_start=True,
        ) or {}
        has_content = bool(
            payload.get("feed_items")
            or payload.get("posts")
            or payload.get("reels")
            or payload.get("stories")
            or payload.get("live_rooms")
        )
        if not has_content:
            raise RuntimeError("homepage refresh produced no public content")

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
