"""
Phase 68B — Safe Index Migration Runner.
Connects to Neon, checks table/column existence, applies indexes safely.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from services.neon_service import get_connection, release_connection
except ImportError:
    print("FAIL: Cannot import neon_service. DATABASE_URL may be missing.")
    sys.exit(1)


def get_tables_and_columns(conn):
    """Fetch all user tables and their columns."""
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name, array_agg(column_name::text)
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name LIKE 'chain_%'
        GROUP BY table_name
    """)
    result = {}
    for row in cur.fetchall():
        result[row[0]] = set(row[1])
    cur.close()
    return result


def main():
    indexes_sql = ROOT / "sql" / "phase68b_performance_indexes.sql"
    if not indexes_sql.exists():
        print(f"FAIL: {indexes_sql} not found")
        sys.exit(1)

    with open(indexes_sql) as f:
        statements = [line.strip() for line in f if line.strip().upper().startswith("CREATE INDEX")]

    print(f"Found {len(statements)} index statements to apply")

    conn = None
    try:
        conn = get_connection(timeout_ms=15000)
        conn.set_session(autocommit=True)
        tables = get_tables_and_columns(conn)
        print(f"Found {len(tables)} chain_* tables")
    except Exception as e:
        print(f"FAIL: Could not connect to database: {e}")
        sys.exit(1)

    applied = 0
    skipped = 0
    failed = 0

    for stmt in statements:
        # Extract table name from CREATE INDEX ... ON <table>
        parts = stmt.split()
        on_idx = None
        for i, p in enumerate(parts):
            if p.upper() == "ON":
                on_idx = i + 1
                break
        if on_idx is None or on_idx >= len(parts):
            print(f"  SKIP (cannot parse table): {stmt[:80]}...")
            skipped += 1
            continue

        table_name = parts[on_idx].strip("();")
        if table_name not in tables:
            print(f"  SKIP (table '{table_name}' does not exist): {stmt[:80]}...")
            skipped += 1
            continue

        try:
            cur = conn.cursor()
            cur.execute(stmt)
            cur.close()
            print(f"  OK: {stmt[:80]}...")
            applied += 1
        except Exception as e:
            error_str = str(e)
            if "already exists" in error_str:
                print(f"  SKIP (already exists): {stmt[:80]}...")
                skipped += 1
            else:
                print(f"  FAIL ({error_str[:100]}): {stmt[:80]}...")
                failed += 1

    print(f"\nApplied: {applied}, Skipped: {skipped}, Failed: {failed}")

    if conn:
        release_connection(conn)

    if failed > 0:
        print("WARNING: Some indexes failed. Review above.")
        sys.exit(1)

    print("PASS: All indexes applied or skipped cleanly.")


if __name__ == "__main__":
    main()
