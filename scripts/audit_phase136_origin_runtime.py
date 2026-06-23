#!/usr/bin/env python3
"""
Phase 136: Origin Runtime Audit Script
======================================
Verifies the origin server is stable after startup:
- Port 8080 listening
- Gunicorn process alive
- Healthz returns 200
- Key routes respond
- No worker boot failures
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

RESULTS = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "checks": {},
    "errors": [],
    "warnings": [],
    "recommendations": [],
    "production_ready": False,
}


def run_command(cmd, timeout=10):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1
    except Exception as e:
        return "", str(e), 1


def check_port_listening():
    """Check if port 8080 is listening."""
    stdout, stderr, code = run_command("lsof -i :8080 2>/dev/null || ss -tlnp 2>/dev/null | grep 8080 || netstat -tlnp 2>/dev/null | grep 8080")
    is_listening = bool(stdout.strip())
    RESULTS["checks"]["port_listening"] = {
        "status": "PASS" if is_listening else "FAIL",
        "details": stdout or "Port 8080 not listening",
    }
    if not is_listening:
        RESULTS["errors"].append({
            "source": "Port binding",
            "file": "gunicorn.conf.py",
            "line": 10,
            "message": "Port 8080 is not bound - application not listening",
        })
    return is_listening


def check_gunicorn_alive():
    """Check if Gunicorn process is running."""
    stdout, stderr, code = run_command("ps aux | grep gunicorn | grep -v grep")
    is_alive = bool(stdout.strip())
    RESULTS["checks"]["gunicorn_alive"] = {
        "status": "PASS" if is_alive else "FAIL",
        "details": stdout or "No gunicorn process found",
    }
    if not is_alive:
        RESULTS["errors"].append({
            "source": "Gunicorn process",
            "file": None,
            "line": None,
            "message": "Gunicorn process is not running",
        })
    return is_alive


def check_healthz():
    """Check if /healthz returns 200."""
    stdout, stderr, code = run_command("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/healthz 2>&1")
    is_ok = stdout.strip() == "200"
    RESULTS["checks"]["healthz_200"] = {
        "status": "PASS" if is_ok else "FAIL",
        "details": f"HTTP {stdout}" if stdout else stderr or "No response",
    }
    if not is_ok:
        RESULTS["errors"].append({
            "source": "Healthz endpoint",
            "file": "app.py",
            "line": 942,
            "message": f"Healthz returned {stdout or 'no response'}",
        })
    return is_ok


def check_route(path, name):
    """Check if a route returns 200 or 302."""
    stdout, stderr, code = run_command(f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:8080{path} 2>&1")
    status = stdout.strip()
    is_ok = status in ["200", "302"]
    RESULTS["checks"][f"route_{name}"] = {
        "status": "PASS" if is_ok else "FAIL",
        "details": f"HTTP {status}",
    }
    if not is_ok:
        RESULTS["errors"].append({
            "source": f"Route {name}",
            "file": None,
            "line": None,
            "message": f"Route {path} returned HTTP {status}",
        })
    return is_ok


def check_profile_route():
    """Check /profile/@beta returns 200, 302, or 404 (not connection refused)."""
    stdout, stderr, code = run_command("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/profile/@beta 2>&1")
    status = stdout.strip()
    is_ok = status in ["200", "302", "404"]
    RESULTS["checks"]["profile_beta"] = {
        "status": "PASS" if is_ok else "FAIL",
        "details": f"HTTP {status}",
    }
    if not is_ok:
        RESULTS["errors"].append({
            "source": "Profile route",
            "file": None,
            "line": None,
            "message": f"Route /profile/@beta returned HTTP {status} (expected 200/302/404)",
        })
    return is_ok


def check_worker_boot():
    """Check for worker boot failures in error log."""
    error_log = Path("logs/gunicorn_error.log")
    if not error_log.exists():
        RESULTS["checks"]["worker_boot"] = {"status": "PASS", "details": "No error log found"}
        return True
    
    content = error_log.read_text()
    has_failure = "Worker bootstrapping" in content and "ERROR" in content
    has_exit = "Worker exiting" in content
    
    RESULTS["checks"]["worker_boot"] = {
        "status": "PASS" if not has_failure else "FAIL",
        "details": "Worker boot failures detected" if has_failure else "No boot failures",
    }
    
    if has_failure:
        RESULTS["errors"].append({
            "source": "Worker boot",
            "file": "gunicorn.conf.py",
            "line": None,
            "message": "Worker bootstrapping failed - check error log",
        })
    return not has_failure


def calculate_score():
    """Calculate production readiness score."""
    score = 100
    for check in RESULTS["checks"].values():
        if check["status"] == "FAIL":
            score -= 20
        elif check["status"] == "WARN":
            score -= 10
    for err in RESULTS["errors"]:
        score -= 5
    for warn in RESULTS["warnings"]:
        score -= 3
    RESULTS["production_ready"] = score >= 80
    return max(0, min(100, score))


def main():
    print("=" * 60)
    print("Phase 136: Origin Runtime Audit")
    print("=" * 60)
    print()
    
    # Run all checks
    print("[1/7] Checking port 8080 listening...")
    check_port_listening()
    
    print("[2/7] Checking Gunicorn process...")
    check_gunicorn_alive()
    
    print("[3/7] Checking /healthz endpoint...")
    check_healthz()
    
    print("[4/7] Checking key routes...")
    check_route("/", "homepage")
    check_route("/feedback/", "feedback")
    check_route("/notifications/", "notifications")
    
    print("[5/7] Checking /profile/@beta...")
    check_profile_route()
    
    print("[6/7] Checking worker boot status...")
    check_worker_boot()
    
    print("[7/7] Calculating readiness score...")
    score = calculate_score()
    
    # Print summary
    print()
    print("=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    
    for check_name, result in RESULTS["checks"].items():
        status_icon = "PASS" if result["status"] == "PASS" else "FAIL" if result["status"] == "FAIL" else "WARN"
        print(f"  [{status_icon}] {check_name}: {result['status']}")
    
    print()
    print(f"Production Readiness Score: {score}/100")
    print(f"Production Ready: {'YES' if RESULTS['production_ready'] else 'NO'}")
    
    if RESULTS["errors"]:
        print()
        print("ERRORS:")
        for err in RESULTS["errors"]:
            print(f"  - [{err['source']}] {err['message']}")
    
    # Output JSON report
    report_path = Path("reports/phase136_origin_runtime_audit.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    
    print()
    print(f"Full report written to: {report_path}")
    
    return score


if __name__ == "__main__":
    score = main()
    sys.exit(0 if score >= 80 else 1)