#!/usr/bin/env python3
"""Profile each homepage SQL query with EXPLAIN ANALYZE and index analysis."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["FLASK_APP"] = "app"
os.environ["FLASK_ENV"] = "development"

SKIP_COLD_WARM_COMPARE = "--quick" in sys.argv

HOMEPAGE_QUERIES = {
    "stories": {
        "sql": (
            "SELECT id, profile_id, caption, thumbnail_url, created_at, deleted_at "
            "FROM chain_stories "
            "WHERE deleted_at IS NULL "
            "ORDER BY created_at DESC LIMIT 12"
        ),
        "table": "chain_stories",
    },
    "live_rooms": {
        "sql": (
            "SELECT id, profile_id, title, category, status, is_live, viewer_count, "
            "cover_url, thumbnail_url, entry_fee, created_at, deleted_at "
            "FROM chain_live_rooms "
            "WHERE (is_live = TRUE OR status = 'live') AND deleted_at IS NULL "
            "ORDER BY created_at DESC LIMIT 8"
        ),
        "table": "chain_live_rooms",
    },
    "profiles_creator": {
        "sql": (
            "SELECT id, username, display_name, full_name, avatar_url, photo_url, "
            "thumbnail_url, town, location, bio, created_at, is_verified, verified, "
            "is_online, is_creator, creator_category, dating_mode_enabled, "
            "followers_count, deleted_at "
            "FROM chain_profiles "
            "WHERE is_creator = TRUE AND deleted_at IS NULL "
            "ORDER BY followers_count DESC NULLS LAST LIMIT 10"
        ),
        "table": "chain_profiles",
    },
    "posts": {
        "sql": (
            "SELECT id, profile_id, caption, content, body, video_url, thumbnail_url, "
            "link_url, town_tag, visibility, post_type, likes_count, comments_count, "
            "created_at, category, deleted_at "
            "FROM chain_posts "
            "WHERE deleted_at IS NULL "
            "ORDER BY created_at DESC NULLS LAST LIMIT 8"
        ),
        "table": "chain_posts",
    },
    "reels": {
        "sql": (
            "SELECT id, profile_id, caption, video_url, thumbnail_url, "
            "created_at, deleted_at "
            "FROM chain_reels "
            "WHERE deleted_at IS NULL "
            "ORDER BY created_at DESC LIMIT 8"
        ),
        "table": "chain_reels",
    },
    "dating_matches": {
        "sql": (
            "SELECT id, username, display_name, full_name, avatar_url, photo_url, "
            "thumbnail_url, town, location, bio, created_at, is_verified, verified, "
            "is_online, is_creator, creator_category, dating_mode_enabled, "
            "followers_count, deleted_at "
            "FROM chain_profiles "
            "WHERE dating_mode_enabled = TRUE AND deleted_at IS NULL "
            "ORDER BY created_at DESC LIMIT 8"
        ),
        "table": "chain_profiles",
    },
    "suggested_people": {
        "sql": (
            "SELECT id, username, display_name, full_name, avatar_url, photo_url, "
            "thumbnail_url, town, location, bio, created_at, is_verified, verified, "
            "is_online, is_creator, creator_category, dating_mode_enabled, "
            "followers_count, deleted_at, "
            "((CASE WHEN avatar_url IS NOT NULL AND avatar_url <> '' THEN 2 ELSE 0 END) "
            "+ (CASE WHEN bio IS NOT NULL AND bio <> '' THEN 1.5 ELSE 0 END) "
            "+ (CASE WHEN location IS NOT NULL AND location <> '' THEN 1 ELSE 0 END) "
            "+ (CASE WHEN town IS NOT NULL AND town <> '' THEN 1 ELSE 0 END) "
            "+ (CASE WHEN is_verified IS TRUE THEN 2 ELSE 0 END) "
            "+ (CASE WHEN verified IS TRUE THEN 1 ELSE 0 END)) AS _score "
            "FROM chain_profiles "
            "WHERE deleted_at IS NULL AND id != '00000000-0000-0000-0000-000000000000' "
            "ORDER BY _score DESC, created_at DESC NULLS LAST LIMIT 10"
        ),
        "table": "chain_profiles",
    },
}


def _get_db_cursor(app):
    """Get a raw DB cursor via the app's neon connection."""
    from services.neon_service import get_connection, release_connection

    conn = None
    for attempt in range(3):
        try:
            conn = get_connection(timeout_ms=30000)
            cur = conn.cursor()
            return conn, cur
        except Exception as e:
            if conn:
                try:
                    release_connection(conn)
                except Exception:
                    pass
            if attempt == 2:
                raise
            time.sleep(0.5)
    return None, None


