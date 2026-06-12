#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SQL_FILES = [
    ROOT / "sql" / "phase_namvibe_runtime_schema_fix.sql",
    ROOT / "sql" / "phase_namvibe_runtime_indexes.sql",
]


def _statements(path):
    sql = path.read_text(encoding="utf-8")
    return [stmt.strip() for stmt in sql.split(";") if stmt.strip()]


def main():
    os.chdir(ROOT)
    from services.neon_service import write_query

    applied = 0
    for path in SQL_FILES:
        if not path.exists():
            print(f"FAIL: missing {path}")
            return 1
        for stmt in _statements(path):
            write_query(stmt + ";", timeout_ms=20000)
            applied += 1
    print(f"PASS: applied NamVibe runtime schema fix ({applied} statements)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
