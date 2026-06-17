#!/usr/bin/env python3
"""Phase 63 — Master Audit Runner.

Runs all 6 audit scripts and compileall in sequence.
Returns PASS/FAIL per section.
"""

import os
import sys
import subprocess
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)

SCRIPTS = [
    ("Schema Verification", [sys.executable, "scripts/verify_phase63_real_schema.py"]),
    ("SQL Safety Audit", [sys.executable, "scripts/audit_phase63_sql_safety.py"]),
    ("CSRF Real Audit", [sys.executable, "scripts/audit_phase63_csrf_real.py"]),
    ("Homepage Performance Audit", [sys.executable, "scripts/audit_phase63_homepage_performance.py"]),
    ("Homepage Route Test", [sys.executable, "scripts/test_phase63_homepage_real_routes.py"]),
    ("Homepage UI Integrity", [sys.executable, "scripts/audit_phase63_homepage_ui_integrity.py"]),
    ("Compile Check", [sys.executable, "-m", "compileall", BASE]),
]


def run_script(name, cmd, timeout=120):
    """Run a script and return (passed, output)."""
    print(f"\n{'=' * 60}")
    print(f"RUNNING: {name}")
    print(f"{'=' * 60}")
    sys.stdout.flush()

    start = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = (time.perf_counter() - start)
        output = result.stdout + result.stderr
        passed = result.returncode == 0
        return passed, output, elapsed
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s", timeout
    except FileNotFoundError as e:
        return False, f"Script not found: {e}", 0


def main():
    print("=" * 60)
    print("           PHASE 63 — DEEP AUDIT RUNNER")
    print("=" * 60)
    print(f"Workspace: {BASE}")
    print(f"Python: {sys.executable}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    sys.stdout.flush()

    results = []

    for name, cmd in SCRIPTS:
        passed, output, elapsed = run_script(name, cmd)
        results.append((name, passed, output, elapsed))

    print(f"\n\n{'=' * 60}")
    print("                 FINAL REPORT")
    print(f"{'=' * 60}\n")

    all_pass = True
    for name, passed, output, elapsed in results:
        if passed:
            print(f"  [PASS] {name} ({elapsed:.1f}s)")
        else:
            print(f"  [FAIL] {name} ({elapsed:.1f}s)")
            all_pass = False
            # Print last 30 lines of output
            lines = output.strip().split("\n")
            tail = lines[-40:] if len(lines) > 40 else lines
            print(f"         Last {len(tail)} lines of output:")
            for line in tail:
                print(f"         {line}")

    print(f"\n{'=' * 60}")
    if all_pass:
        print("  OVERALL: ALL CHECKS PASSED")
    else:
        print(f"  OVERALL: SOME CHECKS FAILED")
    print(f"{'=' * 60}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
