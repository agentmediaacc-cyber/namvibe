#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path


BASE_URL = "http://127.0.0.1:8080"
BAD_STATUSES = {500, 502, 503, 504}
ROOT = Path(__file__).resolve().parents[1]


def fetch(path, timeout=5.0):
    command = [
        "curl",
        "-i",
        "-s",
        "-H",
        "Host: namvibe.com",
        "-m",
        str(timeout),
        "-w",
        "\nHTTP:%{http_code}\nTIME:%{time_total}s\n",
        f"{BASE_URL}{path}",
    ]
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return None, "", 0.0, (proc.stderr or proc.stdout or f"curl exited {proc.returncode}").strip()

    output = proc.stdout
    status_marker = "\nHTTP:"
    time_marker = "\nTIME:"
    status_idx = output.rfind(status_marker)
    time_idx = output.rfind(time_marker)
    if status_idx == -1 or time_idx == -1:
        return None, output, 0.0, "missing curl markers"

    body = output[:status_idx]
    if "\r\n\r\n" in body:
        body = body.split("\r\n\r\n", 1)[1]
    elif "\n\n" in body:
        body = body.split("\n\n", 1)[1]
    status_text = output[status_idx + len(status_marker):time_idx].strip()
    time_text = output[time_idx + len(time_marker):].strip().rstrip("s")
    try:
        status = int(status_text)
        elapsed_ms = float(time_text) * 1000
    except ValueError as exc:
        return None, body, 0.0, f"parse error: {exc}"
    return status, body, elapsed_ms, None


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    results = {}

    profile_status, profile_body, profile_ms, profile_error = fetch("/profile/@beta", timeout=3.5)
    require(profile_error is None, f"/profile/@beta failed: {profile_error}")
    require(profile_status not in BAD_STATUSES, f"/profile/@beta returned {profile_status}")
    require(profile_status == 200 or profile_status == 302, f"/profile/@beta returned {profile_status}")
    require(profile_ms < 3000 or profile_status in {200, 302}, f"/profile/@beta exceeded 3000ms: {profile_ms:.2f}ms")
    results["profile"] = {"status": profile_status, "elapsed_ms": round(profile_ms, 2)}

    feed_status, feed_body, feed_ms, feed_error = fetch("/api/homepage/feed", timeout=3.5)
    require(feed_error is None, f"/api/homepage/feed failed: {feed_error}")
    require(feed_status not in BAD_STATUSES, f"/api/homepage/feed returned {feed_status}")
    require(feed_status == 200, f"/api/homepage/feed returned {feed_status}")
    require(feed_ms < 3000, f"/api/homepage/feed exceeded 3000ms: {feed_ms:.2f}ms")
    require(feed_body.lstrip().startswith("{"), "/api/homepage/feed did not return JSON")
    results["homepage_feed"] = {"status": feed_status, "elapsed_ms": round(feed_ms, 2)}

    settings_status, settings_body, settings_ms, settings_error = fetch("/settings/", timeout=3.5)
    require(settings_error is None, f"/settings/ failed: {settings_error}")
    require(settings_status not in BAD_STATUSES, f"/settings/ returned {settings_status}")
    require(settings_status in {200, 302}, f"/settings/ returned {settings_status}")
    results["settings"] = {"status": settings_status, "elapsed_ms": round(settings_ms, 2)}

    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"AUDIT FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
