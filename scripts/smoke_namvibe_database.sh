#!/bin/bash

set -euo pipefail

cd "${APP_DIR:-$HOME/Desktop/chain_app}"

python3 - <<'PY'
import os
import time

results = []

def emit(name, ok, latency_ms=None, detail=""):
    state = "PASS" if ok else "FAIL"
    latency = f" latency_ms={latency_ms:.1f}" if latency_ms is not None else ""
    detail_text = f" {detail}" if detail else ""
    print(f"{state} {name}{latency}{detail_text}".rstrip())
    results.append(ok)

# Neon
os.environ["FLASK_ENV"] = "production"
os.environ["ENV"] = "production"
os.environ["CHAIN_FAST_LOCAL"] = "0"
os.environ["CHAIN_DISABLE_DB_PING"] = "0"
os.environ["CHAIN_DISABLE_SCHEMA_CHECK"] = "0"
try:
    from services.neon_service import get_neon_health
    started = time.perf_counter()
    health = get_neon_health()
    elapsed_ms = (time.perf_counter() - started) * 1000
    latency_ms = health.get("latency_ms")
    if latency_ms is None:
        latency_ms = elapsed_ms
    emit(
        "Neon",
        bool(health.get("connected")),
        float(latency_ms),
        f"status={health.get('status')} configured={health.get('configured')}",
    )
except Exception as exc:
    emit("Neon", False, None, f"error={exc}")

# Redis
try:
    from services.redis_service import get_redis_health
    started = time.perf_counter()
    health = get_redis_health()
    elapsed_ms = (time.perf_counter() - started) * 1000
    latency_ms = health.get("latency_ms")
    if latency_ms is None:
        latency_ms = elapsed_ms
    emit(
        "Redis",
        bool(health.get("connected")),
        float(latency_ms),
        f"status={health.get('status')}",
    )
except Exception as exc:
    emit("Redis", False, None, f"error={exc}")

# Supabase
try:
    from utils.supabase_client import get_supabase, get_supabase_admin
    started = time.perf_counter()
    client = get_supabase()
    admin = get_supabase_admin()
    latency_ms = (time.perf_counter() - started) * 1000
    ok = bool(client) and bool(admin) and hasattr(client, "auth")
    emit("Supabase", ok, latency_ms, "status=ok" if ok else "status=error")
except Exception as exc:
    emit("Supabase", False, None, f"error={exc}")

if not all(results):
    raise SystemExit(1)
PY
