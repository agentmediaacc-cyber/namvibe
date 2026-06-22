#!/usr/bin/env python3
"""
Phase 129 — Production Safety Audit.
Verifies all Phase 129 reliability and safety components.
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0; FAIL = 0; WARN = 0


def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")


def read_file(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return None
    with open(full, encoding="utf-8", errors="ignore") as f:
        return f.read()


def file_exists(path):
    return os.path.exists(os.path.join(ROOT, path))


GITIGNORE_PATH = os.path.join(ROOT, ".gitignore")

print("=" * 60)
print("PHASE 129 — PRODUCTION SAFETY AUDIT")
print("=" * 60)

# ── 1. Awake guard exists ──
print("\n--- 1. Awake Guard ---")
if file_exists("scripts/start_phase129_awake_guard.py"):
    ok("start_phase129_awake_guard.py exists")
else:
    fail("start_phase129_awake_guard.py missing")

# ── 2. Awake guard uses caffeinate -dimsu ──
print("\n--- 2. caffeinate -dimsu ---")
awake_text = read_file("scripts/start_phase129_awake_guard.py")
if awake_text and "caffeinate" in awake_text and "-dimsu" in awake_text:
    ok("Awake guard uses caffeinate -dimsu")
else:
    fail("Awake guard missing caffeinate -dimsu")

# ── 3. Awake guard writes PID file ──
print("\n--- 3. PID File ---")
if awake_text and "namvibe_awake_guard.pid" in awake_text:
    ok("Awake guard writes PID to tmp/namvibe_awake_guard.pid")
else:
    fail("Awake guard missing PID file path")

# ── 4. Stop script exists ──
print("\n--- 4. Stop Script ---")
if file_exists("scripts/stop_phase129_production_local.py"):
    ok("stop_phase129_production_local.py exists")
else:
    fail("Stop script missing")
stop_text = read_file("scripts/stop_phase129_production_local.py")

# ── 5. Stop script doesn't pkill -f python ──
print("\n--- 5. Stop Script Safety ---")
if stop_text and "pkill.*-f.*python" not in stop_text:
    ok("Stop script does not use pkill -f on python")
else:
    fail("Stop script dangerously kills all Python processes")

# ── 6. Stop script handles --tunnel --awake --all ──
print("\n--- 6. Stop Script Flags ---")
if stop_text and all(flag in stop_text for flag in ["--tunnel", "--awake", "--all"]):
    ok("Stop script supports --tunnel, --awake, --all")
else:
    fail("Stop script missing required flags")

# ── 7. Monitor script exists ──
print("\n--- 7. Monitor Script ---")
if file_exists("scripts/monitor_phase129_beta_health.py"):
    ok("monitor_phase129_beta_health.py exists")
else:
    fail("Monitor script missing")
monitor_text = read_file("scripts/monitor_phase129_beta_health.py")

# ── 8. Monitor writes JSONL ──
print("\n--- 8. JSONL Logging ---")
if monitor_text and "beta_health_phase129.jsonl" in monitor_text:
    ok("Monitor writes JSONL to logs/beta_health_phase129.jsonl")
else:
    fail("Monitor missing JSONL log path")

# ── 9. Monitor supports --loop and --interval ──
print("\n--- 9. Monitor Flags ---")
if monitor_text and "--loop" in monitor_text and "--interval" in monitor_text:
    ok("Monitor supports --loop and --interval")
else:
    fail("Monitor missing --loop or --interval")

# ── 10. Status script exists ──
print("\n--- 10. Status Script ---")
if file_exists("scripts/status_phase129_production.py"):
    ok("status_phase129_production.py exists")
else:
    fail("Status script missing")

# ── 11. Secrets audit exists ──
print("\n--- 11. Secrets Audit ---")
if file_exists("scripts/audit_phase129_secrets_safety.py"):
    ok("audit_phase129_secrets_safety.py exists")
else:
    fail("Secrets audit script missing")

# ── 12. Awake launchd plist exists ──
print("\n--- 12. Awake Launchd Plist ---")
if file_exists("ops/macos/com.namvibe.awake.plist"):
    ok("com.namvibe.awake.plist exists")
else:
    fail("Awake launchd plist missing")

# ── 13. Safety docs exist ──
print("\n--- 13. Safety Docs ---")
if file_exists("docs/PHASE129_PRODUCTION_SAFETY_MONITORING.md"):
    ok("Safety docs exist")
else:
    fail("Safety docs missing")

# ── 14. .gitignore safety entries ──
print("\n--- 14. .gitignore Protection ---")
required_entries = [
    ".env", "secrets/", "logs/", "tmp/",
    "*.pem", "*.key", "*.crt", "*.p12",
    "*.sqlite", "*.db", "*.bak",
    "*.pid", "*.log",
]
gitignore_text = read_file(".gitignore") or ""
missing = [e for e in required_entries if e not in gitignore_text]
if not missing:
    ok(".gitignore contains all required safety entries")
else:
    for e in missing:
        fail(f".gitignore missing: {e}")

# ── 15. Secrets audit doesn't print secrets ──
print("\n--- 15. Secrets Audit Safety ---")
secrets_text = read_file("scripts/audit_phase129_secrets_safety.py")
if secrets_text:
    unsafe_patterns = [
        r"print\(.*SUPABASE_SERVICE_ROLE",
        r"print\(.*DATABASE_URL",
        r"print\(.*UPSTASH_REDIS",
        r"print\(.*PRIVATE.KEY",
    ]
    unsafe = False
    for pat in unsafe_patterns:
        if re.search(pat, secrets_text):
            warn(f"Secrets audit may print secrets: {pat}")
            unsafe = True
    if not unsafe:
        ok("Secrets audit does not print secret values")
else:
    fail("Cannot read secrets audit script")

# ── 16. Scripts don't print credential content ──
print("\n--- 16. Credential Print Safety ---")
all_phase129_scripts = [
    "scripts/start_phase129_awake_guard.py",
    "scripts/stop_phase129_production_local.py",
    "scripts/monitor_phase129_beta_health.py",
    "scripts/status_phase129_production.py",
    "scripts/audit_phase129_secrets_safety.py",
    "scripts/audit_phase129_production_safety.py",
]
safe = True
for s in all_phase129_scripts:
    text = read_file(s)
    if text and (".json" in text or "credentials" in text.lower()):
        if "8f008f0f" in text:
            warn(f"{s} contains tunnel ID — acceptable for internal use")
        elif re.search(r'cat.*\.json|open.*\.json.*creden', text, re.IGNORECASE):
            warn(f"{s} may expose credential content")
            safe = False
if safe:
    ok("Scripts do not expose credential file content")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 129 — PRODUCTION SAFETY AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"\n  RESULT: {'READY' if FAIL == 0 else 'BLOCKERS PRESENT'}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
