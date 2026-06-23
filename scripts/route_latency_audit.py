#!/usr/bin/env python3
"""
Performance audit script for Cloudflare tunnel optimization.
Measures route latency and identifies slow queries.

Usage: python scripts/route_latency_audit.py
"""

import os
import sys
import time
import json
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set testing mode before imports
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from flask import Flask
from app import create_app

app = create_app()

def measure_route(route_path, iterations=3):
    """Measure average latency for a route."""
    latencies = []
    
    with app.test_client() as client:
        for i in range(iterations):
            start = time.perf_counter()
            try:
                response = client.get(route_path)
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append({
                    "iteration": i + 1,
                    "latency_ms": round(elapsed, 2),
                    "status_code": response.status_code
                })
            except Exception as e:
                latencies.append({
                    "iteration": i + 1,
                    "error": str(e)
                })
    
    if latencies:
        avg = sum(l["latency_ms"] for l in latencies if "latency_ms" in l) / len([l for l in latencies if "latency_ms" in l])
        return {
            "route": route_path,
            "avg_latency_ms": round(avg, 2),
            "iterations": iterations,
            "samples": latencies
        }
    return {"route": route_path, "error": "All iterations failed"}


def run_audit():
    """Run latency audit on all monitored routes."""
    routes = [
        "/profile/@beta",
        "/contacts/",
        "/discover/",
        "/messages/?thread=test",
        "/api/notifications/unread-count",
        "/healthz",
        "/health/redis",
    ]
    
    results = []
    for route in routes:
        result = measure_route(route)
        results.append(result)
        print(f"[{datetime.now(timezone.utc).isoformat()}] {route} -> {result.get('avg_latency_ms', 'N/A')}ms")
    
    # Summary
    valid_results = [r for r in results if "avg_latency_ms" in r]
    if valid_results:
        overall_avg = sum(r["avg_latency_ms"] for r in valid_results) / len(valid_results)
        print(f"\n=== AUDIT SUMMARY ===")
        print(f"Routes tested: {len(results)}")
        print(f"Average latency: {round(overall_avg, 2)}ms")
        print(f"Slow routes (>100ms): {[r['route'] for r in valid_results if r['avg_latency_ms'] > 100]}")
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results
    }


if __name__ == "__main__":
    audit_result = run_audit()
    
    # Write results to file
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audit_results.json")
    with open(output_path, "w") as f:
        json.dump(audit_result, f, indent=2)
    print(f"\nResults written to: {output_path}")