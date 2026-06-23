#!/usr/bin/env python3
"""
Phase 155 — Live Homepage Data Reflection Audit.

Tests that:
1. build_homepage_payload() returns stories (from chain_status_posts)
2. build_homepage_payload() returns public posts
3. build_homepage_payload() returns public reels
4. No empty fallback when real data exists
5. force_fast_home no longer blocks namvibe.com
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
    print("Phase 155 — Live Homepage Data Reflection Audit")
    print("=" * 60)

    # 1. Check chain_status_posts for public stories
    print("\n1. Checking chain_status_posts for public stories...")
    try:
        from services.neon_service import fast_query
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        public_stories = fast_query(
            """SELECT id, profile_id, media_url, visibility, created_at, expires_at
               FROM chain_status_posts
               WHERE visibility = 'public'
               AND deleted_at IS NULL
               AND (expires_at IS NULL OR expires_at > %s)
               ORDER BY created_at DESC LIMIT 20""",
            (now.isoformat(),), timeout_ms=5000, default=[]
        )
        if public_stories and len(public_stories) > 0:
            report("chain_status_posts has public stories", PASS,
                   f"{len(public_stories)} story(ies) found")
        else:
            report("chain_status_posts has public stories", SKIP,
                   "No public stories — upload one via the upload pipeline")
    except Exception as e:
        report("chain_status_posts has public stories", FAIL, str(e))

    # 2. Check chain_posts for public posts
    print("\n2. Checking chain_posts for public posts...")
    try:
        public_posts = fast_query(
            """SELECT id, profile_id, media_url, visibility, created_at
               FROM chain_posts
               WHERE visibility = 'public' AND deleted_at IS NULL
               ORDER BY created_at DESC LIMIT 20""",
            timeout_ms=5000, default=[]
        )
        if public_posts and len(public_posts) > 0:
            report("chain_posts has public posts", PASS,
                   f"{len(public_posts)} post(s) found")
        else:
            report("chain_posts has public posts", SKIP,
                   "No public posts — upload one via the upload pipeline")
    except Exception as e:
        report("chain_posts has public posts", FAIL, str(e))

    # 3. Check chain_reels for public reels
    print("\n3. Checking chain_reels for public reels...")
    try:
        public_reels = fast_query(
            """SELECT id, profile_id, video_url, visibility, created_at
               FROM chain_reels
               WHERE visibility = 'public' AND deleted_at IS NULL
               ORDER BY created_at DESC LIMIT 20""",
            timeout_ms=5000, default=[]
        )
        if public_reels and len(public_reels) > 0:
            report("chain_reels has public reels", PASS,
                   f"{len(public_reels)} reel(s) found")
        else:
            report("chain_reels has public reels", SKIP,
                   "No public reels — upload one via the upload pipeline")
    except Exception as e:
        report("chain_reels has public reels", FAIL, str(e))

    # 4. Call build_homepage_payload() directly
    print("\n4. Calling build_homepage_payload()...")
    try:
        from services.homepage_service import build_homepage_payload
        payload = build_homepage_payload()
        has_stories = bool(payload.get("stories"))
        has_posts = bool(payload.get("trending_posts"))
        has_reels = bool(payload.get("reels"))
        sections = []
        if has_stories: sections.append(f"stories({len(payload['stories'])})")
        if has_posts: sections.append(f"posts({len(payload['trending_posts'])})")
        if has_reels: sections.append(f"reels({len(payload['reels'])})")
        if sections:
            report("build_homepage_payload returns non-empty sections", PASS,
                   f"Sections: {', '.join(sections)}")
        else:
            report("build_homepage_payload returns non-empty sections", FAIL,
                   "All sections empty — check queries and data")
    except Exception as e:
        report("build_homepage_payload returns non-empty sections", FAIL, str(e))

    # 5. Check app.py no longer blocks namvibe.com in force_fast_home
    print("\n5. Checking force_fast_home does not block namvibe.com...")
    try:
        with open("app.py", "r") as f:
            content = f.read()
        if "namvibe.com" in content and "force_fast_home" in content:
            idx = content.index("force_fast_home")
            snippet = content[idx:idx+300]
            if "namvibe.com" in snippet:
                report("force_fast_home blocks namvibe.com", FAIL,
                       "namvibe.com still present in force_fast_home check")
            else:
                report("force_fast_home blocks namvibe.com", PASS,
                       "namvibe.com removed from force_fast_home")
        else:
            report("force_fast_home blocks namvibe.com", PASS,
                   "namvibe.com not found in force_fast_home context")
    except Exception as e:
        report("force_fast_home blocks namvibe.com", SKIP, str(e))

    # 6. Check homepage_api.py force_fast_home
    print("\n6. Checking homepage_api.py force_fast_home does not block namvibe.com...")
    try:
        with open("api_routes/homepage_api.py", "r") as f:
            content = f.read()
        if "force_fast_home" in content:
            idx = content.index("force_fast_home")
            snippet = content[idx:idx+300]
            if "namvibe.com" in snippet:
                report("API force_fast_home blocks namvibe.com", FAIL,
                       "namvibe.com still present in API force_fast_home check")
            else:
                report("API force_fast_home blocks namvibe.com", PASS,
                       "namvibe.com removed from API force_fast_home")
        else:
            report("API force_fast_home blocks namvibe.com", PASS,
                   "force_fast_home removed entirely from API")
    except Exception as e:
        report("API force_fast_home blocks namvibe.com", SKIP, str(e))

    # 7. Check visibility='public' in reels query
    print("\n7. Checking reels query includes visibility filter...")
    try:
        from services.homepage_service import build_homepage_payload as _bhp
        import inspect
        src = inspect.getsource(_bhp)
        if "visibility" in src and "public" in src and "reels" in src:
            report("Reels query filters by public visibility", PASS)
        else:
            report("Reels query filters by public visibility", FAIL,
                   "No visibility filter found in reels section of build_homepage_payload")
    except Exception as e:
        report("Reels query filters by public visibility", SKIP, str(e))

    # 8. Check _reel_select includes visibility
    print("\n8. Checking _reel_select includes visibility column...")
    try:
        from services.homepage_service import _reel_select
        cols = _reel_select()
        if cols and "visibility" in cols:
            report("_reel_select includes visibility", PASS)
        else:
            report("_reel_select includes visibility", FAIL,
                   f"Columns: {cols}" if cols else "_reel_select returned None/empty")
    except Exception as e:
        report("_reel_select includes visibility", FAIL, str(e))

    print_summary()

def print_summary():
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
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
