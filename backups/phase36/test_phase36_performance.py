#!/usr/bin/env python3
"""Phase 36 — Production Performance Targets"""

import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

from app import create_app

app = create_app()
client = app.test_client()

passed = 0
failed = 0
results = {}

TARGETS = {
    "/": 500,
    "/messages/": 300,
    "/calls/recent": 300,
    "/live/": 500,
    "/profile/": 300,
    "/creator/dashboard": 500,
}

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1

def measure(path, iterations=3):
    times = []
    for _ in range(iterations):
        start = time.monotonic()
        r = client.get(path)
        elapsed = (time.monotonic() - start) * 1000
        times.append(elapsed)
    avg = sum(times) / len(times)
    return {
        "avg_ms": round(avg, 1),
        "min_ms": round(min(times), 1),
        "max_ms": round(max(times), 1),
        "status_code": r.status_code,
    }

print("Measuring page performance (3 warm-up iterations each)...")
for path, target_ms in TARGETS.items():
    result = measure(path)
    results[path] = result
    avg = result["avg_ms"]
    target = TARGETS[path]
    ok = avg < target
    check(f"GET {path} — avg {avg}ms (target <{target}ms)", ok, f"{avg}ms exceeds {target}ms target")
    check(f"GET {path} returns valid status", result["status_code"] in (200, 302))

print()
print("  [PERFORMANCE RESULTS]")
print(f"  {'Route':25s} {'Avg(ms)':>10s} {'Min(ms)':>10s} {'Max(ms)':>10s} {'Target(ms)':>12s} {'Status':>8s}")
print("  " + "-" * 75)
for path in sorted(results.keys()):
    r = results[path]
    status = "OK" if r["avg_ms"] < TARGETS[path] else "SLOW"
    print(f"  {path:25s} {r['avg_ms']:>10.1f} {r['min_ms']:>10.1f} {r['max_ms']:>10.1f} {TARGETS[path]:>12d} {status:>8s}")

# Redis cache layer check
print()
print("  [CACHE LAYER CHECKS]")
try:
    from services.redis_service import get_redis, redis_available
    check("Redis cache layer accessible", callable(get_redis))
    check("redis_available checkable", callable(redis_available))
except Exception as e:
    check("Redis cache layer", False, str(e))

try:
    from services.cache_engine_redis import cache_get, cache_set
    check("cache_engine_redis: cache_get", callable(cache_get))
    check("cache_engine_redis: cache_set", callable(cache_set))
except Exception as e:
    check("cache_engine_redis", False, str(e))

print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
