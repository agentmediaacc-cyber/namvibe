#!/usr/bin/env python3
"""
Phase 129 — Beta Health Monitor.
Checks all critical endpoints on localhost and namvibe.com.
Records timestamp, status, latency to JSONL log.
Accepts --loop (run every N seconds) and --interval (default 60).
"""

import os
import sys
import time
import json
import argparse
import ssl

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "beta_health_phase129.jsonl")
TIMEOUT = 15
HEADERS = {"User-Agent": "NamVibeHealthMonitor/phase129"}

ENDPOINTS = [
    "http://127.0.0.1:8080/",
    "http://127.0.0.1:8080/healthz",
    "http://127.0.0.1:8080/reels/",
    "http://127.0.0.1:8080/discover/",
    "http://127.0.0.1:8080/profile/",
    "https://namvibe.com/",
    "https://namvibe.com/healthz",
    "https://namvibe.com/reels/",
    "https://namvibe.com/discover/",
]


def check_url(url):
    started = time.perf_counter()
    status = -1
    error = None
    body = ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=True)
        status = r.status_code
        body = r.text[:50000]
    except requests.exceptions.SSLError as e:
        error = f"SSL: {e}"
    except requests.exceptions.ConnectionError as e:
        error = f"Connection: {e}"
    except requests.exceptions.Timeout:
        error = "timeout"
    except requests.exceptions.RequestException as e:
        error = str(e)
    except Exception as e:
        error = str(e)

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    return status, latency_ms, error, body


def check_build_marker(body):
    if not body:
        return None
    for marker in ("phase129", "phase128", "phase127"):
        if marker in body:
            return marker
    return None


def run_check():
    results = []
    for url in ENDPOINTS:
        status, latency_ms, error, body = check_url(url)
        marker = None
        if status == 200 and not error:
            marker = check_build_marker(body)

        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ts_epoch": time.time(),
            "url": url,
            "status": status,
            "latency_ms": latency_ms,
            "error": error,
            "build_marker": marker,
        }
        results.append(record)

        if status == 200 and not error:
            print(f"  [PASS] {url} — {status} — {latency_ms:.0f}ms" +
                  (f" [{marker}]" if marker else ""))
        elif error:
            print(f"  [FAIL] {url} — ERROR: {error}")
        else:
            print(f"  [WARN] {url} — {status} — {latency_ms:.0f}ms")

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["status"] == 200 and not r["error"])
    failed = sum(1 for r in results if r["error"])
    warned = total - passed - failed
    print(f"\n  Total: {total}, PASS: {passed}, WARN: {warned}, FAIL: {failed}")

    # Check build markers on homepage
    homepage_live = next(
        (r for r in results if r["url"] == "https://namvibe.com/"), None
    )
    if homepage_live and homepage_live["build_marker"]:
        print(f"  Build marker on namvibe.com: {homepage_live['build_marker']}")
    elif homepage_live and homepage_live["status"] == 200:
        print("  WARN: Homepage loaded but no phase127+ marker found")

    # Write JSONL
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        for record in results:
            f.write(json.dumps(record) + "\n")

    return failed


def main():
    parser = argparse.ArgumentParser(description="NamVibe Beta Health Monitor")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=60, help="Check interval seconds")
    args = parser.parse_args()

    if args.loop:
        print(f"Beta monitor starting — interval {args.interval}s (Ctrl+C to stop)")
        print(f"Logging to {LOG_FILE}")
        while True:
            print(f"\n--- {time.strftime('%Y-%m-%dT%H:%M:%S')} ---")
            try:
                run_check()
            except KeyboardInterrupt:
                print("\nMonitor stopped")
                break
            except Exception as e:
                print(f"  [ERROR] {e}")
            time.sleep(args.interval)
    else:
        run_check()

    return 0


if __name__ == "__main__":
    sys.exit(main())
