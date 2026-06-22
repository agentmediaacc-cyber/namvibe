#!/usr/bin/env python3
"""
Phase 129 — Production Status Report.
Shows git state, running processes, health status, and recent monitor logs.
"""

import os
import sys
import subprocess
import time
import socket
import json
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONITOR_LOG = os.path.join(ROOT, "logs", "beta_health_phase129.jsonl")
HEADERS = {"User-Agent": "NamVibeStatus/phase129"}


def log(label, value, status="ok"):
    icon = {"ok": "✓", "warn": "!", "fail": "✗"}.get(status, "?")
    print(f"  {icon} {label}: {value}")


def process_running(pattern):
    try:
        r = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def port_listening(port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(("127.0.0.1", port))
        s.close()
        return result == 0
    except Exception:
        return False


def http_get(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, verify=True)
        return r.status_code, r.text[:2000]
    except requests.exceptions.RequestException as e:
        return -1, str(e)
    except Exception as e:
        return -1, str(e)


def get_git_info():
    info = {"branch": "?", "commit": "?", "dirty": True}
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=ROOT,
        )
        info["branch"] = r.stdout.strip()
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, text=True, timeout=5, cwd=ROOT,
        )
        info["commit"] = r.stdout.strip()
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5, cwd=ROOT,
        )
        info["dirty"] = bool(r.stdout.strip())
    except Exception:
        pass
    return info


def read_monitor_logs(n=5):
    if not os.path.exists(MONITOR_LOG):
        return None
    try:
        with open(MONITOR_LOG) as f:
            lines = f.readlines()
        return lines[-n:]
    except Exception:
        return None


def main():
    print("=" * 60)
    print("PHASE 129 — PRODUCTION STATUS")
    print("=" * 60)

    # Git state
    print("\n--- Git ---")
    git = get_git_info()
    log("Branch", git["branch"])
    log("HEAD", git["commit"])
    log("Working tree", "CLEAN" if not git["dirty"] else "DIRTY",
        "ok" if not git["dirty"] else "warn")

    # Processes
    print("\n--- Processes ---")
    log("Port 8080", "LISTENING" if port_listening(8080) else "NOT LISTENING",
        "ok" if port_listening(8080) else "fail")
    log("Gunicorn", "RUNNING" if process_running("gunicorn") else "STOPPED",
        "ok" if process_running("gunicorn") else "fail")
    log("cloudflared", "RUNNING" if process_running("cloudflared.*tunnel") else "STOPPED",
        "ok" if process_running("cloudflared.*tunnel") else "warn")
    log("caffeinate (-dimsu)",
        "RUNNING" if process_running("caffeinate.*-dimsu") else "STOPPED",
        "ok" if process_running("caffeinate.*-dimsu") else "warn")

    # Health
    print("\n--- Health ---")
    for label, url in [
        ("Local /healthz", "http://127.0.0.1:8080/healthz"),
        ("Local /", "http://127.0.0.1:8080/"),
        ("Live /", "https://namvibe.com/"),
        ("Live /healthz", "https://namvibe.com/healthz"),
    ]:
        status, body = http_get(url)
        marker = ""
        for m in ("phase129", "phase128", "phase127"):
            if m in body:
                marker = f" [{m}]"
                break
        st = "ok" if status == 200 else ("warn" if status in (301, 302, 404) else "fail")
        log(label, f"{status}{marker}" if status == 200 else str(status), st)

    # Healthz details
    print("\n--- /healthz Details ---")
    _, body = http_get("http://127.0.0.1:8080/healthz", timeout=5)
    if body:
        components = ""
        if '"database"' in body:
            components += "DB:ok "
        if '"redis"' in body:
            components += "Redis:ok "
        if '"job_queue"' in body or '"queue"' in body:
            components += "Queue:ok "
        if components:
            log("Components", components.strip())
        log("Raw", body[:150])
    else:
        log("Raw", "no response")

    # Recent monitor logs
    print("\n--- Recent Monitor Logs ---")
    recent = read_monitor_logs(5)
    if recent:
        for line in recent:
            line = line.strip()
            if line:
                try:
                    rec = json.loads(line)
                    print(f"  {rec.get('ts','?')} | {rec.get('status','?')} | "
                          f"{rec.get('latency_ms',0):.0f}ms | {rec.get('url','?')}")
                except json.JSONDecodeError:
                    print(f"  {line[:120]}")
    else:
        log("Monitor logs", "No entries yet (run monitor_phase129_beta_health.py)")

    print("\n---")
    print("  Tip: python3 scripts/monitor_phase129_beta_health.py to run a check")
    print("  Tip: python3 scripts/stop_phase129_production_local.py --all to stop all")


if __name__ == "__main__":
    main()
