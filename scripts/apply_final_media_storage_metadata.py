#!/usr/bin/env python3
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SQL_PATH = BASE / "sql" / "final_media_storage_metadata.sql"
sys.path.insert(0, str(BASE))


def main():
    os.chdir(BASE)
    sql = SQL_PATH.read_text(encoding="utf-8")
    if "IF NOT EXISTS" not in sql:
        print("FAIL: migration must be idempotent")
        return 1
    if any(term in sql.lower() for term in (" bytea", " blob", "base64")):
        print("FAIL: migration contains raw binary storage type/pattern")
        return 1
    try:
        from services.neon_service import write_query
        write_query(sql, timeout_ms=15000)
        print("PASS: final media storage metadata migration applied")
        return 0
    except Exception as error:
        print(f"FAIL: migration apply failed: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
