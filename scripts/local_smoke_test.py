"""
Phase 68B — Local Smoke Test.
Tests critical routes and APIs against a running CHAIN instance.
"""
import os
import sys
import time
import requests as http_requests

BASE = os.environ.get("CHAIN_TEST_BASE", "http://127.0.0.1:5000")
TIMEOUT = 10


def check(method, path, label=None, expected_statuses=(200, 302, 401)):
    url = f"{BASE}{path}"
    label = label or path
    try:
        start = time.perf_counter()
        resp = http_requests.request(method, url, timeout=TIMEOUT, allow_redirects=False)
        elapsed = (time.perf_counter() - start) * 1000
        status_ok = resp.status_code in expected_statuses
        status_str = "PASS" if status_ok else "FAIL"
        print(f"  [{status_str}] {label} -> {resp.status_code} ({elapsed:.0f}ms)")
        return status_ok
    except Exception as e:
        print(f"  [FAIL] {label} -> ERROR: {e}")
        return False


def main():
    print("=" * 60)
    print(f"CHAIN Local Smoke Test — {BASE}")
    print("=" * 60)

    results = []

    # Page routes
    results.append(check("GET", "/healthz", "/healthz", expected_statuses=(200,)))
    results.append(check("GET", "/", "Home"))
    results.append(check("GET", "/login", "Login redirect"))
    results.append(check("GET", "/register", "Register redirect"))
    results.append(check("GET", "/profile/", "/profile/", expected_statuses=(302, 200, 401)))
    results.append(check("GET", "/messages/", "/messages/", expected_statuses=(302, 200, 401)))
    results.append(check("GET", "/notifications/", "/notifications/", expected_statuses=(302, 200, 401)))

    # Public routes
    results.append(check("GET", "/marketplace", "/marketplace", expected_statuses=(200, 302)))
    results.append(check("GET", "/dating/discover", "/dating/discover", expected_statuses=(200, 302)))
    results.append(check("GET", "/wallet/", "/wallet/", expected_statuses=(302, 200, 401)))
    results.append(check("GET", "/creator/dashboard", "/creator/dashboard", expected_statuses=(302, 200, 401)))
    results.append(check("GET", "/live/", "/live/", expected_statuses=(200, 302)))
    results.append(check("GET", "/ai/", "/ai/", expected_statuses=(200, 302)))
    results.append(check("GET", "/terms", "/terms", expected_statuses=(200,)))
    results.append(check("GET", "/health/db", "/health/db", expected_statuses=(200, 503)))
    results.append(check("GET", "/health/redis", "/health/redis", expected_statuses=(200, 503)))

    # API routes
    results.append(check("GET", "/api/notifications/unread-count", "/api/notifications/unread-count", expected_statuses=(200, 401)))
    results.append(check("GET", "/api/home/feed?tab=for_you&page=1", "Feed API", expected_statuses=(200, 401)))

    passed = sum(results)
    total = len(results)
    print("=" * 60)
    print(f"RESULTS: {passed}/{total} passed")
    if passed == total:
        print("✅ All smoke tests passed!")
    else:
        print(f"❌ {total - passed} test(s) failed")
    print("=" * 60)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
