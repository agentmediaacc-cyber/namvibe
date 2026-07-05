#!/usr/bin/env python3
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8080").rstrip("/")
TIMEOUT = 20


def fetch(path, method="GET", data=None, headers=None):
    url = path if path.startswith("http") else f"{BASE_URL}{path}"
    payload = None
    request_headers = {"User-Agent": "namvibe-homepage-interactions/1.0"}
    if headers:
        request_headers.update(headers)
    if data is not None:
        if isinstance(data, str):
            payload = data.encode("utf-8")
        else:
            payload = data
    req = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body, None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body, None
    except Exception as exc:
        return None, "", str(exc)


def find_first(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.groups() if match else None


def report(label, ok, detail):
    prefix = "PASS" if ok else "FAIL"
    print(f"[{prefix}] {label}: {detail}")
    return ok


def main():
    overall = True

    status, home_html, err = fetch("/")
    overall &= report("homepage load", status == 200 and err is None, err or f"HTTP {status}")
    if status != 200 or err:
        return 1

    like_match = find_first(r'data-action="like"[^>]*data-id="([^"]+)"[^>]*data-type="([^"]+)"', home_html)
    comment_match = find_first(r'data-action="comment"[^>]*data-id="([^"]+)"[^>]*data-type="([^"]+)"', home_html)

    like_path = None
    if like_match:
        item_id, item_type = like_match
        like_path = f"/api/home/post/{item_id}/like" if item_type == "post" else f"/reels/api/reels/{item_id}/like" if item_type == "reel" else None
    overall &= report("like button wiring", bool(like_path), like_path or "No homepage post/reel like target found")
    if like_path:
        status, body, err = fetch(like_path, method="POST", headers={"X-Requested-With": "XMLHttpRequest"})
        overall &= report("like endpoint", err is None and status in (200, 201, 302, 401, 403), err or f"HTTP {status}")
        if status and status >= 500:
            overall = False

    comment_path = None
    if comment_match:
        item_id, item_type = comment_match
        if item_type in ("post", "reel", "story"):
            comment_path = f"/api/comments/{item_type}/{item_id}"
    overall &= report("comment button wiring", bool(comment_path), comment_path or "No homepage comment target found")
    if comment_path:
        status, body, err = fetch(comment_path, method="GET", headers={"X-Requested-With": "XMLHttpRequest"})
        overall &= report("comment list endpoint", err is None and status in (200, 302, 401, 403), err or f"HTTP {status}")
        if status and status >= 500:
            overall = False
        status, body, err = fetch(
            comment_path,
            method="POST",
            data='{"body":"diagnostic comment"}',
            headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
        )
        overall &= report("comment submit endpoint", err is None and status in (200, 201, 302, 401, 403), err or f"HTTP {status}")
        if status and status >= 500:
            overall = False

    for path, label in (
        ("/status/create", "story create page"),
        ("/status/api/status/create", "story create API"),
    ):
        method = "GET" if path.endswith("/create") and not path.endswith("/api/status/create") else "POST"
        status, body, err = fetch(path, method=method, headers={"X-Requested-With": "XMLHttpRequest"})
        ok = err is None and status in (200, 201, 302, 401, 403, 400)
        overall &= report(label, ok, err or f"HTTP {status}")
        if status and status >= 500:
            overall = False

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
