#!/usr/bin/env python3
"""Phase 35 — Local Load Smoke Test (Flask test client, no real Neon)"""

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
total_requests = 0

load_results = {}

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1

def smoke_request(path, count=10, valid_codes=(200, 302)):
    times = []
    statuses = []
    successes = 0
    for _ in range(count):
        try:
            start = time.monotonic()
            r = client.get(path)
            elapsed = (time.monotonic() - start) * 1000
            times.append(elapsed)
            statuses.append(r.status_code)
            if r.status_code in valid_codes:
                successes += 1
        except Exception as e:
            times.append(9999)
            statuses.append(0)
    avg_ms = sum(times) / len(times)
    max_ms = max(times)
    return {
        "path": path,
        "count": count,
        "avg_ms": round(avg_ms, 1),
        "max_ms": round(max_ms, 1),
        "statuses": list(set(statuses)),
        "successes": successes,
        "failures": count - successes,
    }

# Run smoke requests
print("Running load smoke tests...")
load_results["/"] = smoke_request("/", 20)
load_results["/messages/"] = smoke_request("/messages/", 20)
load_results["/calls/recent"] = smoke_request("/calls/recent", 10)
load_results["/live/"] = smoke_request("/live/", 10)
load_results["/notifications/"] = smoke_request("/notifications/", 10)
load_results["/profile/"] = smoke_request("/profile/", 10)

# Validate each result
for path, result in load_results.items():
    total_requests += result["count"]
    avg = result["avg_ms"]
    mx = result["max_ms"]
    succ = result["successes"]
    statuses = result["statuses"]
    check(f"GET {path} ({result['count']}x) — avg {avg}ms, max {mx}ms", succ == result["count"], f"{result['failures']} failures")
    for s in statuses:
        check(f"GET {path} status code {s}", s in (200, 302), f"Unexpected status {s}")

# Summary
print()
print("  [LOAD SMOKE RESULTS]")
print(f"    Total requests: {total_requests}")
for path, result in load_results.items():
    print(f"    {path:25s}  {result['count']:2d}x  avg {result['avg_ms']:>8.1f}ms  max {result['max_ms']:>8.1f}ms  OK:{result['successes']}  FAIL:{result['failures']}")

# Write report
report_path = os.path.join(BASE, "reports", "phase35_load_test.md")
with open(report_path, "w") as f:
    f.write(f"# CHAIN Phase 35 — Load Smoke Test Results\n")
    f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n")
    f.write(f"## Summary\n\n")
    f.write(f"- Total requests: {total_requests}\n")
    f.write(f"- Passed: {passed}/{passed+failed}\n")
    f.write(f"- Failed: {failed}/{passed+failed}\n\n")
    f.write(f"## Per-Route Results\n\n")
    f.write(f"| Route | Requests | Avg (ms) | Max (ms) | Success | Failures |\n")
    f.write(f"|-------|----------|----------|----------|---------|----------|\n")
    for path, result in load_results.items():
        f.write(f"| `{path}` | {result['count']} | {result['avg_ms']} | {result['max_ms']} | {result['successes']} | {result['failures']} |\n")
    f.write(f"\n## Verdict\n\n")
    if failed == 0:
        f.write("- [x] All requests passed\n")
        f.write("- [ ] Performance degradation detected\n")
    else:
        f.write("- [ ] All requests passed\n")
        f.write("- [x] Performance degradation detected\n")
    f.write("\n*This is a local smoke test. Real production load testing requires a dedicated tool like Locust or k6.*\n")
print(f"\nReport written to {report_path}")
print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
