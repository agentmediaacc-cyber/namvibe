#!/usr/bin/env python3
"""
Phase 128 — Reliability Audit.
Checks Cloudflare tunnel config, start scripts, health checks, plists, runbook,
and ensures no credentials are leaked.
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
    full = os.path.join(ROOT, path) if not path.startswith("/") and not path.startswith("~") else os.path.expanduser(path)
    if not os.path.exists(full):
        return None
    with open(full, encoding="utf-8", errors="ignore") as f:
        return f.read()


def file_exists(path):
    full = os.path.join(ROOT, path) if not path.startswith("/") and not path.startswith("~") else os.path.expanduser(path)
    return os.path.exists(full)


CONFIG = os.path.expanduser("~/.cloudflared/config.yml")


print("=" * 60)
print("PHASE 128 — RELIABILITY AUDIT")
print("=" * 60)

# ── 1. Config.yml exists ──
print("\n--- 1. Tunnel Config Exists ---")
if file_exists(CONFIG):
    ok("config.yml exists at ~/.cloudflared/config.yml")
else:
    fail("config.yml not found — tunnel cannot run")

config_text = read_file(CONFIG) if os.path.exists(CONFIG) else ""

# ── 2. Config has namvibe.com ──
print("\n--- 2. namvibe.com in Config ---")
if "namvibe.com" in config_text:
    ok("config.yml contains namvibe.com")
else:
    fail("config.yml does not reference namvibe.com")

# ── 3. Config has www.namvibe.com ──
print("\n--- 3. www.namvibe.com in Config ---")
if "www.namvibe.com" in config_text:
    ok("config.yml contains www.namvibe.com")
else:
    warn("config.yml does not reference www.namvibe.com")

# ── 4. Config uses localhost:8080 ──
print("\n--- 4. localhost:8080 in Config ---")
if "localhost:8080" in config_text:
    ok("config.yml routes to localhost:8080")
else:
    fail("config.yml does not route to localhost:8080")

# ── 5. Start scripts exist ──
print("\n--- 5. Start Scripts ---")
expected_scripts = [
    "scripts/start_phase128_production_local.py",
    "scripts/start_phase128_tunnel.py",
]
for s in expected_scripts:
    if file_exists(s):
        ok(f"{s} exists")
    else:
        fail(f"{s} missing")

# ── 6. Health script exists ──
print("\n--- 6. Health Script ---")
if file_exists("scripts/check_phase128_production_health.py"):
    ok("check_phase128_production_health.py exists")
else:
    fail("Health script missing")

# ── 7. Plist templates exist ──
print("\n--- 7. Plist Templates ---")
expected_plists = [
    "ops/macos/com.namvibe.gunicorn.plist",
    "ops/macos/com.namvibe.cloudflared.plist",
]
for p in expected_plists:
    if file_exists(p):
        ok(f"{p} exists")
    else:
        fail(f"{p} missing")

# ── 8. Runbook exists ──
print("\n--- 8. Runbook ---")
if file_exists("docs/PHASE128_CLOUDFLARE_TUNNEL_RUNBOOK.md"):
    ok("Runbook exists")
else:
    fail("Runbook missing")

# ── 9. Gunicorn command uses port 8080 ──
print("\n--- 9. Gunicorn Port 8080 ---")
start_text = read_file("scripts/start_phase128_production_local.py")
if start_text and "8080" in start_text:
    ok("Start script uses port 8080")
else:
    fail("Start script does not use port 8080")

# ── 10. Gunicorn uses websocket worker ──
print("\n--- 10. WebSocket Worker ---")
if start_text and "GeventWebSocketWorker" in start_text:
    ok("Start script uses GeventWebSocketWorker")
else:
    fail("Start script missing WebSocket worker class")

# ── 11. Logs directory handled ──
print("\n--- 11. Logs Directory ---")
if os.path.isdir(os.path.join(ROOT, "logs")):
    ok("logs/ directory exists")
else:
    warn("logs/ directory missing (will be created on first run)")

# ── 12. No secrets printed from cloudflared credentials ──
print("\n--- 12. Credentials Not Exposed ---")
credential_patterns = [
    r'credentials-file["\':\s]+/',
    r'os\.popen.*cloudflared.*token',
    r'8f008f0f-9d5e-4b7f-b67e-08e0f1c83921\.json',
]
all_scripts = []
for s in ["scripts/start_phase128_tunnel.py", "scripts/start_phase128_production_local.py",
           "scripts/check_phase128_production_health.py", "scripts/audit_phase128_reliability.py"]:
    t = read_file(s)
    if t:
        all_scripts.append((s, t))

exposed = False
for fname, text in all_scripts:
    for pat in credential_patterns:
        if re.search(pat, text):
            warn(f"Credential exposure risk in {fname}: matches '{pat}'")
            exposed = True
if not exposed:
    ok("No credential exposure in scripts")

# ── 13. Plist does not embed credential content ──
print("\n--- 13. Plist Credential Safety ---")
for pname in expected_plists:
    text = read_file(pname)
    if text and '.json' in text:
        warn(f"{pname} references .json file — ensure it's not credentials")
    else:
        ok(f"{pname} does not embed credentials")

# ── 14. Health script does not start services ──
print("\n--- 14. Health Script Doesn't Start Services ---")
health_text = read_file("scripts/check_phase128_production_health.py")
if health_text and "subprocess.Popen" not in health_text and "Popen" not in health_text:
    ok("Health script reads-only (does not start processes)")
else:
    warn("Health script may start processes — verify read-only intent")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 128 — RELIABILITY AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"\n  RESULT: {'READY' if FAIL == 0 else 'BLOCKERS PRESENT'}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
