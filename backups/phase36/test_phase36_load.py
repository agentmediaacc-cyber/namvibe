#!/usr/bin/env python3
"""Phase 36 — Load Testing (concurrent virtual users via sequential bursts)"""

import os
import sys
import time
import threading

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
report_lines = []

ROUTES = ["/", "/messages/", "/calls/recent", "/live/", "/profile/", "/notifications/"]

def user_burst(path, count, results_list):
    for _ in range(count):
        try:
            start = time.monotonic()
            r = client.get(path)
            elapsed = (time.monotonic() - start) * 1000
            results_list.append({
                "path": path,
                "ms": elapsed,
                "status": r.status_code,
                "ok": r.status_code in (200, 302),
            })
        except Exception:
            results_list.append({"path": path, "ms": 9999, "status": 0, "ok": False})

def simulate_users(user_count, requests_per_user=2):
    all_results = []
    threads = []
    for _ in range(user_count):
        for path in ROUTES:
            t = threading.Thread(target=user_burst, args=(path, requests_per_user, all_results))
            threads.append(t)
            t.start()
    for t in threads:
        t.join()

    by_path = {}
    for r in all_results:
        by_path.setdefault(r["path"], []).append(r)

    return by_path

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1

for user_count in [50]:
    print(f"\nSimulating {user_count} concurrent users...")
    by_path = simulate_users(user_count, requests_per_user=1)
    total_requests = sum(len(v) for v in by_path.values())
    total_ok = sum(sum(1 for r in v if r["ok"]) for v in by_path.values())
    check(f"{user_count} users — {total_requests} requests, {total_ok} OK", total_ok == total_requests, f"{total_requests - total_ok} failed")

    report_lines.append(f"\n### {user_count} Users\n")
    report_lines.append(f"| Route | Requests | Avg (ms) | Max (ms) | OK | Fail |\n")
    report_lines.append(f"|---|---|---|---|---|---|\n")
    for path in ROUTES:
        results = by_path.get(path, [])
        if results:
            avg = round(sum(r["ms"] for r in results) / len(results), 1)
            mx = round(max(r["ms"] for r in results), 1)
            ok_count = sum(1 for r in results if r["ok"])
            fail_count = len(results) - ok_count
            report_lines.append(f"| `{path}` | {len(results)} | {avg} | {mx} | {ok_count} | {fail_count} |\n")
            check(f"  {path}: {len(results)} req, avg {avg}ms, max {mx}ms", ok_count == len(results), f"{fail_count} failed")

report_path = os.path.join(BASE, "reports", "phase36_load_report.md")
with open(report_path, "w") as f:
    f.write("# CHAIN Phase 36 — Load Test Report\n\n")
    f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n")
    f.write("## Summary\n\n")
    f.write(f"- Passed: {passed}/{passed+failed}\n")
    f.write(f"- Failed: {failed}/{passed+failed}\n\n")
    f.writelines(report_lines)
    f.write("\n## Verdict\n\n")
    if failed == 0:
        f.write("- [x] All load tests passed\n")
    else:
        f.write("- [ ] Some load tests failed\n")
    f.write("\n*Note: Tested via Flask test client sequentially. Real production load testing requires Locust or k6.*\n")

print(f"\nReport written to {report_path}")
print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
