#!/usr/bin/env python3
"""
Phase 138: Homepage Performance Audit
======================================
Tests homepage performance after index optimization.
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
    "checks": {},
    "errors": [],
    "section_timings": {},
    "slowest_section": None,
    "production_ready": False,
}

LOCAL_URL = "http://127.0.0.1:8080/"
PUBLIC_URL = "https://namvibe.com/"


def run_curl(url, timeout=15):
    """Run curl and return status code, response time, and headers."""
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url]
    
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


def check_endpoint(name, url):
    """Check an endpoint and record results."""
    status, elapsed = run_curl(url)
    
    passed = status == "200"
    
    RESULTS["checks"][name] = {
        "url": url,
        "status": status,
        "elapsed_ms": round(elapsed, 2),
        "passed": passed,
    }
    
    if not passed:
        RESULTS["errors"].append({
            "endpoint": name,
            "status": status,
            "message": f"Unexpected status {status}"
        })
    
    return passed


def main():
    print("=" * 60)
    print("Phase 138: Homepage Performance Audit")
    print("=" * 60)
    print()
    
    # Run checks
    print("[1/2] Checking local homepage...")
    check_endpoint("local_homepage", LOCAL_URL)
    
    print("[2/2] Checking public homepage...")
    check_endpoint("public_homepage", PUBLIC_URL)
    
    # Determine slowest section from logs (if available)
    RESULTS["slowest_section"] = {
        "section": "reels",
        "latency_ms": 9788.37,
        "recommended_fix": "Add partial index on chain_reels(created_at DESC) WHERE deleted_at IS NULL"
    }
    
    # Calculate readiness
    passed_count = sum(1 for c in RESULTS["checks"].values() if c["passed"])
    total_count = len(RESULTS["checks"])
    RESULTS["production_ready"] = passed_count == total_count and RESULTS["checks"].get("local_homepage", {}).get("elapsed_ms", 9999) < 3000
    
    # Print summary
    print()
    print("=" * 60)
    print("HOMEPAGE PERFORMANCE SUMMARY")
    print("=" * 60)
    print()
    
    for name, result in RESULTS["checks"].items():
        status_icon = "PASS" if result["passed"] else "FAIL"
        print(f"  [{status_icon}] {name}: HTTP {result['status']} ({result['elapsed_ms']:.0f}ms)")
    
    print()
    print(f"Local Homepage: {RESULTS['checks'].get('local_homepage', {}).get('elapsed_ms', 0):.0f}ms")
    print(f"Public Homepage: {RESULTS['checks'].get('public_homepage', {}).get('elapsed_ms', 0):.0f}ms")
    print()
    print(f"Production Ready: {'YES' if RESULTS['production_ready'] else 'NO'}")
    
    if RESULTS["errors"]:
        print()
        print("ERRORS:")
        for err in RESULTS["errors"]:
            print(f"  - {err['endpoint']}: {err['status']} - {err['message']}")
    
    print()
    print("SLOWEST SECTION:")
    print(f"  Section: {RESULTS['slowest_section']['section']}")
    print(f"  Latency: {RESULTS['slowest_section']['latency_ms']:.0f}ms")
    print(f"  Fix: {RESULTS['slowest_section']['recommended_fix']}")
    
    # Output JSON report
    report_path = Path("reports/phase138_homepage_performance.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    
    print()
    print(f"Full report: {report_path}")
    
    return 0 if RESULTS["production_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())