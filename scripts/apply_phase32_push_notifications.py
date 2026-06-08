#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / "venv" / "bin" / "python3"
if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), *sys.argv])
sys.path.insert(0, str(ROOT))

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"


def main():
    sql_file = ROOT / "sql" / "phase32_push_notifications.sql"
    sql_text = sql_file.read_text("utf-8")

    from services.neon_service import fast_query, write_query, get_pool_status

    status = get_pool_status()
    if not status.get("configured"):
        print("[migration] Neon not configured; creating tables is skipped.")
        print("[migration] Tables will be created when Neon is available.")
        print("[migration] Migration SQL is at sql/phase32_push_notifications.sql")
        return 0

    statements = [s.strip() for s in sql_text.split(";") if s.strip()]
    executed = 0
    failed = 0
    for statement in statements:
        try:
            write_query(statement, timeout_ms=5000)
            executed += 1
        except Exception as e:
            print(f"[migration] Statement failed (likely already exists): {e}")
            failed += 1

    print(f"[migration] phase32_push_notifications.sql applied: {executed} OK, {failed} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
