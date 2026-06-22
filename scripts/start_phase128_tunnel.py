#!/usr/bin/env python3
"""
Phase 128 — Cloudflare Tunnel Launcher.
Starts cloudflared tunnel run for namvibe.com.
Logs to logs/cloudflared_phase128.log.
"""

import os
import sys
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "cloudflared_phase128.log")
CONFIG_PATH = os.path.expanduser("~/.cloudflared/config.yml")
TUNNEL_ID = "8f008f0f-9d5e-4b7f-b67e-08e0f1c83921"


def log(msg):
    print(f"[cloudflared] {msg}")


def ensure_dirs():
    os.makedirs(LOG_DIR, exist_ok=True)


def check_config():
    if not os.path.exists(CONFIG_PATH):
        log(f"ERROR: Config not found at {CONFIG_PATH}")
        log("Run: cloudflared tunnel login")
        return False

    with open(CONFIG_PATH) as f:
        content = f.read()

    if "localhost:8080" not in content:
        log(f"ERROR: Config does not route to localhost:8080")
        log(f"       Update {CONFIG_PATH} to use service: http://localhost:8080")
        return False

    if "namvibe.com" not in content:
        log(f"WARNING: namvibe.com not found in config — tunnel may not route correctly")

    log("Config OK")
    return True


def check_tunnel_credentials():
    creds_path = os.path.expanduser(f"~/.cloudflared/{TUNNEL_ID}.json")
    if not os.path.exists(creds_path):
        log(f"WARNING: Credentials file not found at {creds_path}")
        log("Run: cloudflared tunnel login")
        return False
    return True


def tunnel_running():
    try:
        result = subprocess.run(
            ["pgrep", "-f", "cloudflared.*tunnel"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def start():
    ensure_dirs()

    if tunnel_running():
        log("Cloudflared tunnel already running")
        return 0

    if not check_config():
        return 1

    check_tunnel_credentials()

    log(f"Starting cloudflared tunnel {TUNNEL_ID}")
    log(f"Config: {CONFIG_PATH}")
    log(f"Log: {LOG_FILE}")

    cmd = [
        "cloudflared", "tunnel", "run",
        "--config", CONFIG_PATH,
        TUNNEL_ID,
    ]

    try:
        with open(LOG_FILE, "a") as log_fh:
            proc = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=log_fh,
            )
        log(f"Cloudflared started (PID {proc.pid})")
    except FileNotFoundError:
        log("ERROR: cloudflared not found on PATH")
        log("Install: brew install cloudflared")
        return 1

    # Wait and verify
    for i in range(10):
        time.sleep(1)
        if tunnel_running():
            log(f"Tunnel running after {i+1}s")
            break
    else:
        log("WARNING: Tunnel may not have started — check logs")

    return 0


if __name__ == "__main__":
    sys.exit(start())
