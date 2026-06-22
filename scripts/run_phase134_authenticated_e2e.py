#!/usr/bin/env python3
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    "scripts/test_phase134_disposable_accounts.py",
    "scripts/setup_phase134_test_thread.py",
    "scripts/test_phase134_authenticated_messaging_flow.py",
    "scripts/test_phase134_authenticated_media_flow.py",
    "scripts/test_phase134_authenticated_voice_note_flow.py",
    "scripts/test_phase134_authenticated_call_flow.py",
    "scripts/test_phase134_authenticated_notification_flow.py",
    "scripts/test_phase134_authenticated_group_flow.py",
    "scripts/cleanup_phase134_test_data.py",
]

print("=" * 60)
print("PHASE 134 - AUTHENTICATED E2E MASTER RUNNER")
print("=" * 60)

total_pass = total_fail = total_warn = 0
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
print("PHASE 134 - AUTHENTICATED E2E MASTER RUNNER SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {total_pass}  FAIL: {total_fail}  WARN: {total_warn}")
print(f"  safe_to_commit: {'YES' if total_fail == 0 else 'NO'}")