def run_explain_analyze(cur, sql_text, label):
    """Run EXPLAIN (ANALYZE, BUFFERS) for a query and return parsed plan."""
    explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql_text}"
    try:
        cur.execute(explain_sql)
        rows = cur.fetchall()
        if not rows:
            return {"label": label, "error": "no rows returned from EXPLAIN", "planning_time_ms": 0, "execution_time_ms": 0, "total_time_ms": 0}
        raw = rows[0].get("QUERY PLAN", rows[0].get("query_plan", ""))
        if not raw:
            return {"label": label, "error": "no query plan column in result", "planning_time_ms": 0, "execution_time_ms": 0, "total_time_ms": 0}
        plan_list = raw if isinstance(raw, list) else json.loads(raw)
        plan = plan_list[0] if isinstance(plan_list, list) and len(plan_list) > 0 else plan_list

        if not isinstance(plan, dict):
            return {"label": label, "error": f"unexpected plan type: {type(plan).__name__}", "planning_time_ms": 0, "execution_time_ms": 0, "total_time_ms": 0}

        ep = plan.get("Execution Time", 0)
        pp = plan.get("Planning Time", 0)
        plan_node = plan.get("Plan", plan)

        analysis = _analyze_plan_node(plan_node)
        analysis["label"] = label
        analysis["planning_time_ms"] = round(float(pp), 2) if pp else 0
        analysis["execution_time_ms"] = round(float(ep), 2) if ep else 0
        analysis["total_time_ms"] = round(analysis["planning_time_ms"] + analysis["execution_time_ms"], 2)
        analysis["rows_returned"] = analysis.get("actual_rows", 0) or analysis.get("plan_rows", 0)
        analysis["raw_plan"] = plan
        return analysis
    except Exception as e:
        return {"label": label, "error": str(e), "planning_time_ms": 0, "execution_time_ms": 0, "total_time_ms": 0}


