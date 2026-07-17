#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.env_service import load_project_env, get_env, mask_env_value
from services.neon_service import (
    DATABASE_URL,
    _canonical_database_url,
    _get_dsn_kwargs,
    _pool_instance,
    fetch_one,
    reset_neon_pool,
)


def _mask_dsn(raw: str) -> str:
    if not raw or "@" not in raw:
        return raw
    left, right = raw.split("@", 1)
    if "://" in left:
        scheme, _ = left.split("://", 1)
        left = f"{scheme}://***:***"
    return f"{left}@{right}"


def _summary(url: str) -> dict:
    parsed = urlparse(url or "")
    return {
        "host": parsed.hostname or "",
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/") if parsed.path else "",
        "sslmode": "sslmode=" in (parsed.query or ""),
    }


def _emit(stage: str, *, status: str, started: float, **payload) -> None:
    record = {
        "record_type": "neon_connection_compare",
        "stage": stage,
        "status": status,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        **payload,
    }
    print(json.dumps(record, ensure_ascii=True))


def _sanitize_error(exc: Exception) -> str:
    text = str(exc).replace(str(ROOT), "[repo]")
    return text[:240]


def _run_query(stage: str, sql_text: str):
    import psycopg2

    started = time.perf_counter()
    try:
        conn = psycopg2.connect(_canonical_database_url(), connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(sql_text)
                row = cur.fetchone()
            _emit(stage, status="ok", started=started, row=row)
            return row
        finally:
            conn.close()
    except Exception as exc:
        _emit(stage, status="error", started=started, error_type=type(exc).__name__, sanitized_error=_sanitize_error(exc))
        return None


def main() -> int:
    load_project_env()
    raw = (DATABASE_URL or get_env("DATABASE_URL", "") or "").strip()
    eff = _get_dsn_kwargs().get("dsn", raw)
    started = time.perf_counter()
    _emit(
        "config_load",
        status="ok",
        started=started,
        cwd=os.getcwd(),
        python=sys.executable,
        raw_summary=_summary(raw),
        effective_summary=_summary(eff),
        masked_dsn=_mask_dsn(raw),
        masked_env={name: mask_env_value(name, get_env(name, "")) for name in ("DATABASE_URL", "NEON_DATABASE_URL", "NEON_URL", "PGHOST", "PGPORT") if get_env(name, "")},
    )

    import socket
    started = time.perf_counter()
    try:
        infos = socket.getaddrinfo(_summary(eff)["host"], _summary(eff)["port"], type=socket.SOCK_STREAM)
        _emit("socket_dns", status="ok", started=started, addresses=sorted({item[4][0] for item in infos}))
    except Exception as exc:
        _emit("socket_dns", status="error", started=started, error_type=type(exc).__name__, sanitized_error=_sanitize_error(exc))

    _run_query("direct_psycopg", "SELECT 1 AS ok")
    _run_query("diagnostic_helper", "SELECT 1 AS ok")

    started = time.perf_counter()
    try:
        pool_inst = _pool_instance()
        _emit("pool_initialization", status="ok" if pool_inst else "error", started=started, pool_ready=bool(pool_inst))
    except Exception as exc:
        _emit("pool_initialization", status="error", started=started, error_type=type(exc).__name__, sanitized_error=_sanitize_error(exc))

    started = time.perf_counter()
    try:
        row = fetch_one("SELECT 1 AS ok", timeout_ms=5000)
        _emit("fetch_one", status="ok" if row else "error", started=started, row=row)
        first_ok = bool(row)
    except Exception as exc:
        first_ok = False
        _emit("fetch_one", status="error", started=started, error_type=type(exc).__name__, sanitized_error=_sanitize_error(exc))

    started = time.perf_counter()
    try:
        row2 = fetch_one("SELECT 1 AS ok", timeout_ms=5000)
        _emit("fetch_one_reuse", status="ok" if row2 else "error", started=started, row=row2)
        second_ok = bool(row2)
    except Exception as exc:
        second_ok = False
        _emit("fetch_one_reuse", status="error", started=started, error_type=type(exc).__name__, sanitized_error=_sanitize_error(exc))

    started = time.perf_counter()
    with suppress(Exception):
        reset_neon_pool(reason="compare_probe")
    try:
        row3 = fetch_one("SELECT 1 AS ok", timeout_ms=5000)
        _emit("pool_reset", status="ok" if row3 else "error", started=started, row=row3)
        reset_ok = bool(row3)
    except Exception as exc:
        reset_ok = False
        _emit("pool_reset", status="error", started=started, error_type=type(exc).__name__, sanitized_error=_sanitize_error(exc))

    started = time.perf_counter()
    try:
        db = fetch_one("SELECT current_database() AS db, current_user AS current_user", timeout_ms=5000)
        table = fetch_one("SELECT to_regclass('public.chain_reels') AS chain_reels", timeout_ms=5000)
        count = fetch_one("SELECT COUNT(*)::int AS count FROM chain_reels", timeout_ms=5000)
        _emit(
            "schema_check",
            status="ok" if db and table and count else "error",
            started=started,
            database=db,
            chain_reels=table,
            count=count,
        )
        schema_ok = bool(db and table and count)
    except Exception as exc:
        schema_ok = False
        _emit("schema_check", status="error", started=started, error_type=type(exc).__name__, sanitized_error=_sanitize_error(exc))

    return 0 if (first_ok and second_ok and reset_ok and schema_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
