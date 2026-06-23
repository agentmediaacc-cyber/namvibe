#!/usr/bin/env python3
"""
Phase 143 — Real User Smoke Test Audit Script

Tests public domain endpoints for stability:
- GET https://namvibe.com/ must not 500/502/503/504
- GET /feedback/
- GET /reels/
- GET /notifications/
- GET /profile/@beta
- POST /reels/api/reels/view/batch
- GET /api/homepage/feed

Also checks:
- homepage HTML contains NAMVIBE_HOME_DEGRADED flag
- static JS loads
- static CSS loads
- response time recorded for each endpoint
"""

import os
import time
import sys
import re
from datetime import datetime

# Try to import requests, fall back to urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    import json as json_module
    HAS_REQUESTS = False

# Configuration
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8080")
TIMEOUT_SECONDS = 10
FAILED_STATUS_CODES = {500, 502, 503, 504}

# Test results storage
results = {
    "passed": [],
    "failed": [],
    "warnings": [],
    "response_times": {},
    "degraded_mode": None,
}


def make_request(method, path, **kwargs):
    """Make HTTP request with timeout and error handling."""
    url = f"{BASE_URL}{path}"
    start_time = time.perf_counter()
    
    try:
        if HAS_REQUESTS:
            response = requests.request(method, url, timeout=TIMEOUT_SECONDS, **kwargs)
        else:
            # Fallback to urllib
            data = kwargs.get('json') or kwargs.get('data')
            if data and isinstance(data, dict):
                data = json_module.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header('Content-Type', 'application/json')
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
                    status = response.status
                    body = response.read().decode('utf-8')
            except urllib.error.HTTPError as e:
                status = e.code
                body = e.read().decode('utf-8')
            response = type('Response', (), {'status_code': status, 'text': body, 'headers': {}})()
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return response.status_code, response.text, elapsed_ms
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return 0, str(e), elapsed_ms


def test_endpoint(name, method, path, expect_success=True, check_body=None):
    """Test a single endpoint and record results."""
    print(f"  Testing {name}...", end=" ")
    
    status, body, elapsed = make_request(method, path)
    results["response_times"][name] = round(elapsed, 2)
    
    if status in FAILED_STATUS_CODES:
        print(f"FAILED (status={status}, {elapsed:.0f}ms)")
        results["failed"].append({
            "endpoint": name,
            "path": path,
            "status": status,
            "error": f"HTTP {status}",
            "response_time_ms": elapsed
        })
    elif status == 0:
        print(f"ERROR (timeout/conn)")
        results["failed"].append({
            "endpoint": name,
            "path": path,
            "status": 0,
            "error": body,
            "response_time_ms": elapsed
        })
    elif status >= 400:
        print(f"WARNING (status={status}, {elapsed:.0f}ms)")
        results["warnings"].append({
            "endpoint": name,
            "path": path,
            "status": status,
            "response_time_ms": elapsed
        })
    else:
        print(f"PASSED (status={status}, {elapsed:.0f}ms)")
        results["passed"].append({
            "endpoint": name,
            "path": path,
            "status": status,
            "response_time_ms": elapsed
        })
        
        # Check body if provided
        if check_body and body:
            if not check_body(body):
                results["warnings"].append({
                    "endpoint": name,
                    "path": path,
                    "status": status,
                    "warning": "Body check failed",
                    "response_time_ms": elapsed
                })
    
    return status, body, elapsed


