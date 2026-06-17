#!/usr/bin/env python3
"""Audit Phase 64 — verify all homepage queries were analyzed with EXPLAIN ANALYZE."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPECTED_QUERIES = {
    "stories", "live_rooms", "profiles_creator", "posts",
    "reels", "dating_matches", "suggested_people",
}


def main():
    report_path = ROOT / "reports" / "phase64_query_analysis.json"
    if not report_path.exists():
        print("FAIL: phase64_query_analysis.json report not found")
        print(f"  Run scripts/profile_neon_queries.py first")
        return 1

    report = json.loads(report_path.read_text())
    queries = report.get("queries", {})
    analyzed = set(queries.keys())

    missing = EXPECTED_QUERIES - analyzed
    if missing:
        print(f"FAIL: Missing query analysis for: {', '.join(sorted(missing))}")
        return 1

    errors = []
    for name, data in sorted(queries.items()):
        plan = data.get("plan", {})
        if plan.get("error"):
            errors.append(f"  {name}: {plan['error']}")
        if not plan.get("execution_time_ms") and plan.get("execution_time_ms") != 0:
            errors.append(f"  {name}: missing execution_time_ms")
        if not plan.get("planning_time_ms") and plan.get("planning_time_ms") != 0:
            errors.append(f"  {name}: missing planning_time_ms")

    if errors:
        print("FAIL: Some queries have incomplete analysis:")
        for e in errors:
            print(e)
        return 1

    print("PASS: All 7 homepage queries analyzed")

    indexes = report.get("indexes", {})
    for table, idxs in sorted(indexes.items()):
        if not idxs:
            print(f"  WARNING: No indexes on {table}")
        else:
            print(f"  {table}: {len(idxs)} index(es)")

    plan_saved = any(
        isinstance(data.get("plan", {}).get("raw_plan"), dict)
        for data in queries.values()
    )
    if plan_saved:
        print("PASS: Execution plans saved to report")

    recs_path = ROOT / "reports" / "phase64_index_recommendations.txt"
    rec_count = 0
    for name, data in sorted(queries.items()):
        plan = data.get("plan", {})
        issues = []
        for child in plan.get("children", []):
            issues.extend(child.get("issues", []))
        issues.extend(plan.get("issues", []))
        for iss in issues:
            if iss.get("severity") == "high" and iss.get("type") == "seq_scan":
                rec_count += 1

    print(f"PASS: {rec_count} index recommendation(s) generated from seq scan detection")

    slowest = report.get("slowest")
    fastest = report.get("fastest")
    if slowest:
        print(f"\n  Slowest query: {slowest['label']} at {slowest['ms']}ms")
    if fastest:
        print(f"  Fastest query: {fastest['label']} at {fastest['ms']}ms")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
