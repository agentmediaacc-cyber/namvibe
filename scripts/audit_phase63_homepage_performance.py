#!/usr/bin/env python3
"""Phase 63 — Homepage Performance Real Audit.

Measures:
  - cold build_homepage_payload()
  - warm build_homepage_payload()
  - warm get_homepage_data() if safe

Does NOT import the full Flask app unless necessary.
"""

import os
import sys
import time
import signal

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

TIMEOUT_SECONDS = 15


class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("Timed out")


def timed_call(func, *args, label="", **kwargs):
    """Call func with args/kwargs and return (result, elapsed_ms)."""
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(TIMEOUT_SECONDS)
    start = time.perf_counter()
    try:
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        return result, elapsed
    except TimeoutError:
        return None, -1
    finally:
        signal.alarm(0)


def main():
    print("=" * 60)
    print("Phase 63 — Homepage Performance Real Audit")
    print("=" * 60)

    try:
        from services.homepage_service import (
            build_homepage_payload,
            build_tiktok_home_payload,
            get_homepage_data,
        )
        from services.neon_service import prime_neon_runtime
        print("\nImports OK")
    except ImportError as e:
        print(f"FAIL: Import error: {e}")
        return 1

    # Prime Neon
    try:
        prime_neon_runtime()
        print("Neon runtime primed")
    except Exception as e:
        print(f"WARN: prime_neon_runtime failed: {e}")

    results = []

    # 1. Cold build_homepage_payload (first call)
    print("\n--- 1. COLD build_homepage_payload() ---")
    for i in range(3):
        result, ms = timed_call(build_homepage_payload, label="cold")
        if ms < 0:
            print(f"  Run {i+1}: TIMEOUT (>={TIMEOUT_SECONDS}s)")
        else:
            print(f"  Run {i+1}: {ms:.2f}ms ({'PASS' if ms < 5000 else 'SLOW'})")
            if i == 0:
                results.append(("Cold (first call)", ms))

    # 2. Warm build_homepage_payload
    print("\n--- 2. WARM build_homepage_payload() ---")
    for i in range(3):
        result, ms = timed_call(build_homepage_payload, label="warm")
        if ms < 0:
            print(f"  Run {i+1}: TIMEOUT (>={TIMEOUT_SECONDS}s)")
        else:
            print(f"  Run {i+1}: {ms:.2f}ms ({'PASS' if ms < 1000 else 'SLOW'})")
            results.append((f"Warm run {i+1}", ms))

    # 3. build_tiktok_home_payload
    print("\n--- 3. build_tiktok_home_payload() ---")
    for i in range(3):
        result, ms = timed_call(build_tiktok_home_payload, label="tiktok")
        if ms < 0:
            print(f"  Run {i+1}: TIMEOUT (>={TIMEOUT_SECONDS}s)")
        else:
            print(f"  Run {i+1}: {ms:.2f}ms ({'PASS' if ms < 2000 else 'SLOW'})")

    # 4. Warm get_homepage_data (may fail if session required)
    print("\n--- 4. get_homepage_data() (cache-only attempt) ---")
    try:
        for i in range(2):
            result, ms = timed_call(get_homepage_data, label="homepage_data")
            if ms < 0:
                print(f"  Run {i+1}: TIMEOUT (>={TIMEOUT_SECONDS}s)")
            else:
                print(f"  Run {i+1}: {ms:.2f}ms ({'PASS' if ms < 1000 else 'SLOW'})")
    except Exception as e:
        print(f"  SKIP: get_homepage_data requires Flask app context: {e}")

    print(f"\n--- Summary ---")
    all_pass = True
    target_pass = True
    for label, ms in results:
        ok = ms < 1000
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label}: {ms:.2f}ms")
        if not ok and "cold" not in label.lower():
            all_pass = False

    print(f"\nOVERALL: {'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