def _analyze_plan_node(node):
    """Recursively analyze a plan node for issues."""
    issues = []
    node_type = node.get("Node Type", "Unknown")
    strategy = node.get("Strategy", "")
    join_type = node.get("Join Type", "")
    relation = node.get("Relation Name", node.get("Relation", ""))
    alias = node.get("Alias", "")

    actual_rows = node.get("Actual Rows", 0)
    actual_startup = node.get("Actual Startup Time", 0)
    actual_total = node.get("Actual Total Time", 0)
    plan_rows = node.get("Plan Rows", 0)
    plan_width = node.get("Plan Width", 0)

    sort_key = node.get("Sort Key", [])
    index_name = node.get("Index Name", "")
    index_cond = node.get("Index Condition", "")
    filter_cond = node.get("Filter", "")
    recheck_cond = node.get("Recheck Condition", "")

    if node_type == "Seq Scan":
        issues.append({
            "type": "seq_scan",
            "table": relation or alias,
            "detail": f"Sequential scan on {relation or alias} (rows={actual_rows}, cost={round(actual_total, 2)}ms)",
            "severity": "high",
        })
    if node_type == "Bitmap Heap Scan":
        issues.append({
            "type": "bitmap_scan",
            "table": relation or alias,
            "detail": f"Bitmap heap scan on {relation or alias} (rows={actual_rows})",
            "severity": "medium",
        })
    if node_type == "Sort":
        issues.append({
            "type": "sort",
            "detail": f"Sort operation: {sort_key} (rows={actual_rows})",
            "severity": "low",
        })
    if node_type and "Join" in node_type and "Nested Loop" in node_type and actual_rows > 100:
        issues.append({
            "type": "nested_loop",
            "detail": f"{join_type} Nested Loop join on {relation or alias} (rows={actual_rows})",
            "severity": "medium",
        })
    if not index_name and node_type in ("Index Scan", "Index Only Scan", "Bitmap Index Scan"):
        pass
    elif node_type == "Index Scan" and index_name:
        issues.append({
            "type": "index_used",
            "detail": f"Index scan using {index_name} on {relation or alias}",
            "severity": "info",
        })

    result = {
        "node_type": node_type,
        "relation": relation or alias,
        "actual_rows": actual_rows,
        "actual_total_ms": round(float(actual_total), 2) if actual_total else 0,
        "plan_rows": plan_rows,
        "plan_width": plan_width,
        "sort_keys": sort_key,
        "index_name": index_name,
        "filter": filter_cond[:120] if filter_cond else "",
        "issues": issues,
    }

    for child_key in ("Plans", "Subplans"):
        for child in node.get(child_key, []):
            child_result = _analyze_plan_node(child)
            result.setdefault("children", []).append(child_result)
            result.setdefault("issues", []).extend(child_result.get("issues", []))
            result.setdefault("sub_issues", []).extend(child_result.get("sub_issues", []))

    return result


def check_indexes(cur, tables):
    """Check which indexes actually exist on each table."""
    index_info = {}
    for table in tables:
        try:
            cur.execute(
                "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = %s ORDER BY indexname",
                (table,),
            )
            rows = cur.fetchall()
            indexes = []
            for r in rows:
                if isinstance(r, dict):
                    indexes.append({"name": r.get("indexname", ""), "definition": r.get("indexdef", "")})
                else:
                    indexes.append({"name": r[0], "definition": r[1]})
            index_info[table] = indexes
        except Exception as e:
            index_info[table] = {"error": str(e)}
    return index_info


def generate_recommendations(label, analysis, existing_indexes):
    """Generate index recommendations based on EXPLAIN ANALYZE results."""
    issues = analysis.get("issues", [])
    children_issues = []
    for child in analysis.get("children", []):
        children_issues.extend(child.get("issues", []))
    all_issues = issues + children_issues

    exec_ms = analysis.get("execution_time_ms", 0)
    has_seq_scan = any(i["type"] == "seq_scan" for i in all_issues)
    has_sort = any(i["type"] == "sort" for i in all_issues)

    recs = []

    if label == "stories":
        if has_seq_scan:
            recs.append(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stories_deleted_created "
                "ON chain_stories(deleted_at, created_at DESC) "
                "WHERE deleted_at IS NULL;"
            )
    elif label == "live_rooms":
        if has_seq_scan:
            recs.append(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_live_rooms_live_deleted_created "
                "ON chain_live_rooms(is_live, status, deleted_at, created_at DESC) "
                "WHERE deleted_at IS NULL AND (is_live = TRUE OR status = 'live');"
            )
    elif label in ("profiles_creator",):
        if has_seq_scan:
            recs.append(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_creator_deleted_followers "
                "ON chain_profiles(is_creator, deleted_at, followers_count DESC) "
                "WHERE is_creator = TRUE AND deleted_at IS NULL;"
            )
    elif label == "posts":
        if has_seq_scan:
            recs.append(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_posts_deleted_created "
                "ON chain_posts(deleted_at, created_at DESC) "
                "WHERE deleted_at IS NULL;"
            )
    elif label == "reels":
        if has_seq_scan:
            recs.append(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reels_deleted_created "
                "ON chain_reels(deleted_at, created_at DESC) "
                "WHERE deleted_at IS NULL;"
            )
    elif label == "dating_matches":
        if has_seq_scan:
            recs.append(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_dating_deleted_created "
                "ON chain_profiles(dating_mode_enabled, deleted_at, created_at DESC) "
                "WHERE dating_mode_enabled = TRUE AND deleted_at IS NULL;"
            )
    elif label == "suggested_people":
        if has_seq_scan:
            recs.append(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_suggested_score "
                "ON chain_profiles(deleted_at, created_at DESC);"
            )

    for child in analysis.get("children", []):
        if child.get("node_type") == "Seq Scan" and child.get("relation"):
            table = child["relation"]
            if table.endswith("_pkey"):
                continue
            if table not in [r["table"] for r in issues if r.get("type") == "seq_scan"]:
                recs.append(f"-- Consider index on {table} for filter conditions used in this query")

    return recs


