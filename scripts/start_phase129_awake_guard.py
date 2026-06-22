#!/usr/bin/env python3
"""
Phase 129 — Awake Guard (macOS Sleep Prevention).
Uses caffeinate to keep the Mac awake during production.
Writes PID to tmp/namvibe_awake_guard.pid
Logs to logs/awake_guard_phase129.log
"""

import os
import sys
import subprocess
import time
import signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PID_FILE = os.path.join(ROOT, "tmp", "namvibe_awake_guard.pid")
LOG_DIR = os.path.join(ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "awake_guard_phase129.log")


def log(msg):
    line = f"[awake_guard] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n")
    except OSError:
        pass


def ensure_dirs():
    for d in (LOG_DIR, os.path.dirname(PID_FILE)):
        os.makedirs(d, exist_ok=True)


def read_pid():
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def caffeinate_running():
    try:
        r = subprocess.run(
            ["pgrep", "-f", "caffeinate.*-dimsu"],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def start():
    ensure_dirs()

    pid = read_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGCONT)
            log(f"A guard PID {pid} is already running")
            return 0
        except ProcessLookupError:
            log(f"Stale PID {pid} — starting fresh")

    if caffeinate_running():
        log("caffeinate -dimsu already running (via pgrep)")
        # Update PID file
        try:
            r = subprocess.run(
                ["pgrep", "-f", "caffeinate.*-dimsu"],
                capture_output=True, text=True, timeout=5,
            )
            if r.stdout.strip():
                pids = r.stdout.strip().splitlines()
                with open(PID_FILE, "w") as f:
                    f.write(pids[0] + "\n")
                log(f"Updated PID file with existing caffeinate PID {pids[0]}")
        except Exception:
            pass
        return 0

    log("Starting caffeinate -dimsu (preventing Mac sleep, display sleep, idle sleep)")
    try:
        proc = subprocess.Popen(
            ["caffeinate", "-dimsu"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with open(PID_FILE, "w") as f:
            f.write(str(proc.pid) + "\n")
        log(f"Caffeinate started (PID {proc.pid})")
    except FileNotFoundError:
        log("ERROR: caffeinate not found on PATH (macOS only)")
        return 1
    except Exception as e:
        log(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(start())
