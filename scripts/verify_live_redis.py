#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.redis_service import get_redis_health


def main():
    health = get_redis_health() or {}
    scheme = str(health.get("redis_url_scheme") or "")
    configured = bool(health.get("configured") or health.get("redis_url_present") or health.get("url_present") or scheme)
    connected = bool(health.get("connected"))
    fallback = bool(health.get("fallback"))

    print(f"[{'PASS' if configured else 'FAIL'}] Redis configured")
    if connected:
        print(f"[PASS] Redis ping :: latency_ms={health.get('latency_ms')}")
        print("PASS")
        return 0

    detail = health.get("error") or health.get("status") or "not connected"
    if fallback and configured:
        print(f"[FAIL] Redis ping :: fallback active ({detail})")
    else:
        print(f"[FAIL] Redis ping :: {detail}")
    print("FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
