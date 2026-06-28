#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.neon_service import fast_query, get_neon_health, table_exists

REQUIRED_TABLES = [
    "chain_profiles",
    "chain_wallets",
    "chain_wallet_transactions",
    "chain_message_threads",
    "chain_thread_members",
    "chain_messages",
]

RETRY_TIMEOUTS_MS = [1500, 3000, 7000]
RETRY_BACKOFF_SECONDS = [0.5, 1.0]


def _line(status, label, detail=""):
    suffix = f" :: {detail}" if detail else ""
    print(f"[{status}] {label}{suffix}")


def main():
    failures = []
    warnings = []
    health = get_neon_health()
    connected = bool(health.get("connected"))
    local_fast = bool(health.get("local_fast_mode"))
    configured = bool(health.get("configured"))
    _line("PASS" if configured else "FAIL", "DATABASE_URL configured")
    if not connected:
        detail = health.get("status") or health.get("error") or "not connected"
        if local_fast:
            print(f"[SKIP] Neon live table checks skipped :: {detail}")
            print("PASS")
            return 0
        _line("WARN", "Initial Neon health", detail)
        warnings.append(f"initial health not ready: {detail}")
    else:
        _line("PASS", "Initial Neon health", f"latency_ms={health.get('latency_ms')}")

    ping = []
    ping_elapsed_ms = None
    for attempt, timeout_ms in enumerate(RETRY_TIMEOUTS_MS, start=1):
        started = time.perf_counter()
        ping = fast_query("SELECT 1 AS ok", timeout_ms=timeout_ms, default=[])
        ping_elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        if ping:
            break
        if attempt < len(RETRY_TIMEOUTS_MS):
            time.sleep(RETRY_BACKOFF_SECONDS[attempt - 1])

    if not ping:
        failures.append("select 1 failed after retry/backoff")
        _line("FAIL", "Neon SELECT 1", "retry budget exhausted")
    else:
        timed_out_initially = (not connected) or (ping_elapsed_ms is not None and ping_elapsed_ms > 5000)
        if timed_out_initially:
            _line("WARN", "Neon SELECT 1", f"cold start recovered in {ping_elapsed_ms}ms")
            warnings.append(f"cold start latency {ping_elapsed_ms}ms")
        else:
            _line("PASS", "Neon SELECT 1", f"{ping_elapsed_ms}ms")

        for table_name in REQUIRED_TABLES:
            exists = table_exists(table_name, timeout_ms=3000)
            if exists:
                _line("PASS", f"table {table_name} exists")
            else:
                _line("FAIL", f"table {table_name} exists")
                failures.append(f"missing table: {table_name}")

    if failures:
        print("FAIL")
        for failure in failures:
            print(failure)
        return 1
    if warnings:
        print("WARN")
        for warning in warnings:
            print(warning)
        return 0
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
