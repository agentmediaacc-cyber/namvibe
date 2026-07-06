#!/usr/bin/env python3
import os
import re
import sys
import json
import http.cookiejar
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8080").rstrip("/")
TIMEOUT = 20
COOKIE_JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(COOKIE_JAR))


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
        with OPENER.open(req, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body, None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body, None
    except Exception as exc:
        return None, "", str(exc)


def contains(text, needle):
    return needle in text if text is not None else False


def find_first(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.groups() if match else None


def report(label, ok, detail):
    prefix = "PASS" if ok else "FAIL"
    print(f"[{prefix}] {label}: {detail}")
    return ok


def parse_json(body):
    try:
        return json.loads(body or "")
    except Exception:
        return None


def find_csrf_token(html):
    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]*)"', html, re.IGNORECASE)
    return match.group(1) if match else ""


def main():
    overall = True

    status, home_html, err = fetch("/")
    overall &= report("homepage load", status == 200 and err is None, err or f"HTTP {status}")
    if status != 200 or err:
        return 1

    overall &= report(
        "actual homepage JS path",
        contains(home_html, "/static/js/namvibe_camera_creator.js") and contains(home_html, 'document.addEventListener("click", safeHandler("delegated-click"'),
        "chain_home inline handler + camera creator loaded"
    )
    overall &= report(
        "homepage build marker present",
        contains(home_html, 'name="namvibe-home-build"') and contains(home_html, 'window.NAMVIBE_HOME_BUILD = "home-interactions-2026-07-05-v3"'),
        "home-interactions-2026-07-05-v3"
    )
    overall &= report(
        "unused duplicate homepage bundles not loaded",
        not contains(home_html, "/static/js/namvibe_home_pro.js") and not contains(home_html, "/static/js/tiktok_home.js") and not contains(home_html, "/static/js/namvibe_2026_home.js"),
        "namvibe_home_pro.js/tiktok_home.js/namvibe_2026_home.js not referenced by chain_home.html"
    )

    csrf_token = find_csrf_token(home_html)
    overall &= report("homepage csrf token present", bool(csrf_token), "meta csrf token found" if csrf_token else "missing csrf token")

    like_match = find_first(r'data-action="like"[^>]*data-post-id="([^"]+)"[^>]*data-type="([^"]+)"', home_html)
    comment_match = find_first(r'data-action="comment"[^>]*data-post-id="([^"]+)"[^>]*data-type="([^"]+)"', home_html)

    like_path = None
    if like_match:
        item_id, item_type = like_match
        like_path = f"/api/home/post/{item_id}/like" if item_type == "post" else f"/reels/api/reels/{item_id}/like" if item_type == "reel" else None
    overall &= report("like button wiring", bool(like_path), like_path or "No homepage post/reel like target found")
    overall &= report(
        "like button carries stable post attr",
        bool(like_match),
        "homepage rendered a post like button with data-post-id"
    )
    if like_path:
        status, body, err = fetch(like_path, method="POST", headers={"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf_token})
        overall &= report("like endpoint", err is None and status in (200, 201, 302, 401, 403), err or f"HTTP {status}")
        like_json = parse_json(body)
        liked_state_ok = isinstance(like_json, dict) and isinstance(like_json.get("liked"), bool)
        count_ok = isinstance(like_json, dict) and isinstance((like_json.get("likes_count") if like_json.get("likes_count") is not None else like_json.get("count")), int)
        if status in (401, 403):
            liked_state_ok = True
            count_ok = True
        overall &= report("like response liked field", liked_state_ok, like_json if like_json is not None else body)
        overall &= report("like response count field", count_ok, like_json if like_json is not None else body)
        if status and status >= 500:
            overall = False

    comment_path = None
    if comment_match:
        item_id, item_type = comment_match
        if item_type in ("post", "reel", "story"):
            comment_path = f"/api/comments/{item_type}/{item_id}"
    overall &= report("comment button wiring", bool(comment_path), comment_path or "No homepage comment target found")
    overall &= report(
        "comment button carries stable post attr",
        bool(comment_match),
        "homepage rendered a post comment button with data-post-id"
    )
    if comment_path:
        status, body, err = fetch(comment_path, method="GET", headers={"X-Requested-With": "XMLHttpRequest"})
        overall &= report("comment list endpoint", err is None and status in (200, 302, 401, 403), err or f"HTTP {status}")
        if status and status >= 500:
            overall = False
        status, body, err = fetch(
            comment_path,
            method="POST",
            data='{"body":"diagnostic comment","content":"diagnostic comment","text":"diagnostic comment","comment":"diagnostic comment"}',
            headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf_token},
        )
        comment_json = parse_json(body)
        submit_ok = err is None and status in (200, 201, 302, 401, 403)
        overall &= report("comment submit endpoint", submit_ok, comment_json if comment_json is not None else (err or f"HTTP {status}"))
        if status not in (401, 403):
            contract_ok = isinstance(comment_json, dict) and (
                (comment_json.get("ok") is True and isinstance(comment_json.get("comment"), dict))
                or comment_json.get("success") is True
            )
            overall &= report("comment response contract", contract_ok, comment_json if comment_json is not None else body)
        if status and status >= 500:
            overall = False

    inline_handler_count = len(re.findall(r'document\.addEventListener\("click", safeHandler\("delegated-click"', home_html))
    overall &= report("no duplicate delegated like/comment handler", inline_handler_count == 1, f"delegated-click handlers found: {inline_handler_count}")
    overall &= report(
        "inline JS contains like/comment handlers",
        contains(home_html, 'action === "like"') and contains(home_html, 'action === "comment"'),
        "like/comment handler branches present in chain_home inline JS"
    )

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
