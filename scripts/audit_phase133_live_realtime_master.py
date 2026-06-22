#!/usr/bin/env python3
"""Phase 133 - Master live realtime audit runner."""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    "scripts/test_phase133_messaging_reality.py",
    "scripts/test_phase133_voice_notes_reality.py",
    "scripts/test_phase133_calls_reality.py",
    "scripts/test_phase133_realtime_socket_reality.py",
    "scripts/test_phase133_browser_reality.py",
    "scripts/audit_phase133_production_realtime.py",
    "scripts/test_phase133_live_user_flow_optional.py",
]

total_pass = 0
total_fail = 0
total_warn = 0

print("=" * 60)
print("PHASE 133 - LIVE REALTIME MASTER AUDIT")
print("=" * 60)

for script in SCRIPTS:
    print(f"\n--- Running {script} ---")
    proc = subprocess.run([sys.executable, script], cwd=ROOT, capture_output=True, text=True, timeout=180)
    output = proc.stdout + proc.stderr
    print(output)
    matches = re.findall(r"PASS:\s*(\d+)\s+FAIL:\s*(\d+)\s+WARN:\s*(\d+)", output)
    if matches:
        p, f, w = map(int, matches[-1])
        total_pass += p
        total_fail += f
        total_warn += w
    else:
        total_fail += 1
        print(f"  [FAIL] {script} did not print a parseable summary")
    if proc.returncode != 0:
        total_fail += 1
        print(f"  [FAIL] {script} exited with {proc.returncode}")

print(f"\n{'=' * 60}")
print("PHASE 133 - LIVE REALTIME MASTER AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {total_pass}  FAIL: {total_fail}  WARN: {total_warn}")
print(f"  safe_to_commit: {'YES' if total_fail == 0 else 'NO'}")

