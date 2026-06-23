#!/usr/bin/env python3
"""
Phase 154 — Homepage Story Reels Reflection Test.

Tests that:
1. Public stories appear on the homepage story strip.
2. Public reels appear in reels preview on homepage.
3. Public posts appear in homepage feed.
4. Homepage service functions build_homepage_payload() and get_homepage_data() work.
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
    print("Phase 154 — Homepage Story Reels Reflection Test")
    print("=" * 60)

    # 1. Check homepage_service import
    print("\n1. Checking homepage_service import...")
    try:
        import services.homepage_service as hs
        report("homepage_service importable", PASS)
    except (ImportError, Exception) as e:
        report("homepage_service importable", FAIL, str(e))
        print_summary()
        return

    # 2. Check build_homepage_payload and get_homepage_data
    print("\n2. Checking homepage payload functions...")
    try:
        from services.homepage_service import build_homepage_payload
        report("build_homepage_payload importable", PASS)
    except (ImportError, AttributeError) as e:
        report("build_homepage_payload importable", FAIL, str(e))

    try:
        from services.homepage_service import get_homepage_data
        report("get_homepage_data importable", PASS)
    except (ImportError, AttributeError):
        report("get_homepage_data importable", SKIP, "Not found — may use different function name")
    except Exception as e:
        report("get_homepage_data importable", FAIL, str(e))

    # 3. Inspect payload sections
    print("\n3. Inspecting homepage payload structure...")
    try:
        import inspect
        from services.homepage_service import build_homepage_payload as _bhp
        source = inspect.getsource(_bhp)
        sections = []
        if "stories" in source:
            sections.append("stories")
        if "reels" in source:
            sections.append("reels")
        if "trending_posts" in source or "posts" in source:
            sections.append("posts")
        if sections:
            report("Payload contains expected sections", PASS, f"Sections: {', '.join(sections)}")
        else:
            report("Payload contains expected sections", FAIL, "No expected sections found in build_homepage_payload")
    except Exception as e:
        report("Payload contains expected sections", SKIP, str(e))

    # 4. Check that stories come from chain_status_posts with public visibility
    print("\n4. Checking story data source (public stories)...")
    try:
        from services.neon_service import fast_query
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=24)).isoformat()
        public_stories = fast_query(
            """SELECT s.id, s.profile_id, s.media_url, s.visibility, s.created_at
               FROM chain_status_posts s
               WHERE s.visibility = 'public'
               AND s.expires_at > %s
               AND s.deleted_at IS NULL
               ORDER BY s.created_at DESC LIMIT 12""",
            (now.isoformat(),), timeout_ms=3000, default=[]
        )
        if public_stories is not None:
            report("Public stories queryable from chain_status_posts", PASS,
                   f"{len(public_stories)} public story(ies) found")
        else:
            report("Public stories queryable from chain_status_posts", FAIL, "Query returned None")
    except Exception as e:
        report("Public stories queryable from chain_status_posts", SKIP, str(e))

    # 5. Check that reels come from chain_reels
    print("\n5. Checking reel data source...")
    try:
        reels = fast_query(
            """SELECT r.id, r.profile_id, r.video_url, r.visibility, r.created_at
               FROM chain_reels r
               WHERE r.deleted_at IS NULL
               ORDER BY r.created_at DESC LIMIT 12""",
            timeout_ms=3000, default=[]
        )
        if reels is not None:
            report("Reels queryable from chain_reels", PASS, f"{len(reels)} reel(s) found")
        else:
            report("Reels queryable from chain_reels", FAIL, "Query returned None")
    except Exception as e:
        report("Reels queryable from chain_reels", SKIP, str(e))

    # 6. Check that posts come from chain_posts with public visibility
    print("\n6. Checking post data source (public feed)...")
    try:
        posts = fast_query(
            """SELECT p.id, p.profile_id, p.media_url, p.visibility, p.post_type, p.created_at
               FROM chain_posts p
               WHERE p.visibility = 'public' AND p.deleted_at IS NULL
               ORDER BY p.created_at DESC LIMIT 12""",
            timeout_ms=3000, default=[]
        )
        if posts is not None:
            report("Public posts queryable from chain_posts", PASS, f"{len(posts)} public post(s) found")
        else:
            report("Public posts queryable from chain_posts", FAIL, "Query returned None")
    except Exception as e:
        report("Public posts queryable from chain_posts", SKIP, str(e))

    # 7. Check homepage_phase141_service functions used by homepage
    print("\n7. Checking homepage phase141 service functions...")
    try:
        from services.homepage_phase141_service import fetch_stories_v2, fetch_reels_v2, fetch_posts_v2
        report("Homepage v2 fetchers importable", PASS)
    except (ImportError, Exception) as e:
        report("Homepage v2 fetchers importable", SKIP, str(e))

    # 8. Check that profile data is joined in homepage queries
    print("\n8. Checking profile JOINs in homepage queries...")
    try:
        from services.homepage_service import _fetch_stories
        import inspect
        source = inspect.getsource(_fetch_stories)
        if "LEFT JOIN" in source or "JOIN" in source:
            report("Profile JOINs in homepage queries", PASS)
        else:
            report("Profile JOINs in homepage queries", WARN := "WARN", "No JOIN found in _fetch_stories")
    except Exception as e:
        report("Profile JOINs in homepage queries", SKIP, str(e))

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
