#!/usr/bin/env python3
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.logging_service import log_info, log_warning
from services.neon_service import get_neon_health, get_table_columns
from services.homepage_warmup_service import warm_homepage_cache
from services.live_service import prime_live_rooms_public_cache
from services.reels_service import get_reel_feed, build_public_reels_feed_cache_key
from services.content_service import get_reels_content_version
from services.redis_service import redis_manager


def _stage(name, fn, required=True):
    started = time.perf_counter()
    try:
        result = fn()
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        log_info("runtime_warm_stage", stage=name, duration_ms=elapsed, ok=True)
        print(f"{name}: ok {elapsed:.2f}ms")
        return True, result
    except Exception as exc:
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        log_warning("runtime_warm_stage_failed", stage=name, duration_ms=elapsed, error_type=type(exc).__name__)
        print(f"{name}: failed {elapsed:.2f}ms {type(exc).__name__}", file=sys.stderr)
        return (not required), None


def warm_schema():
    for table in ("chain_profiles", "chain_reels", "chain_posts", "chain_live_rooms"):
        get_table_columns(table, timeout_ms=1500)
    return True


def warm_homepage():
    return warm_homepage_cache()


def warm_reels():
    version = get_reels_content_version("public")
    payload = get_reel_feed(limit=5, cursor=None, viewer_id=None)
    key = build_public_reels_feed_cache_key(content_version=version, limit=5, cursor="first", feed_type="public")
    cached = redis_manager.get_json_result(key)
    direct = redis_manager.get_client().get("chain:" + key) if redis_manager.get_client() else None
    ttl = redis_manager.get_ttl(key)
    print(f"REELS_CACHE_KEY={key}")
    print(f"REELS_CACHE_BACKEND={cached.get('backend')}")
    print(f"REELS_CACHE_SHARED={cached.get('shared')}")
    print(f"REELS_CACHE_EXISTS={cached.get('value') is not None}")
    print(f"REELS_CACHE_TTL={ttl}")
    print(f"REELS_CACHE_ITEMS={len((payload or {}).get('items', []))}")
    print(f"REELS_WARM_VERIFIED={bool(cached.get('value')) and direct is not None and ttl > 0}")
    if not (cached.get("shared") and cached.get("value") is not None and direct is not None and ttl > 0):
        raise RuntimeError("reels warm verification failed")
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description="Warm production runtime caches without blocking Gunicorn boot.")
    parser.add_argument("--schema", action="store_true", help="Warm schema metadata.")
    parser.add_argument("--homepage", action="store_true", help="Warm homepage cache.")
    parser.add_argument("--reels", action="store_true", help="Warm public Reels cache.")
    parser.add_argument("--all", action="store_true", help="Warm schema, homepage, and Reels caches.")
    args = parser.parse_args(argv)

    if not (args.schema or args.homepage or args.reels or args.all):
        args.homepage = True
        args.reels = True

    stages = []
    if args.all or args.schema:
        stages.append(("schema", warm_schema, True))
    if args.all or args.homepage:
        stages.append(("homepage", warm_homepage, True))
    if args.all or args.reels:
        stages.append(("reels", warm_reels, True))

    started = time.perf_counter()
    health_started = time.perf_counter()
    health = get_neon_health()
    health_ms = round((time.perf_counter() - health_started) * 1000, 2)
    print(f"neon_health={health.get('status')} latency_ms={health.get('latency_ms')} checked_ms={health_ms:.2f}")

    redis_health = redis_manager.get_health()
    print(f"redis_backend={redis_health.get('backend')} shared={redis_health.get('shared')} persistent={redis_health.get('persistent')}")

    lock = redis_manager.acquire_lock("runtime:warm:lock", ttl=120)
    if lock.get("shared"):
        print("runtime_lock=shared")
    else:
        print(f"runtime_lock={lock.get('backend')}")

    ok = True
    try:
        if lock.get("success"):
            for name, fn, required in stages:
                stage_ok, _ = _stage(name, fn, required=required)
                ok = ok and stage_ok
        else:
            print("runtime_warm_skipped_existing_lock=True")
            ok = False
    finally:
        if lock.get("success") and lock.get("token"):
            release = redis_manager.release_lock("runtime:warm:lock", lock.get("token"))
            print(f"runtime_lock_released={release.get('success')}")

    total_ms = round((time.perf_counter() - started) * 1000, 2)
    log_info("runtime_warm_complete", total_ms=total_ms, ok=ok, stages=[name for name, _, _ in stages])
    print(f"total_ms={total_ms:.2f}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
