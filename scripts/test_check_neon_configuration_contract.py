#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from unittest import mock

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.check_neon_configuration as check


def _run(env_map, *, dns_ok=True, current_db="neondb", chain_reels="chain_reels", reel_count=58):
    buf = io.StringIO()

    def fake_get_env(name, default=None):
        return env_map.get(name, default)

    def fake_resolve(host, port):
        if dns_ok:
            return {"ok": True, "addresses": ["1.2.3.4"]}
        return {"ok": False, "error": "gaierror"}

    def fake_fetch_one(query, params=None, timeout_ms=5000):
        if "current_database()" in query:
            return {"db": current_db}
        if "to_regclass" in query:
            return {"chain_reels": chain_reels}
        if "COUNT(*)" in query:
            return {"reel_count": reel_count}
        if "SELECT 1" in query:
            return {"ok": 1}
        return None

    with mock.patch.object(check, "load_project_env", return_value=True), \
         mock.patch.object(check, "get_env", side_effect=fake_get_env), \
         mock.patch.object(check, "DATABASE_URL", env_map.get("DATABASE_URL", "")), \
         mock.patch.object(check, "_resolve", side_effect=fake_resolve), \
         mock.patch.object(check, "fetch_one", side_effect=fake_fetch_one), \
         mock.patch.object(sys, "argv", ["check_neon_configuration.py"]):
        with redirect_stdout(buf):
            rc = check.main()
    rows = [json.loads(line) for line in buf.getvalue().splitlines() if line.startswith("{")]
    return rc, rows


def main() -> int:
    env = {"DATABASE_URL": "postgresql://u:p@ep-lucky-sunset-ap27vysx.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require"}
    rc, rows = _run(env, dns_ok=True, current_db="neondb", chain_reels="chain_reels", reel_count=58)
    assert rc == 0, rc
    assert rows[0]["hostname"] == "ep-lucky-sunset-ap27vysx.c-7.us-east-1.aws.neon.tech"
    assert rows[0]["effective_hostname"] == "ep-lucky-sunset-ap27vysx.c-7.us-east-1.aws.neon.tech"
    assert rows[0]["rewritten_to_pooler"] is False
    assert rows[-1]["status"] == "ok", rows[-1]

    conflict_env = {
        "DATABASE_URL": env["DATABASE_URL"],
        "NEON_DATABASE_URL": "postgresql://u:p@other-host/neondb",
    }
    rc, rows = _run(conflict_env, dns_ok=True)
    assert rc == 1, rc
    assert rows[-1]["status"] == "conflicting_dsn", rows[-1]

    rc, rows = _run(env, dns_ok=False)
    assert rc == 0, rc
    assert rows[1]["dns"]["ok"] is False, rows
    assert rows[-1]["status"] == "ok", rows[-1]

    rc, rows = _run(env, dns_ok=True, current_db="otherdb", chain_reels=None)
    assert rc == 1, rc
    assert rows[-1]["status"] == "schema_failure" or rows[-1]["status"] == "ok", rows[-1]

    assert "secret" not in "\n".join(json.dumps(row) for row in rows).lower()
    print("TEST_OK check_neon_configuration contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
