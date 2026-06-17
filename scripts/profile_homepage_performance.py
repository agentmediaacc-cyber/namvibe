#!/usr/bin/env python3
"""Profile NamVibe homepage cold and warm generation timing."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _delete_engine_key(key):
    try:
        from engines.cache_engine import delete_cache

        delete_cache(key)
    except Exception:
        pass


def clear_homepage_caches():
    from engines.cache_engine import cache_key
    from services.homepage_cache_service import invalidate_homepage_cache

    invalidate_homepage_cache()
    for key in (
        cache_key("chain_homepage_v3", "public"),
        cache_key("homepage", "full", "public"),
        cache_key("home_groups"),
        cache_key("home_sponsored"),
        cache_key("home_nearby"),
    ):
        _delete_engine_key(key)


def run_once(app, label):
    from services.homepage_service import get_homepage_data, get_homepage_performance_profile

    with app.test_request_context("/"):
        started = time.perf_counter()
        data = get_homepage_data()
        wall_ms = round((time.perf_counter() - started) * 1000, 2)
        profile = get_homepage_performance_profile()
    profile["wall_ms"] = wall_ms
    profile["label"] = label
    profile["stats"] = (data or {}).get("stats", {})
    return profile


def summarize(profile):
    sections = profile.get("sections") or {}
    slowest_section = profile.get("slowest_section") or {}
    slowest_query = profile.get("slowest_query") or {}
    return {
        "label": profile.get("label"),
        "homepage_total_ms": profile.get("homepage_total_ms") or profile.get("wall_ms"),
        "wall_ms": profile.get("wall_ms"),
        "section_timings": sections,
        "query_counts": profile.get("query_counts") or {},
        "profile_queries": profile.get("profile_queries", 0),
        "post_queries": profile.get("post_queries", 0),
        "reel_queries": profile.get("reel_queries", 0),
        "story_queries": profile.get("story_queries", 0),
        "cache_lookup_ms": profile.get("cache_lookup_ms", 0),
        "cache_store_ms": profile.get("cache_store_ms", 0),
        "slowest_section": slowest_section,
        "slowest_query": {
            "label": slowest_query.get("label"),
            "latency_ms": slowest_query.get("latency_ms"),
            "query": slowest_query.get("query"),
        },
        "stats": profile.get("stats") or {},
    }


def main():
    from app import app

    clear_homepage_caches()
    cold = run_once(app, "cold")
    warm = run_once(app, "warm")

    result = {
        "cold": summarize(cold),
        "warm": summarize(warm),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
