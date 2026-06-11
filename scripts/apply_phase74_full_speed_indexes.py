#!/usr/bin/env python3
"""Apply Phase 74 full-speed indexes to the database."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SQL_PATH = os.path.join(os.path.dirname(__file__), "..", "sql", "phase74_full_speed_indexes.sql")

def main():
    try:
        from services.neon_service import fast_query
    except ImportError:
        from services.supabase_safe import safe_select, safe_update

    with open(SQL_PATH) as f:
        sql = f.read()

    statements = [s.strip() for s in sql.split(";") if s.strip()]
    passed = 0
    failed = 0
    for stmt in statements:
        try:
            from services.neon_service import fast_query
            fast_query(stmt, [], timeout_ms=10000)
            passed += 1
            print(f"  ✓ {stmt[:70]}...")
        except Exception as e:
            failed += 1
            print(f"  ✗ {stmt[:70]}... {e}")

    print(f"\nResults: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
