import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_project_python():
    try:
        import psycopg2  # noqa: F401
    except ModuleNotFoundError:
        venv_python = ROOT / "venv" / "bin" / "python3"
        if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
            os.execv(str(venv_python), [str(venv_python), *sys.argv])
        raise


_ensure_project_python()

from services.neon_service import write_query


SQL_PATH = ROOT / "sql" / "phase28_profile_schema_fix.sql"


def main():
    sql_text = SQL_PATH.read_text(encoding="utf-8")
    statements = [statement.strip() for statement in sql_text.split(";") if statement.strip()]
    for statement in statements:
        write_query(statement, timeout_ms=8000)
    print(f"phase28 profile schema fix applied: {len(statements)} statement(s)")


if __name__ == "__main__":
    main()
