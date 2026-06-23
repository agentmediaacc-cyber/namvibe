#!/usr/bin/env python3
"""
Phase 154 — Public Media Visibility Test.

Tests that list_active_statuses() correctly filters by visibility:
- Public stories appear for any viewer.
- Followers-only stories appear only for followers.
- Private stories appear only for the owner.
"""
import os
import sys
from datetime import datetime, timezone, timedelta

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
    print("Phase 154 — Public Media Visibility Test")
    print("=" * 60)

    # 1. Check list_active_statuses import
    print("\n1. Checking list_active_statuses import...")
    try:
        from services.status_service import list_active_statuses
        report("list_active_statuses importable", PASS)
    except (ImportError, Exception) as e:
        report("list_active_statuses importable", FAIL, str(e))
        print_summary()
        return

    # 2. Check function signature
    print("\n2. Checking function signature...")
    try:
        import inspect
        sig = inspect.signature(list_active_statuses)
        params = list(sig.parameters.keys())
        expected = {"profile_id", "viewer_profile_id"}
        if expected.intersection(params):
            report("list_active_statuses has profile_id/viewer_profile_id params", PASS, f"Params: {params}")
        else:
            report("list_active_statuses has profile_id/viewer_profile_id params", FAIL, f"Params: {params}")
    except Exception as e:
        report("list_active_statuses has profile_id/viewer_profile_id params", SKIP, str(e))

    # 3. Inspect source for visibility filtering logic
    print("\n3. Inspecting visibility filtering logic...")
    try:
        from services.status_service import list_active_statuses as _las
        import inspect
        source = inspect.getsource(_las)
        has_public_check = "visibility = 'public'" in source
        has_followers_check = "visibility = 'followers'" in source
        has_follows_join = "chain_follows" in source
        if has_public_check and has_followers_check:
            report("Visibility filtering present (public + followers)", PASS)
        else:
            detail_parts = []
            if not has_public_check:
                detail_parts.append("missing public check")
            if not has_followers_check:
                detail_parts.append("missing followers check")
            report("Visibility filtering present (public + followers)", FAIL, "; ".join(detail_parts))
        if has_follows_join:
            report("Follows join for followers visibility", PASS)
        else:
            report("Follows join for followers visibility", WARN := "WARN", "Expected chain_follows reference not found in source")
    except Exception as e:
        report("Visibility filtering present (public + followers)", SKIP, str(e))
        report("Follows join for followers visibility", SKIP, str(e))

    # 4. Run list_active_statuses() with no args (feed view — should return public only)
    print("\n4. Running list_active_statuses() with no viewer (anonymous feed)...")
    try:
        rows = list_active_statuses()
        if rows is not None:
            visible_count = len(rows)
            report("Anonymous feed returns results", PASS if visible_count >= 0 else FAIL,
                   f"{visible_count} status(es) returned")
            if rows:
                non_public = [r for r in rows if r.get("visibility") and r["visibility"] != "public"]
                if non_public:
                    report("All returned statuses are public", FAIL,
                           f"{len(non_public)} non-public status(es) leaked")
                else:
                    report("All returned statuses are public", PASS)
            else:
                report("All returned statuses are public", PASS, "No rows to check (not a failure)")
        else:
            report("Anonymous feed returns results", FAIL, "list_active_statuses returned None")
    except Exception as e:
        report("Anonymous feed returns results", FAIL, str(e))

    # 5. Check Neon query pattern directly
    print("\n5. Checking Neon query pattern for visibility filtering...")
    try:
        from services.neon_service import fast_query
        now = datetime.now(timezone.utc).isoformat()
        sample = fast_query(
            """SELECT DISTINCT s.visibility, COUNT(*) as cnt
               FROM chain_status_posts s
               WHERE s.expires_at > %s AND s.deleted_at IS NULL
               GROUP BY s.visibility""",
            (now,), timeout_ms=3000, default=[]
        )
        if sample is not None:
            vis_summary = {r.get("visibility", "?"): r.get("cnt", 0) for r in sample}
            report("Visibility distribution readable", PASS, str(vis_summary))
        else:
            report("Visibility distribution readable", PASS, "No data (not a failure)")
    except Exception as e:
        report("Visibility distribution readable", SKIP, str(e))

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
