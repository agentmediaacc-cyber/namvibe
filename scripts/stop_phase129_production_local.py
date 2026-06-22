#!/usr/bin/env python3
"""
Phase 129 — Safe Production Stop Script.
Stops Gunicorn, cloudflared, and/or caffeinate cleanly.
Uses PID files first; falls back to process search.
Never kills unrelated Python processes.
"""

import os
import sys
import signal
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STOPPED = []


def log(msg):
    print(f"[stop] {msg}")


def read_pid(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def kill_pid(pid, name):
    if not pid:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        log(f"Sent SIGTERM to {name} (PID {pid})")
        time.sleep(1)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        STOPPED.append(name)
        return True
    except ProcessLookupError:
        log(f"{name} PID {pid} not found (already stopped)")
        return False
    except PermissionError:
        log(f"Cannot kill {name} PID {pid}")
        return False


def find_and_kill(pattern, name):
    try:
        r = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            pids = r.stdout.strip().splitlines()
            for pid_str in pids:
                try:
                    pid = int(pid_str.strip())
                    kill_pid(pid, name)
                except ValueError:
                    pass
    except Exception:
        pass


def stop_gunicorn():
    pid = read_pid(os.path.join(ROOT, "tmp", "namvibe_gunicorn.pid"))
    if pid:
        kill_pid(pid, "gunicorn")
    else:
        find_and_kill("gunicorn.*:8080", "gunicorn")


def stop_cloudflared():
    find_and_kill("cloudflared.*tunnel", "cloudflared")


def stop_awake():
    pid = read_pid(os.path.join(ROOT, "tmp", "namvibe_awake_guard.pid"))
    if pid:
        kill_pid(pid, "caffeinate")
    else:
        find_and_kill("caffeinate.*-dimsu", "caffeinate")


def main():
    stop_gunicorn()

    if "--tunnel" in sys.argv:
        stop_cloudflared()

    if "--awake" in sys.argv:
        stop_awake()

    if "--all" in sys.argv:
        stop_cloudflared()
        stop_awake()

    if not STOPPED:
        log("Nothing stopped (no processes found)")
        return 0

    log(f"Stopped: {', '.join(STOPPED)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