def main():
    print("=" * 60)
    print("Phase 143 — Real User Smoke Test Audit")
    print(f"Target: {BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)
    print()
    
    # 1. Test homepage (GET /)
    print("[1/9] Homepage Test")
    status, body, elapsed = make_request("GET", "/")
    
    # Check for degraded flag in homepage
    if 'window.NAMVIBE_HOME_DEGRADED' in body:
        degraded_match = re.search(r'window\.NAMVIBE_HOME_DEGRADED\s*=\s*(\w+)', body)
        if degraded_match:
            results["degraded_mode"] = degraded_match.group(1) == 'true'
            print(f"  Degraded mode flag: {results['degraded_mode']}")
    
    # Check static assets
    js_status, _, js_time = make_request("GET", "/static/js/namvibe_home_pro.js")
    css_status, _, css_time = make_request("GET", "/static/css/namvibe_home_pro.css")
    
    if js_status in FAILED_STATUS_CODES:
        results["failed"].append({"endpoint": "static-js", "status": js_status, "response_time_ms": js_time})
    if css_status in FAILED_STATUS_CODES:
        results["failed"].append({"endpoint": "static-css", "status": css_status, "response_time_ms": css_time})
    
    if status in FAILED_STATUS_CODES:
        results["failed"].append({"endpoint": "homepage", "path": "/", "status": status, "response_time_ms": elapsed})
    else:
        results["passed"].append({"endpoint": "homepage", "path": "/", "status": status, "response_time_ms": elapsed})
    
    # 2. Test /feedback/
    print("[2/9] Feedback Page")
    test_endpoint("feedback", "GET", "/feedback/")
    
    # 3. Test /reels/
    print("[3/9] Reels Page")
    test_endpoint("reels", "GET", "/reels/")
    
    # 4. Test /notifications/ (may require auth - check for redirect or 401)
    print("[4/9] Notifications Page")
    status, _, _ = test_endpoint("notifications", "GET", "/notifications/")
    
    # 5. Test /profile/@beta
    print("[5/9] Profile @beta")
    test_endpoint("profile-beta", "GET", "/profile/@beta")
    
    # 6. Test POST /reels/api/reels/view/batch
    print("[6/9] Reels View Batch API")
    status, _, elapsed = make_request("POST", "/reels/api/reels/view/batch", json={"views": []})
    if status in FAILED_STATUS_CODES:
        results["failed"].append({"endpoint": "reels-view-batch", "path": "/reels/api/reels/view/batch", "status": status, "response_time_ms": elapsed})
    else:
        results["passed"].append({"endpoint": "reels-view-batch", "path": "/reels/api/reels/view/batch", "status": status, "response_time_ms": elapsed})
        print(f"  Reels View Batch: PASSED (status={status}, {elapsed:.0f}ms)")
    
    # 7. Test GET /api/homepage/feed
    print("[7/9] Homepage Feed API")
    test_endpoint("homepage-feed", "GET", "/api/homepage/feed")
    
    # 8. Test static JS
    print("[8/9] Static JS Load")
    if js_status not in FAILED_STATUS_CODES:
        results["passed"].append({"endpoint": "static-js", "status": js_status, "response_time_ms": js_time})
        print(f"  Static JS: PASSED (status={js_status}, {js_time:.0f}ms)")
    else:
        results["failed"].append({"endpoint": "static-js", "status": js_status, "response_time_ms": js_time})
        print(f"  Static JS: FAILED (status={js_status})")
    
    # 9. Test static CSS
    print("[9/9] Static CSS Load")
    if css_status not in FAILED_STATUS_CODES:
        results["passed"].append({"endpoint": "static-css", "status": css_status, "response_time_ms": css_time})
        print(f"  Static CSS: PASSED (status={css_status}, {css_time:.0f}ms)")
    else:
        results["failed"].append({"endpoint": "static-css", "status": css_status, "response_time_ms": css_time})
        print(f"  Static CSS: FAILED (status={css_status})")
    
    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Passed:    {len(results['passed'])}")
    print(f"Failed:    {len(results['failed'])}")
    print(f"Warnings:  {len(results['warnings'])}")
    print(f"Degraded:  {results['degraded_mode']}")
    print()
    
    # Response times
    print("Response Times:")
    for endpoint, ms in sorted(results["response_times"].items(), key=lambda x: x[1], reverse=True):
        print(f"  {endpoint}: {ms:.0f}ms")
    
    # Failed endpoints
    if results["failed"]:
        print()
        print("FAILED ENDPOINTS:")
        for f in results["failed"]:
            print(f"  - {f['endpoint']}: status={f['status']}")
    
    # Status determination
    print()
    if results["failed"]:
        status_str = "FAIL"
    elif results["degraded_mode"] is True:
        status_str = "SAFE FOR TUNNEL TESTING (degraded)"
    else:
        status_str = "PASS"
    
    print(f"Status: {status_str}")
    print("=" * 60)
    
    return len(results["failed"]) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)