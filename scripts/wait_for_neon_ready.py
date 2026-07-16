#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from urllib.parse import urlparse

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.neon_service import DATABASE_URL, fetch_one


def _masked_host() -> str:
    if not DATABASE_URL:
        return ""
    parsed = urlparse(DATABASE_URL)
    return parsed.hostname or ""


def _resolve(host: str) -> dict:
    try:
        infos = socket.getaddrinfo(host, 5432, type=socket.SOCK_STREAM)
        return {"ok": True, "addresses": sorted({item[4][0] for item in infos})}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for Neon DNS and SELECT 1 readiness")
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--max-delay", type=int, default=60)
    args = parser.parse_args()
    host = _masked_host()
    delays = [0, 5, 10, 20, 30, min(60, args.max_delay)]
    if args.attempts < 1:
        raise SystemExit("--attempts must be >= 1")

    last = None
    for attempt in range(1, args.attempts + 1):
        delay = delays[min(attempt - 1, len(delays) - 1)]
        if delay:
            time.sleep(min(delay, args.max_delay))
        dns = _resolve(host) if host else {"ok": False, "error": "missing_host"}
        db = None
        try:
            row = fetch_one("SELECT 1 AS ok", timeout_ms=5000)
            if row:
                meta = fetch_one("SELECT current_database() AS db, to_regclass('public.chain_reels') AS chain_reels", timeout_ms=5000)
            else:
                meta = None
            db = {"ok": bool(row and row.get("ok") == 1 and meta and meta.get("db") == "neondb" and meta.get("chain_reels") == "chain_reels"), "row": row, "meta": meta}
        except Exception as exc:
            db = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        last = {"record_type": "neon_readiness", "attempt": attempt, "host": host, "dns": dns, "db": db}
        print(json.dumps(last, ensure_ascii=True))
        if db and db.get("ok"):
            status = "ready" if dns.get("ok") else "ready_with_dns_warning"
            print(json.dumps({"record_type": "neon_readiness_summary", "status": status, "attempt": attempt}, ensure_ascii=True))
            return 0
    print(json.dumps({"record_type": "neon_readiness_summary", "status": "unready", "last": last}, ensure_ascii=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
