#!/usr/bin/env python3
"""
Phase 137: Real Domain Smoke Test
==================================
Tests the public Cloudflare domain paths after tunnel is established.
"""

import os
import sys
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

RESULTS = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "base_url": "https://namvibe.com",
    "checks": {},
    "errors": [],
    "production_ready": False,
}

DOMAIN = "https://namvibe.com"


def run_curl(url, method="GET", data=None, timeout=10):
    """Run curl and return status code, response time, and body."""
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-X", method]
    if data:
        cmd.extend(["-H", "Content-Type: application/json", "-d", data])
    cmd.append(url)
    
    start = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        elapsed = (time.time() - start) * 1000
        status = result.stdout.strip()
        return status, elapsed
    except subprocess.TimeoutExpired:
        return "timeout", timeout * 1000
    except Exception as e:
        return "error", 0


def is_pass_status(status):
    """Check if status code is acceptable."""
    return status in ["200", "302", "401", "403"]


def check_endpoint(path, name, method="GET", data=None):
    """Check an endpoint and record results."""
    url = f"{DOMAIN}{path}"
    status, elapsed = run_curl(url, method, data)
    
    passed = is_pass_status(status)
    
    RESULTS["checks"][name] = {
        "url": url,
        "status": status,
        "elapsed_ms": round(elapsed, 2),
        "passed": passed,
    }
    
    if not passed:
        RESULTS["errors"].append({
            "endpoint": path,
            "status": status,
            "message": f"Unexpected status {status}"
        })
    
    return passed


def main():
    print("=" * 60)
    print("Phase 137: Real Domain Smoke Test")
    print("=" * 60)
    print()
    
    # Run all checks
    print("[1/7] Checking /healthz...")
    check_endpoint("/healthz", "healthz")
    
    print("[2/7] Checking /...")
    check_endpoint("/", "homepage")
    
    print("[3/7] Checking /feedback/...")
    check_endpoint("/feedback/", "feedback")
    
    print("[4/7] Checking /notifications/...")
    check_endpoint("/notifications/", "notifications")
    
    print("[5/7] Checking /profile/@beta...")
    check_endpoint("/profile/@beta", "profile_beta")
    
    print("[6/7] Checking /reels/...")
    check_endpoint("/reels/", "reels")
    
    print("[7/7] Checking POST /reels/api/reels/view/batch...")
    check_endpoint("/reels/api/reels/view/batch", "reels_view_batch", method="POST", data='{"views":[]}')
    
    # Calculate readiness
    passed_count = sum(1 for c in RESULTS["checks"].values() if c["passed"])
    total_count = len(RESULTS["checks"])
    RESULTS["production_ready"] = passed_count == total_count
    
    # Print summary
    print()
    print("=" * 60)
    print("SMOKE TEST SUMMARY")
    print("=" * 60)
    print()
    
    for name, result in RESULTS["checks"].items():
        status_icon = "PASS" if result["passed"] else "FAIL"
        print(f"  [{status_icon}] {name}: HTTP {result['status']} ({result['elapsed_ms']:.0f}ms)")
    
    print()
    print(f"Endpoints Passed: {passed_count}/{total_count}")
    print(f"Production Ready: {'YES' if RESULTS['production_ready'] else 'NO'}")
    
    if RESULTS["errors"]:
        print()
        print("ERRORS:")
        for err in RESULTS["errors"]:
            print(f"  - {err['endpoint']}: {err['status']} - {err['message']}")
    
    # Output JSON report
    report_path = Path("reports/phase137_real_domain_smoke.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    
    print()
    print(f"Full report: {report_path}")
    
    return 0 if RESULTS["production_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())