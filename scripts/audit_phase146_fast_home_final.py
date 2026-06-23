#!/usr/bin/env python3
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8080"
HOME_URL = f"{BASE_URL}/"
FEED_URL = f"{BASE_URL}/api/homepage/feed?tab=for_you&limit=20"
BAD_STATUSES = {500, 502, 503, 504}
HTML_FLAG = "window.NAMVIBE_HOME_DEGRADED = true;"


def fetch(url, timeout=6.0):
    req = Request(url, headers={"Host": "namvibe.com"})
    start = time.perf_counter()
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            elapsed_ms = (time.perf_counter() - start) * 1000
            return resp.status, body, elapsed_ms, None
    except HTTPError as exc:
        body = exc.read()
        elapsed_ms = (time.perf_counter() - start) * 1000
        return exc.code, body, elapsed_ms, None
    except URLError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return None, b"", elapsed_ms, str(exc)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return None, b"", elapsed_ms, str(exc)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def fetch_via_test_client(path):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from app import app as flask_app

    client = flask_app.test_client()
    start = time.perf_counter()
    resp = client.get(path, headers={"Host": "namvibe.com"})
    elapsed_ms = (time.perf_counter() - start) * 1000
    return resp.status_code, resp.get_data(), elapsed_ms


def main():
    results = {}
    mode = "http"

    home_status, home_body, home_elapsed_ms, home_error = fetch(HOME_URL, timeout=5.0)
    if home_error is not None:
        mode = "test_client"
        home_status, home_body, home_elapsed_ms = fetch_via_test_client("/")
    require(home_status not in BAD_STATUSES, f"homepage returned bad status {home_status}")
    require(home_status == 200, f"homepage returned {home_status}")
    require(home_elapsed_ms < 3000, f"homepage exceeded 3000ms: {home_elapsed_ms:.2f}ms")

    home_text = home_body.decode("utf-8", errors="replace")
    require(HTML_FLAG in home_text, "homepage missing degraded flag")

    results["homepage"] = {
        "status": home_status,
        "elapsed_ms": round(home_elapsed_ms, 2),
        "contains_flag": HTML_FLAG in home_text,
    }

    feed_status, feed_body, feed_elapsed_ms, feed_error = fetch(FEED_URL, timeout=6.5)
    if feed_error is not None:
        mode = "test_client"
        feed_status, feed_body, feed_elapsed_ms = fetch_via_test_client("/api/homepage/feed?tab=for_you&limit=20")
    require(feed_status not in BAD_STATUSES, f"feed returned bad status {feed_status}")
    require(feed_status == 200, f"feed returned {feed_status}")

    try:
        feed_json = json.loads(feed_body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"feed returned invalid JSON: {exc}") from exc

    require(isinstance(feed_json, dict), "feed JSON was not an object")
    require(
        ("ok" in feed_json) or ("payload" in feed_json) or ("homepage_degraded" in feed_json),
        "feed JSON was not a recognized success or degraded payload",
    )

    results["feed"] = {
        "status": feed_status,
        "elapsed_ms": round(feed_elapsed_ms, 2),
        "keys": sorted(feed_json.keys())[:12],
    }
    results["mode"] = mode

    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"AUDIT FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