def format_plan_summary(analysis):
    """Format plan analysis into readable summary."""
    lines = []
    lines.append(f"  Node Type: {analysis.get('node_type', '?')}")
    lines.append(f"  Relation: {analysis.get('relation', '?')}")
    lines.append(f"  Actual Rows: {analysis.get('actual_rows', '?')}")
    lines.append(f"  Actual Total: {analysis.get('actual_total_ms', '?')}ms")
    lines.append(f"  Plan Rows: {analysis.get('plan_rows', '?')}")
    if analysis.get("sort_keys"):
        lines.append(f"  Sort Keys: {analysis.get('sort_keys')}")
    if analysis.get("index_name"):
        lines.append(f"  Index Used: {analysis.get('index_name')}")
    if analysis.get("filter"):
        lines.append(f"  Filter: {analysis.get('filter')}")
    issues = analysis.get("issues", [])
    for child in analysis.get("children", []):
        issues.extend(child.get("issues", []))
    if issues:
        lines.append("  Issues:")
        for iss in issues:
            sev = iss.get("severity", "info")
            lines.append(f"    [{sev}] {iss.get('detail', iss.get('type', ''))}")
    return "\n".join(lines)


def run_query_timing(cur, sql_text, label):
    """Run the actual query (not EXPLAIN) and time it."""
    try:
        started = time.perf_counter()
        cur.execute(sql_text)
        rows = cur.fetchall()
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "label": label,
            "duration_ms": round(elapsed_ms, 2),
            "rows_returned": len(rows),
        }
    except Exception as e:
        return {"label": label, "error": str(e), "duration_ms": 0, "rows_returned": 0}


