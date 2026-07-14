#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from urllib.request import urlopen, Request


def _fetch(url: str):
    started = time.perf_counter()
    with urlopen(Request(url, headers={"Accept": "text/html"}), timeout=30) as resp:
        body = resp.read()
        status = getattr(resp, "status", 200)
    return {
        "status": status,
        "total_ms": round((time.perf_counter() - started) * 1000, 2),
        "size": len(body),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("NAMVIBE_PUBLIC_BASE_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--path", default="/reels/")
    args = parser.parse_args(argv)

    url = args.base_url.rstrip("/") + args.path
    latencies = []
    results = []
    for idx in range(1, args.requests + 1):
        result = _fetch(url)
        latencies.append(result["total_ms"])
        results.append({"request": idx, **result})
        print(json.dumps({"request": idx, **result}, sort_keys=True))

    summary = {
        "min": round(min(latencies), 2),
        "median": round(statistics.median(latencies), 2),
        "p90": round(statistics.quantiles(latencies, n=10)[8], 2) if len(latencies) >= 10 else round(max(latencies), 2),
        "p95": round(statistics.quantiles(latencies, n=20)[18], 2) if len(latencies) >= 20 else round(max(latencies), 2),
        "p99": round(sorted(latencies)[max(0, int(len(latencies) * 0.99) - 1)], 2),
        "max": round(max(latencies), 2),
        "over_1s": sum(1 for v in latencies if v > 1000),
        "over_2s": sum(1 for v in latencies if v > 2000),
        "over_3s": sum(1 for v in latencies if v > 3000),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
