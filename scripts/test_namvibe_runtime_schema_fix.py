#!/usr/bin/env python3
import contextlib
import io
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check(name, ok, detail=""):
    print(("PASS" if ok else "FAIL") + f": {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        raise AssertionError(name)


def main():
    os.chdir(ROOT)
    schema_sql = ROOT / "sql" / "phase_namvibe_runtime_schema_fix.sql"
    index_sql = ROOT / "sql" / "phase_namvibe_runtime_indexes.sql"
    apply_script = ROOT / "scripts" / "apply_namvibe_runtime_schema_fix.py"
    check("migration file exists", schema_sql.exists())
    check("index migration file exists", index_sql.exists())
    check("apply script exists", apply_script.exists())

    result = subprocess.run([sys.executable, str(apply_script)], cwd=ROOT, text=True, capture_output=True, timeout=60)
    check("apply script runs", result.returncode == 0, (result.stdout + result.stderr)[-500:])

    os.environ.setdefault("FLASK_TESTING", "1")
    from app import app

    from services.neon_service import fast_query
    cols = fast_query(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'chain_profiles'
        """,
        timeout_ms=5000,
        default=[],
    )
    col_names = {row.get("column_name") for row in cols}
    for col in ("avatar_size_bytes", "cover_size_bytes", "avatar_storage_path", "cover_storage_path"):
        check(f"chain_profiles has {col}", col in col_names)

    idx_rows = fast_query(
        """
        SELECT indexname, indexdef FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename IN ('chain_profiles', 'chain_wallets')
        """,
        timeout_ms=5000,
        default=[],
    )
    idx_text = "\n".join((row.get("indexname", "") + " " + row.get("indexdef", "")) for row in idx_rows)
    check("chain_profiles auth_user_id index exists", "auth_user_id" in idx_text)
    check("chain_wallets profile_id index or unique constraint exists", "chain_wallets" in idx_text and "profile_id" in idx_text)

    app.config["TESTING"] = True
    captured = io.StringIO()
    with app.test_client() as client, contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        for route in ("/", "/api/home/feed?tab=for_you&page=1", "/live/", "/live/studio"):
            response = client.get(route, follow_redirects=False)
            expected = {200} if route != "/live/studio" else {200, 302, 303}
            check(f"{route} returns safely", response.status_code in expected, str(response.status_code))
    logs = captured.getvalue()
    check("no list index out of range during homepage test", "list index out of range" not in logs)
    check("no avatar_size_bytes missing column error", "column avatar_size_bytes does not exist" not in logs)

    final_check = ROOT / "scripts" / "final_launch_check.py"
    if final_check.exists():
        result = subprocess.run([sys.executable, str(final_check)], cwd=ROOT, text=True, capture_output=True, timeout=120)
        check("final_launch_check still passes", result.returncode == 0, (result.stdout + result.stderr)[-1000:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
