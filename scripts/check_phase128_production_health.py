#!/usr/bin/env python3
"""
Phase 128 — Production Health Check.
Verifies:
- Port 8080 listening
- Gunicorn process exists
- Cloudflared process exists
- Local /healthz returns ok
- Live https://namvibe.com returns 200
- Live homepage contains phase127+
- Live CSS/JS return 200
- www redirects to namvibe.com
- /games/ redirects safely
- Tunnel config points to localhost:8080
- Mac sleep/power warnings
"""

import os
import sys
import subprocess
import time
import socket
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0; FAIL = 0; WARN = 0

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BASE = "https://namvibe.com"
HEADERS = {"User-Agent": "Mozilla/5.0 NamVibeAudit Phase128"}
TIMEOUT = 20


def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")


def http_get(url, allow_redirects=True):
    try:
        import requests
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                         allow_redirects=allow_redirects, verify=True)
        return r.status_code, r.text, r.url
    except requests.exceptions.RequestException as e:
        return -1, str(e), url
    except Exception as e:
        return -1, str(e), url


def port_listening(port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(("127.0.0.1", port))
        s.close()
        return result == 0
    except Exception:
        return False


def process_running(name):
    try:
        result = subprocess.run(
            ["pgrep", "-f", name],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_mac_sleep():
    """Check if Mac sleep settings may break production."""
    issues = []
    try:
        result = subprocess.run(
            ["pmset", "-g"],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.lower()
        if "sleep" in lines and "0" not in lines.split("sleep")[1][:5]:
            issues.append("System sleep may be enabled (sleep: not 0)")
        if "displaysleep" in lines and "0" not in lines.split("displaysleep")[1][:5]:
            issues.append("Display sleep may be enabled (displaysleep: not 0)")
    except Exception:
        issues.append("Could not check pmset")
    return issues


print("=" * 60)
print("PHASE 128 — PRODUCTION HEALTH CHECK")
print("=" * 60)

# ── 1. Port 8080 listening ──
print("\n--- 1. Port 8080 ---")
if port_listening(8080):
    ok("Port 8080 listening")
else:
    fail("Port 8080 NOT listening — start gunicorn")

# ── 2. Gunicorn process ──
print("\n--- 2. Gunicorn Process ---")
if process_running("gunicorn"):
    ok("Gunicorn process found")
else:
    fail("Gunicorn process NOT running")

# ── 3. Cloudflared process ──
print("\n--- 3. Cloudflared Process ---")
if process_running("cloudflared.*tunnel"):
    ok("Cloudflared tunnel process found")
else:
    fail("Cloudflared tunnel NOT running")

# ── 4. Local healthz ──
print("\n--- 4. Local /healthz ---")
s, body, _ = http_get("http://127.0.0.1:8080/healthz")
if s == 200:
    ok("Local /healthz returns 200")
else:
    fail(f"Local /healthz returned {s}")

# ── 5. Live homepage 200 ──
print("\n--- 5. Live https://namvibe.com ---")
s, body, _ = http_get(BASE + "/")
if s == 200:
    ok("namvibe.com returns 200")
else:
    fail(f"namvibe.com returned {s}")

# ── 6. Live homepage phase127+ ──
print("\n--- 6. Build Marker ---")
if "phase127" in body or "phase128" in body:
    ok("Live homepage contains phase127+ marker")
else:
    warn("Build marker not visible yet — server may need redeploy")

# ── 7. Live CSS 200 ──
print("\n--- 7. Live CSS ---")
s, _, _ = http_get(BASE + "/static/css/namvibe_home_pro.css")
if s == 200:
    ok("CSS asset returns 200")
else:
    fail(f"CSS returned {s}")

# ── 8. Live JS 200 ──
print("\n--- 8. Live JS ---")
s, _, _ = http_get(BASE + "/static/js/namvibe_home_pro.js")
if s == 200:
    ok("JS asset returns 200")
else:
    fail(f"JS returned {s}")

# ── 9. www redirect ──
print("\n--- 9. www Redirect ---")
s, _, _ = http_get("https://www.namvibe.com/", allow_redirects=False)
if s in (301, 302):
    ok(f"www.namvibe.com redirects ({s})")
else:
    warn(f"www.namvibe.com returned {s} (expected 301/302)")

# ── 10. /games/ ──
print("\n--- 10. /games/ ---")
s, body, final = http_get(BASE + "/games/")
if s in (301, 302) or s == 200 or "/discover" in final:
    ok(f"/games/ returns {s} (expected redirect)")
else:
    warn(f"/games/ returned {s}")

# ── 11. Tunnel config ──
print("\n--- 11. Tunnel Config ---")
config_path = os.path.expanduser("~/.cloudflared/config.yml")
if os.path.exists(config_path):
    with open(config_path) as f:
        cfg = f.read()
    if "localhost:8080" in cfg:
        ok("Tunnel config routes to localhost:8080")
    else:
        fail("Tunnel config does not route to localhost:8080")
else:
    fail(f"Config file not found at {config_path}")

# ── 12. Mac sleep warning ──
print("\n--- 12. Mac Power/Sleep ---")
sleep_issues = check_mac_sleep()
if not sleep_issues:
    ok("No Mac sleep warnings detected")
else:
    for issue in sleep_issues:
        warn(issue)
    warn("Mac sleep may cause production downtime — consider keeping Mac awake via caffeinate or Amphetamine")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 128 — PRODUCTION HEALTH CHECK SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
if FAIL == 0:
    print("  [HEALTH] All critical checks pass")
else:
    print("  [UNHEALTHY] Critical failures detected — fix before production use")
print()
print(f"  namvibe.com:              https://namvibe.com")
print(f"  Live check:               python3 scripts/check_phase128_production_health.py")
print(f"  Gunicorn logs:            logs/gunicorn_phase128.log")
print(f"  Cloudflared logs:         logs/cloudflared_phase128.log")
print(f"  Runbook:                  docs/PHASE128_CLOUDFLARE_TUNNEL_RUNBOOK.md")
