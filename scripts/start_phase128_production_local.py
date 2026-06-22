#!/usr/bin/env python3
"""
Phase 128 — Production Gunicorn Launcher.
Starts Gunicorn on 0.0.0.0:8080 with proper worker, timeout, and logging.
Usage:
    python3 scripts/start_phase128_production_local.py          # start
    python3 scripts/start_phase128_production_local.py --restart  # restart
"""

import os
import sys
import subprocess
import time
import signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PID_FILE = os.path.join(ROOT, "tmp", "namvibe_gunicorn.pid")
LOG_DIR = os.path.join(ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "gunicorn_phase128.log")
HOST = "0.0.0.0"
PORT = "8080"
VENV_PYTHON = os.path.join(ROOT, "venv", "bin", "python3")


def log(msg):
    print(f"[gunicorn] {msg}")


def ensure_dirs():
    for d in (LOG_DIR, os.path.dirname(PID_FILE)):
        os.makedirs(d, exist_ok=True)


def find_python():
    if os.path.exists(VENV_PYTHON):
        return VENV_PYTHON
    return sys.executable


def port_in_use(port):
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(("127.0.0.1", int(port)))
        s.close()
        return result == 0
    except Exception:
        return False


def read_pid():
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def kill_old():
    pid = read_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            log(f"Sent SIGTERM to PID {pid}")
            time.sleep(2)
        except ProcessLookupError:
            log(f"PID {pid} not found")
        except PermissionError:
            log(f"Cannot kill PID {pid}")
    # Also kill any gunicorn on our port
    try:
        subprocess.run(
            ["pkill", "-f", f"gunicorn.*:{PORT}"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


def start():
    ensure_dirs()
    python = find_python()
    restart = "--restart" in sys.argv

    if port_in_use(PORT):
        log(f"Port {PORT} already in use")
        if restart:
            log("--restart: killing old process")
            kill_old()
            time.sleep(2)
        else:
            log("Use --restart to force restart")
            return

    if restart:
        kill_old()
        time.sleep(2)

    log(f"Starting Gunicorn on {HOST}:{PORT}")
    log(f"Python: {python}")
    log(f"PID file: {PID_FILE}")
    log(f"Log file: {LOG_FILE}")

    cmd = [
        python, "-m", "gunicorn",
        "--bind", f"{HOST}:{PORT}",
        "--worker-class", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker",
        "--workers", "1",
        "--timeout", "120",
        "--keep-alive", "5",
        "--access-logfile", LOG_FILE,
        "--error-logfile", LOG_FILE,
        "--log-level", "info",
        "--pid", PID_FILE,
        "app:app",
    ]

    log("Command: " + " ".join(cmd))
    env = os.environ.copy()
    env["FLASK_ENV"] = "production"
    env["ENV"] = "production"

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log(f"Gunicorn started (PID {proc.pid})")
    except FileNotFoundError as e:
        log(f"ERROR: gunicorn not found — '{e}'")
        log("Install: pip install gunicorn gevent-websocket")
        return 1

    # Wait for startup
    for i in range(15):
        time.sleep(1)
        if port_in_use(PORT):
            log(f"Gunicorn ready on port {PORT} after {i+1}s")
            break
    else:
        log("WARNING: Gunicorn may not be listening yet")

    # Verify /healthz
    try:
        import urllib.request
        r = urllib.request.urlopen("http://127.0.0.1:8080/healthz", timeout=5)
        if r.status == 200:
            log("Health OK: /healthz returned 200")
        else:
            log(f"Health check returned {r.status}")
    except Exception as e:
        log(f"Health check failed: {e}")

    # Verify homepage
    try:
        import urllib.request
        r = urllib.request.urlopen("http://127.0.0.1:8080/", timeout=5)
        body = r.read().decode("utf-8", errors="ignore")
        if "phase127" in body or "phase128" in body:
            log("Homepage OK: phase127+ marker found")
        else:
            log("Homepage loaded but marker not found (expected before redeploy)")
    except Exception as e:
        log(f"Homepage verification failed: {e}")

    log("Done")
    return 0


if __name__ == "__main__":
    sys.exit(start())
