"""
Phase 69 — Realtime Communication Fix migration runner.
Applies idempotent SQL migrations for messaging, calling, and notifications.
Safe to run multiple times. Never prints secrets.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("CHAIN_ENV", "production")

PASS = 0
FAIL = 0
SQL_PATH = ROOT / "sql" / "phase69_realtime_communication_fix.sql"


def print_result(label, ok):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}")


def main():
    global PASS, FAIL

    if not SQL_PATH.exists():
        print_result(f"SQL file not found at {SQL_PATH}", False)
        sys.exit(1)

    sql = SQL_PATH.read_text()
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    print_result(f"Read {len(statements)} SQL statements from {SQL_PATH.name}", True)

    # Try to connect to Neon
    try:
        from services.neon_service import get_connection
        conn = get_connection()
        cur = conn.cursor()
        print_result("Connected to Neon database", True)
    except Exception as e:
        err = str(e)
        if "password" in err.lower() or "DATABASE_URL" in err:
            err = "Database connection failed (check credentials)"
        print_result(f"Database connection failed: {err}", False)
        sys.exit(1)

    applied = 0
    skipped = 0
    failed_statements = []

    for stmt in statements:
        if not stmt or stmt.startswith("--"):
            skipped += 1
            continue
        try:
            cur.execute(stmt)
            conn.commit()
            applied += 1
        except Exception as e:
            conn.rollback()
            err_msg = str(e).split("\n")[0][:120]
            failed_statements.append((stmt[:80], err_msg))

    cur.close()
    conn.close()

    print_result(f"Applied {applied} safe statements", True)
    print_result(f"Skipped {skipped} comments/empty", True)

    if failed_statements:
        print_result(f"{len(failed_statements)} statement(s) failed", False)
        for s, e in failed_statements:
            print(f"    Statement: {s}...")
            print(f"    Error: {e}")
    else:
        print_result("Zero statement failures", True)

    print(f"\nTotal: {PASS} passed, {FAIL} failed")
    if FAIL:
        print("SOME STATEMENTS FAILED (may already exist)")
        sys.exit(1)
    else:
        print("ALL STATEMENTS APPLIED SUCCESSFULLY")
        sys.exit(0)


if __name__ == "__main__":
    main()
