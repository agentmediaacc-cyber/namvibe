"""
Phase 71 — Premium Speed + UI Polish: Index Migration Runner.
Applies sql/phase71_performance_indexes.sql to add missing indexes.
"""
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["CHAIN_ENV"] = "production"
os.environ["CHAIN_DISABLE_CALL_WORKER"] = "1"
os.environ["CHAIN_DISABLE_SCHEDULER"] = "1"
os.environ["CHAIN_DEV_TOOLS"] = "1"


def main():
    sql_path = ROOT / "sql" / "phase71_performance_indexes.sql"
    if not sql_path.exists():
        print(f"[FAIL] SQL file not found: {sql_path}")
        sys.exit(1)

    sql = sql_path.read_text()
    statements = [s.strip() for s in sql.split(";") if s.strip()]

    from services.neon_service import write_query, fast_query

    passed = 0
    failed = 0
    skipped = 0

    print("=" * 60)
    print("Phase 71 — Performance Indexes Migration")
    print("=" * 60)
    print(f"Applying {len(statements)} indexes...\n")

    for i, stmt in enumerate(statements, 1):
        label = stmt.split("\n")[0][:80].strip().replace("--", "").strip()
        try:
            write_query(stmt + ";")
            passed += 1
            print(f"  [{i:2d}/{len(statements)}] [PASS] {label}")
        except Exception as e:
            err = str(e)[:80]
            if "already exists" in err:
                skipped += 1
                print(f"  [{i:2d}/{len(statements)}] [SKIP] {label}")
            else:
                failed += 1
                print(f"  [{i:2d}/{len(statements)}] [FAIL] {label} — {err}")

    print(f"\n{'=' * 60}")
    print(f"Migration: {passed} passed, {failed} failed, {skipped} skipped")
    if failed:
        print("❌ SOME STATEMENTS FAILED")
        sys.exit(1)
    else:
        print("✅ ALL INDEXES APPLIED")
        sys.exit(0)


if __name__ == "__main__":
    main()
