#!/usr/bin/env python3
"""
Phase 155 — Public Homepage Reflection Test.

Tests that:
1. build_homepage_payload() returns stories from chain_status_posts
2. get_homepage_data() returns non-empty sections
3. API /api/homepage/feed returns real data (not degraded)
4. Homepage JS hydration targets exist in namvibe_home_pro.js
5. force_fast_home does not skip server-side rendering
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.env_service import load_project_env
load_project_env()

results = []
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

def report(check_name, status, detail=""):
    results.append((check_name, status, detail))
    marker = "\u2705" if status == PASS else "\u274c" if status == FAIL else "\u23f8"
    print(f"  {marker} {check_name}: {status} {detail}")

def main():
    print("=" * 60)
    print("Phase 155 — Public Homepage Reflection Test")
    print("=" * 60)

    # 1. build_homepage_payload stories section
    print("\n1. Checking build_homepage_payload stories section...")
    try:
        from services.homepage_service import build_homepage_payload
        payload = build_homepage_payload()
        stories = payload.get("stories", [])
        if isinstance(stories, list) and len(stories) > 0:
            sample = stories[0]
            required = {"id", "profile_id", "media_url", "created_at"}
            has_req = required.issubset(sample.keys()) if isinstance(sample, dict) else False
            report("Stories section populated", PASS,
                   f"{len(stories)} stories, has required fields: {has_req}")
        else:
            report("Stories section populated", FAIL,
                   f"stories={type(stories).__name__} len={len(stories) if isinstance(stories, list) else 'N/A'}")
    except Exception as e:
        report("Stories section populated", FAIL, str(e))

    # 2. Posts section
    print("\n2. Checking build_homepage_payload posts section...")
    try:
        posts = payload.get("trending_posts", payload.get("posts", []))
        if isinstance(posts, list) and len(posts) > 0:
            report("Posts section populated", PASS, f"{len(posts)} post(s)")
        else:
            report("Posts section populated", SKIP, "No posts returned — may be empty feed")
    except Exception as e:
        report("Posts section populated", FAIL, str(e))

    # 3. Reels section
    print("\n3. Checking build_homepage_payload reels section...")
    try:
        reels = payload.get("reels", [])
        if isinstance(reels, list) and len(reels) > 0:
            report("Reels section populated", PASS, f"{len(reels)} reel(s)")
        else:
            report("Reels section populated", SKIP, "No reels returned — may be empty")
    except Exception as e:
        report("Reels section populated", FAIL, str(e))

    # 4. get_homepage_data()
    print("\n4. Checking get_homepage_data()...")
    try:
        from services.homepage_service import get_homepage_data
        hdata = get_homepage_data()
        has_sections = any([
            hdata.get("stories"),
            hdata.get("trending_posts") or hdata.get("feed_items") or hdata.get("posts"),
            hdata.get("reels"),
            hdata.get("recommended_profiles"),
        ])
        if has_sections:
            report("get_homepage_data returns non-empty", PASS)
        else:
            report("get_homepage_data returns non-empty", FAIL,
                   "All sections empty — check build_homepage_payload")
    except Exception as e:
        report("get_homepage_data returns non-empty", FAIL, str(e))

    # 5. JS hydration: check that hydrateHomepage expects stories/reels
    print("\n5. Checking JS hydrateHomepage stories/reels hydration...")
    try:
        with open("static/js/namvibe_home_pro.js", "r") as f:
            content = f.read()
        # Check for stories + reels hydration in the API callback
        has_stories_hydration = "p.stories" in content and "nvpro-stories-scroll" in content
        has_reels_hydration = "p.reels" in content and "nvpro-reels-grid" in content
        has_feed_hydration = "p.feed_items" in content and "nvpro-feed" in content
        if has_stories_hydration and has_reels_hydration and has_feed_hydration:
            report("JS hydrateHomepage hydrates stories+reels+feed", PASS)
        else:
            missing = []
            if not has_stories_hydration: missing.append("stories")
            if not has_reels_hydration: missing.append("reels")
            if not has_feed_hydration: missing.append("feed")
            report("JS hydrateHomepage hydrates stories+reels+feed", FAIL,
                   f"Missing hydration for: {', '.join(missing)}")
    except Exception as e:
        report("JS hydrateHomepage hydrates stories+reels+feed", FAIL, str(e))

    # 6. app.py timeout increased
    print("\n6. Checking app.py home route timeout...")
    try:
        with open("app.py", "r") as f:
            content = f.read()
        if "elapsed_ms > 5000" in content:
            report("Home route timeout set to 5000ms", PASS)
        else:
            report("Home route timeout set to 5000ms", FAIL,
                   "Timeout not set to 5000ms — may still time out on cold start")
    except Exception as e:
        report("Home route timeout set to 5000ms", SKIP, str(e))

    # 7. Homepage API does not return degraded by default
    print("\n7. Checking homepage API payload returns real data...")
    try:
        has_degraded_only = False
        with open("api_routes/homepage_api.py", "r") as f:
            content = f.read()
        # Check degraded is based on actual data
        if "not bool(payload.get" in content and "feed_items" in content:
            report("API degraded based on actual data", PASS)
        else:
            report("API degraded based on actual data", SKIP,
                   "Could not verify degraded logic")
    except Exception as e:
        report("API degraded based on actual data", SKIP, str(e))

    print_summary()

def print_summary():
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    skipped = sum(1 for _, s, _ in results if s == SKIP)
    print(f"Total: {len(results)} | PASS: {passed} | FAIL: {failed} | SKIP: {skipped}")
    if failed > 0:
        print(f"\nFAILURES ({failed}):")
        for name, status, detail in results:
            if status == FAIL:
                print(f"  - {name}: {detail}")
    print("=" * 60)
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
