#!/usr/bin/env python3
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "logs" / "gunicorn_error.log"
BASE_URL = "http://127.0.0.1:8080"
BAD_STATUSES = {500, 502, 503, 504}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def fetch(path, timeout=5.0, host=None):
    headers = {}
    if host:
        headers["Host"] = host
    req = Request(f"{BASE_URL}{path}", headers=headers)
    start = time.perf_counter()
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        elapsed_ms = (time.perf_counter() - start) * 1000
        return resp.status, body, elapsed_ms


def main():
    results = {}
    log_text = LOG_PATH.read_text(errors="replace") if LOG_PATH.exists() else ""

    pid_matches = re.findall(r"Listening at: http://127\.0\.0\.1:8080 \((\d+)\)", log_text)
    require(pid_matches, "Gunicorn master PID not found in logs")
    master_pid = int(pid_matches[-1])
    try:
        os.kill(master_pid, 0)
    except OSError as exc:
        raise AssertionError(f"Gunicorn process not alive: {master_pid}") from exc
    results["gunicorn_master_pid"] = master_pid

    require("Listening at: http://127.0.0.1:8080" in log_text, "port 8080 listener not found in logs")
    results["listening"] = True

    health_status, health_body, health_ms = fetch("/healthz", timeout=5.0)
    require(health_status == 200, f"/healthz returned {health_status}")
    results["healthz"] = {"status": health_status, "elapsed_ms": round(health_ms, 2)}

    home_status, home_body, home_ms = fetch("/", timeout=5.0, host="namvibe.com")
    require(home_status == 200, f"/ returned {home_status}")
    require(home_status not in BAD_STATUSES, f"/ returned bad status {home_status}")
    require(home_ms < 3000, f"/ exceeded 3000ms: {home_ms:.2f}ms")
    require("window.NAMVIBE_HOME_DEGRADED = true;" in home_body, "homepage degraded flag was not true")
    results["homepage"] = {
        "status": home_status,
        "elapsed_ms": round(home_ms, 2),
        "degraded_flag": True,
    }

    boot_failure = re.search(r"Exception in worker process|Worker \(pid:.*exited with code|Traceback", log_text)
    require(boot_failure is None, "worker boot failure found in logs")
    results["worker_boot_failure"] = False

    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, URLError, OSError) as exc:
        print(f"AUDIT FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
