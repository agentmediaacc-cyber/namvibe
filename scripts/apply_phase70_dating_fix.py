"""
Phase 70 — Dating Fix Migration Runner.
Applies sql/phase70_dating_fix.sql to create all dating tables
and add backwards-compatible columns.
"""
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["CHAIN_ENV"] = "production"


def main():
    sql_path = ROOT / "sql" / "phase70_dating_fix.sql"
    if not sql_path.exists():
        print(f"[FAIL] SQL file not found: {sql_path}")
        sys.exit(1)

    sql = sql_path.read_text()

    # Split into individual statements
    statements = [s.strip() for s in sql.split(";") if s.strip()]

    from services.neon_service import write_query, fast_query

    passed = 0
    failed = 0
    skipped = 0

    print("=" * 60)
    print("Phase 70 — Dating Fix Migration")
    print("=" * 60)
    print(f"Applying {len(statements)} statements...\n")

    for i, stmt in enumerate(statements, 1):
        label = stmt.split("\n")[0][:80].strip()
        label = label.replace("--", "").strip()
        try:
            write_query(stmt + ";")
            passed += 1
            print(f"  [{i:2d}/{len(statements)}] [PASS] {label}")
        except Exception as e:
            err = str(e)[:80]
            # IF NOT EXISTS / ADD COLUMN IF NOT EXISTS may still raise if
            # the entire transaction fails for unrelated reasons
            if "already exists" in err or "duplicate" in err.lower():
                skipped += 1
                print(f"  [{i:2d}/{len(statements)}] [SKIP] {label} — {err}")
            else:
                failed += 1
                print(f"  [{i:2d}/{len(statements)}] [FAIL] {label} — {err}")

    # Verify tables were created
    print("\n--- Verification ---")
    dating_tables = [
        "chain_dating_profiles", "chain_dating_likes", "chain_dating_matches",
        "chain_dating_reports", "chain_dating_blocks", "chain_dating_preferences",
    ]
    for tbl in dating_tables:
        rows = fast_query(
            "SELECT table_name FROM information_schema.tables WHERE table_name = %s",
            (tbl,), default=[]
        )
        if rows:
            print(f"  [PASS] Table '{tbl}' exists")
        else:
            print(f"  [FAIL] Table '{tbl}' missing")

    # Verify key columns exist
    col_checks = [
        ("chain_dating_profiles", "dating_mode_on"),
        ("chain_dating_profiles", "is_enabled"),
        ("chain_dating_profiles", "looking_for"),
        ("chain_dating_profiles", "height"),
        ("chain_dating_profiles", "relationship_goal"),
        ("chain_dating_profiles", "interests"),
        ("chain_dating_likes", "actor_profile_id"),
        ("chain_dating_matches", "profile_id_a"),
        ("chain_dating_reports", "reporter_profile_id"),
        ("chain_dating_blocks", "blocker_profile_id"),
        ("chain_dating_preferences", "profile_id"),
    ]
    for tbl, col in col_checks:
        rows = fast_query(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
            (tbl, col), default=[]
        )
        if rows:
            print(f"  [PASS] {tbl}.{col} exists")
        else:
            print(f"  [FAIL] {tbl}.{col} missing")

    print(f"\n{'=' * 60}")
    print(f"Migration: {passed} passed, {failed} failed, {skipped} skipped")
    if failed:
        print("❌ SOME STATEMENTS FAILED")
        sys.exit(1)
    else:
        print("✅ ALL STATEMENTS APPLIED")
        sys.exit(0)


if __name__ == "__main__":
    main()