def main():
    from app import app

    print("=" * 72)
    print("Phase 64 — Neon Query Profiler")
    print("=" * 72)

    with app.app_context():
        conn, cur = _get_db_cursor(app)
        if not cur:
            print("FAIL: Could not get database cursor")
            return 1

        tables = list(dict.fromkeys(q["table"] for q in HOMEPAGE_QUERIES.values()))
        index_info = check_indexes(cur, tables)

        print("\n--- Existing Indexes ---")
        for table, idxs in sorted(index_info.items()):
            if isinstance(idxs, dict) and "error" in idxs:
                print(f"  {table}: ERROR - {idxs['error']}")
                continue
            print(f"\n  {table}:")
            if not idxs:
                print("    (no indexes)")
            for idx in idxs:
                print(f"    {idx['name']}: {idx['definition'][:120]}...")

        results = {}

        if not SKIP_COLD_WARM_COMPARE:
            print("\n\n--- COLD CONNECTION: WARMING UP ---")
            warmup_sql = "SELECT 1"
            cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {warmup_sql}")
            cur.fetchall()
            print("  Warmup done.")

        print("\n\n--- QUERY ANALYSIS ---")
        for label, info in sorted(HOMEPAGE_QUERIES.items()):
            sql_text = info["sql"]
            table = info["table"]

            print(f"\n{'─' * 72}")
            print(f"QUERY: {label}")
            print(f"{'─' * 72}")
            print(f"  Table: {table}")

            timing = run_query_timing(cur, sql_text, label)
            print(f"  Actual Duration: {timing.get('duration_ms', '?')}ms")
            print(f"  Actual Rows: {timing.get('rows_returned', '?')}")

            plan = run_explain_analyze(cur, sql_text, label)
            results[label] = {"timing": timing, "plan": plan}

            if "error" in plan:
                print(f"  EXPLAIN ANALYZE ERROR: {plan['error']}")
                continue

            print(f"  Planning Time: {plan.get('planning_time_ms', '?')}ms")
            print(f"  Execution Time: {plan.get('execution_time_ms', '?')}ms")
            print(f"  Total Time: {plan.get('total_time_ms', '?')}ms")
            print(f"\n  Plan Summary:")
            print(format_plan_summary(plan))

            recs = generate_recommendations(label, plan, index_info.get(table, []))
            if recs:
                print(f"\n  Recommended Indexes:")
                for r in recs:
                    print(f"    {r}")

            if not SKIP_COLD_WARM_COMPARE:
                print(f"\n  --- Warm Repeat ---")
                time.sleep(0.1)
                warm_timing = run_query_timing(cur, sql_text, label)
                warm_plan = run_explain_analyze(cur, sql_text, label)
                print(f"  Duration (warm): {warm_timing.get('duration_ms', '?')}ms")
                print(f"  Execution Time (warm): {warm_plan.get('execution_time_ms', '?')}ms")
                results[label]["warm"] = {"timing": warm_timing, "plan": warm_plan}

        print("\n" + "=" * 72)
        print("SUMMARY")
        print("=" * 72)
        fast = min(
            (r["timing"] for r in results.values() if "error" not in r.get("plan", {})),
            key=lambda x: x.get("duration_ms", float("inf")),
            default=None,
        )
        slow = max(
            (r["timing"] for r in results.values() if "error" not in r.get("plan", {})),
            key=lambda x: x.get("duration_ms", 0),
            default=None,
        )
        if fast:
            print(f"  Fastest query: {fast['label']} at {fast['duration_ms']}ms")
        if slow:
            print(f"  Slowest query: {slow['label']} at {slow['duration_ms']}ms")

        expensive = max(
            (
                (label, r)
                for label, r in results.items()
                if "error" not in r.get("plan", {})
            ),
            key=lambda x: x[1]["plan"].get("execution_time_ms", 0),
            default=None,
        )
        if expensive:
            elabel, edata = expensive
            print(f"  Most expensive plan: {elabel} at {edata['plan'].get('execution_time_ms', 0)}ms")

        all_seq_scans = []
        for label, r in results.items():
            plan = r.get("plan", {})
            issues = plan.get("issues", [])
            for child in plan.get("children", []):
                issues.extend(child.get("issues", []))
            for iss in issues:
                if iss["type"] == "seq_scan":
                    all_seq_scans.append((label, iss["table"], iss["detail"]))
        if all_seq_scans:
            print(f"\n  Sequential Scans Detected:")
            for label, tbl, detail in all_seq_scans:
                print(f"    {label} on {tbl}: {detail}")

        print(f"\n  All queries analyzed: {len(results)}")
        print(f"  Tables checked for indexes: {len(tables)}")

        try:
            from services.neon_service import release_connection as _rel
            _rel(conn)
        except Exception:
            pass

        output = {
            "queries": results,
            "indexes": {t: [i["name"] for i in idxs if isinstance(idxs, list)] for t, idxs in index_info.items()},
            "fastest": {"label": fast["label"], "ms": fast["duration_ms"]} if fast else None,
            "slowest": {"label": slow["label"], "ms": slow["duration_ms"]} if slow else None,
        }
        output_path = ROOT / "reports" / "phase64_query_analysis.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, indent=2, default=str))
        print(f"\n  Report saved: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
