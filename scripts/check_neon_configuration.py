#!/usr/bin/env python3
from __future__ import annotations

import json
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.env_service import load_project_env, get_env, mask_env_value
from services.neon_service import DATABASE_URL, _canonical_database_url, _get_dsn_kwargs, fetch_one


def _dsn_parts(raw: str) -> dict:
    parsed = urlparse(raw) if raw else None
    return {
        "host": parsed.hostname if parsed else "",
        "port": parsed.port if parsed and parsed.port else 5432,
        "database": parsed.path.lstrip("/") if parsed and parsed.path else "",
        "sslmode": (parsed.query or "").find("sslmode=") >= 0 if parsed else False,
    }


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=True))


def _resolve(host: str, port: int) -> dict:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        return {"ok": True, "addresses": sorted({info[4][0] for info in infos})}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _safe_db_check() -> dict:
    started = time.perf_counter()
    try:
        row = fetch_one("SELECT 1 AS ok", timeout_ms=5000)
        return {"ok": bool(row and row.get("ok") == 1), "row": row, "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}


def main() -> int:
    load_project_env()
    env_vars = {name: get_env(name, "") or "" for name in ("DATABASE_URL", "NEON_DATABASE_URL", "NEON_URL", "PGHOST", "PGPORT")}
    active_sources = {name: value for name, value in env_vars.items() if value}
    raw = (DATABASE_URL or env_vars.get("DATABASE_URL") or "").strip()
    effective = _get_dsn_kwargs().get("dsn", raw)
    raw_parts = _dsn_parts(raw)
    eff_parts = _dsn_parts(effective)
    db_candidates = {name: value for name, value in active_sources.items() if name in {"DATABASE_URL", "NEON_DATABASE_URL", "NEON_URL"}}
    conflicting = len({value for value in db_candidates.values() if value}) > 1
    _emit({
        "record_type": "neon_configuration",
        "config_source": ".env",
        "variable": "DATABASE_URL",
        "hostname": raw_parts["host"],
        "port": raw_parts["port"],
        "database": raw_parts["database"],
        "sslmode": raw_parts["sslmode"],
        "effective_hostname": eff_parts["host"],
        "effective_port": eff_parts["port"],
        "effective_database": eff_parts["database"],
        "effective_sslmode": eff_parts["sslmode"],
        "conflicting": conflicting,
        "rewritten_to_pooler": raw_parts["host"] != eff_parts["host"],
        "masked_variables": {name: mask_env_value(name, value) for name, value in active_sources.items()},
    })
    if conflicting:
        _emit({"record_type": "neon_configuration_summary", "status": "conflicting_dsn"})
        return 1
    if not raw_parts["host"]:
        _emit({"record_type": "neon_configuration_summary", "status": "missing_database_url"})
        return 1
    dns = _resolve(eff_parts["host"] or raw_parts["host"], eff_parts["port"] or raw_parts["port"])
    _emit({"record_type": "neon_configuration_dns", "dns": dns})
    db = _safe_db_check()
    if not db.get("ok"):
        _emit({"record_type": "neon_configuration_summary", "status": "connection_failure", "error": db.get("error", "empty_result")})
        return 1
    try:
        row_db = fetch_one("SELECT current_database() AS db, current_user AS current_user", timeout_ms=5000)
        table_row = fetch_one("SELECT to_regclass('public.chain_reels') AS chain_reels", timeout_ms=5000)
        count_row = fetch_one("SELECT COUNT(*)::int AS reel_count FROM chain_reels", timeout_ms=5000)
    except Exception as exc:
        _emit({"record_type": "neon_configuration_summary", "status": "schema_failure", "error": f"{type(exc).__name__}: {exc}"})
        return 1
    db_name = row_db["db"] if row_db else None
    chain_reels = table_row["chain_reels"] if table_row else None
    reel_count = count_row["reel_count"] if count_row else None
    result = {
        "record_type": "neon_configuration_summary",
        "status": "ok",
        "database": db_name,
        "chain_reels": chain_reels,
        "reel_count": reel_count,
    }
    _emit(result)
    return 0 if db_name and chain_reels else 1


if __name__ == "__main__":
    raise SystemExit(main())
