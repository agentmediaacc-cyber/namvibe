#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from unittest import mock

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.wait_for_neon_ready as ready


def _run_with_side_effects(resolve_side_effect, fetch_side_effect, attempts=3):
    buf = io.StringIO()
    with mock.patch.object(ready, "DATABASE_URL", "postgresql://user:pass@ep-lucky-sunset-ap27vysx-pooler.c-7.us-east-1.aws.neon.tech/db"), \
         mock.patch.object(ready, "_resolve", side_effect=resolve_side_effect), \
         mock.patch.object(ready, "fetch_one", side_effect=fetch_side_effect), \
         mock.patch.object(ready.time, "sleep", return_value=None), \
         mock.patch.object(sys, "argv", ["wait_for_neon_ready.py", "--attempts", str(attempts), "--max-delay", "1"]):
        with redirect_stdout(buf):
            rc = ready.main()
    return rc, [json.loads(line) for line in buf.getvalue().splitlines() if line.startswith("{")]


def main() -> int:
    def ready_fetch(query, timeout_ms=5000):
        if "current_database()" in query:
            return {"db": "neondb", "chain_reels": "chain_reels"}
        return {"ok": 1}

    rc, rows = _run_with_side_effects(lambda host: {"ok": True, "addresses": ["1.2.3.4"]}, ready_fetch, attempts=1)
    assert rc == 0, rc
    assert rows[-1]["status"] == "ready", rows

    dns = iter([{"ok": False, "error": "gaierror"}, {"ok": True, "addresses": ["1.2.3.4"]}])
    rc, rows = _run_with_side_effects(lambda host: next(dns), ready_fetch, attempts=2)
    assert rc == 0, rc
    assert rows[-1]["status"] == "ready_with_dns_warning", rows
    assert rows[0]["dns"]["ok"] is False, rows

    rc, rows = _run_with_side_effects(lambda host: {"ok": False, "error": "gaierror"}, ready_fetch, attempts=2)
    assert rc == 0, rc
    assert rows[-1]["status"] == "ready_with_dns_warning", rows

    output = "\n".join(json.dumps(row) for row in rows)
    assert "secret" not in output.lower()
    print("TEST_OK wait_for_neon_ready contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
