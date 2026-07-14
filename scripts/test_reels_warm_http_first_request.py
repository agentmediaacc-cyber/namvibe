#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("NAMVIBE_PUBLIC_BASE_URL", "http://127.0.0.1:8083").rstrip("/")


def main() -> int:
    env = os.environ.copy()
    env["CHAIN_REDIS_ALLOW_LOCAL_FALLBACK"] = "1"
    env["REQUIRE_SHARED_CACHE"] = "1"
    env["CHAIN_CACHE_NAMESPACE"] = f"test_http_{int(time.time())}"

    warm = subprocess.run([sys.executable, "scripts/warm_production_runtime.py", "--reels"], cwd=str(ROOT), env=env, text=True, capture_output=True, check=False)
    if warm.returncode != 0:
        print(warm.stdout)
        print(warm.stderr, file=sys.stderr)
        return warm.returncode

    curl = subprocess.run(["curl", "-sS", "-D", "-", f"{BASE_URL}/reels/api/reels/feed?limit=5"], cwd=str(ROOT), text=True, capture_output=True, check=False)
    if curl.returncode != 0:
        print(curl.stdout)
        print(curl.stderr, file=sys.stderr)
        return curl.returncode
    headers, _, body = curl.stdout.partition("\r\n\r\n")
    if not body:
        headers, _, body = curl.stdout.partition("\n\n")
    payload = json.loads(body)
    assert payload["items"] == payload["reels"]
    assert payload["has_more"] in {True, False}
    print("TEST_OK reels warm http first request")
    print(headers.splitlines()[0] if headers else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
