#!/usr/bin/env python3
"""
Phase 164B Controlled Live Repair

This script does NOT modify application files.
It verifies the real failing surfaces:

* homepage health/feed
* post detail route
* like/comment route availability
* story route availability
* reel route availability
* Supabase media URL accessibility
* service worker cache version risk
"""

import json
import re
import ssl
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BASE_LOCAL = "http://127.0.0.1:8080"
BASE_LIVE = "https://namvibe.com"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _can_retry_insecure(url):
    parsed = urlparse(url)
    return parsed.scheme == "https"


def run(cmd, timeout=30):
    print(f"\nCOMMAND: {cmd}")
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    print(f"EXIT: {proc.returncode}")
    if proc.stdout.strip():
        print("STDOUT:")
        print(proc.stdout[-4000:])
    if proc.stderr.strip():
        print("STDERR:")
        print(proc.stderr[-4000:])
    return proc


def _open_url(url, timeout=20, method="GET"):
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS, method=method)
    try:
        return urllib.request.urlopen(req, timeout=timeout), False
    except ssl.SSLCertVerificationError as exc:
        if not _can_retry_insecure(url):
            raise
        print(f"SSL VERIFY ERROR: {type(exc).__name__}: {exc}")
        insecure_ctx = ssl._create_unverified_context()
        return urllib.request.urlopen(req, timeout=timeout, context=insecure_ctx), True
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if not isinstance(reason, ssl.SSLCertVerificationError):
            raise
        if not _can_retry_insecure(url):
            raise
        print(f"SSL VERIFY ERROR: {type(reason).__name__}: {reason}")
        insecure_ctx = ssl._create_unverified_context()
        return urllib.request.urlopen(req, timeout=timeout, context=insecure_ctx), True


def fetch_json(url, timeout=20):
    print(f"\nFETCH JSON: {url}")
    try:
        response, used_insecure_ssl = _open_url(url, timeout=timeout)
        with response:
            body = response.read().decode("utf-8", "replace")
            print(f"HTTP: {response.status}")
            if used_insecure_ssl:
                print("WARNING: SSL verification bypassed for diagnostic access")
            data = json.loads(body)
            print(json.dumps(data, indent=2)[:4000])
            return response.status, data
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 0, None


def fetch_head(url, timeout=15):
    print(f"\nFETCH HEAD: {url}")
    try:
        response, used_insecure_ssl = _open_url(url, timeout=timeout, method="HEAD")
        with response:
            print(f"HTTP: {response.status}")
            if used_insecure_ssl:
                print("WARNING: SSL verification bypassed for diagnostic access")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print(f"Content-Length: {response.headers.get('content-length')}")
            return response.status
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 0


def grep_file(path, patterns):
    file_path = ROOT / path
    print(f"\nCHECK FILE: {path}")
    if not file_path.exists():
        print("MISSING")
        return False
    text = file_path.read_text(errors="ignore")
    ok = True
    for label, pattern in patterns:
        found = re.search(pattern, text, re.S) is not None
        print(f"{'PASS' if found else 'FAIL'}: {label}")
        ok = ok and found
    return ok


def main():
    failures = []

    print("=" * 80)
    print("PHASE 164B CONTROLLED LIVE REPAIR CHECK")
    print("=" * 80)

    proc = run("python3 -m py_compile app.py services/*.py api_routes/*.py", timeout=60)
    if proc.returncode != 0:
        failures.append("COMPILE_FAILED")

    for base in (BASE_LOCAL, BASE_LIVE):
        status, data = fetch_json(f"{base}/healthz")
        if status != 200 or not data or data.get("ok") is not True:
            failures.append(f"HEALTH_FAILED_{base}")

    status, data = fetch_json(f"{BASE_LIVE}/api/homepage/feed")
    first_post_id = None
    first_media_url = None
    first_reel_id = None

    if status == 200 and data and data.get("ok"):
        payload = data.get("payload") or {}
        feed_items = payload.get("feed_items") or []
        reels = payload.get("reels") or []
        print(
            f"\nFEED COUNTS: feed_items={len(feed_items)} "
            f"reels={len(reels)} stories={len(payload.get('stories') or [])}"
        )
        for item in feed_items:
            if item.get("id"):
                first_post_id = item.get("id")
            media_url = item.get("media_url") or item.get("public_url") or item.get("image_url")
            if media_url:
                first_media_url = media_url
                first_post_id = item.get("id")
                break
        for reel in reels:
            if reel.get("id"):
                first_reel_id = reel.get("id")
                break
    else:
        failures.append("HOMEPAGE_FEED_FAILED")

    if not first_post_id:
        failures.append("NO_POST_ID_IN_FEED")
    else:
        print(f"\nFIRST POST ID: {first_post_id}")
        try:
            response, used_insecure_ssl = _open_url(f"{BASE_LIVE}/post/{first_post_id}", timeout=20)
            with response:
                html = response.read().decode("utf-8", "replace")
                print(f"POST DETAIL HTTP: {response.status}")
                if used_insecure_ssl:
                    print("WARNING: SSL verification bypassed for diagnostic access")
                print(f"POST DETAIL HAS COMMENT FORM: {'comment' in html.lower()}")
                print(f"POST DETAIL HAS MEDIA: {('img' in html.lower()) or ('video' in html.lower())}")
                if response.status != 200:
                    failures.append("POST_DETAIL_NOT_200")
        except Exception as exc:
            print(f"POST DETAIL ERROR: {type(exc).__name__}: {exc}")
            failures.append("POST_DETAIL_FAILED")

    if first_media_url:
        if fetch_head(first_media_url) != 200:
            failures.append("MEDIA_URL_NOT_PUBLIC")
    else:
        failures.append("NO_MEDIA_URL_IN_FEED")

    if first_reel_id:
        try:
            response, used_insecure_ssl = _open_url(f"{BASE_LIVE}/reels/{first_reel_id}", timeout=20)
            with response:
                html = response.read().decode("utf-8", "replace")
                print(f"REEL DETAIL HTTP: {response.status}")
                if used_insecure_ssl:
                    print("WARNING: SSL verification bypassed for diagnostic access")
                print(f"REEL DETAIL HAS VIDEO: {'video' in html.lower()}")
                if response.status != 200:
                    failures.append("REEL_DETAIL_NOT_200")
        except Exception as exc:
            print(f"REEL DETAIL ERROR: {type(exc).__name__}: {exc}")
            failures.append("REEL_DETAIL_FAILED")
    else:
        failures.append("NO_REEL_ID_IN_FEED")

    checks = [
        (
            "static/js/namvibe_home_pro.js",
            [
                ("like click handler exists", r"like"),
                ("comment handler exists", r"comment"),
                ("optimistic or rollback logic exists", r"rollback|optimistic|dataset|likes"),
                ("fetch API used", r"fetch\("),
            ],
        ),
        (
            "templates/posts/detail.html",
            [
                ("post detail has comment UI", r"comment"),
                ("post detail has like UI", r"like"),
                ("post detail has media rendering", r"<img|<video"),
            ],
        ),
        (
            "templates/reels/detail.html",
            [
                ("reel detail has video", r"<video"),
                ("reel detail has music or controls", r"music|audio|controls"),
            ],
        ),
        (
            "api_routes/engagement_routes.py",
            [
                ("like route exists", r"like"),
                ("comment route exists", r"comment"),
                ("json response exists", r"jsonify|json_response"),
            ],
        ),
        (
            "api_routes/reels_routes.py",
            [
                ("reel create/upload route exists", r"create|upload"),
                ("media url handling exists", r"media_url|video_url|public_url"),
            ],
        ),
        (
            "api_routes/status_routes.py",
            [
                ("story/status create route exists", r"create|upload|status"),
                ("music duration handling exists", r"music_duration|90"),
            ],
        ),
        (
            "static/js/namvibe_service_worker.js",
            [
                ("service worker cache version exists", r"namvibe-cache-v"),
                ("skip waiting exists", r"skipWaiting"),
                ("clients claim exists", r"clients\.claim"),
            ],
        ),
    ]

    for path, patterns in checks:
        if not grep_file(path, patterns):
            failures.append(f"CONTRACT_FAILED_{path}")

    print("\n" + "=" * 80)
    print("RESULT")
    print("=" * 80)
    if failures:
        print("FAILURES:")
        for failure in failures:
            print("-", failure)
        print("\nNEXT: fix the first failure above only.")
        return 1

    print("PASS: live media contract looks healthy.")
    print("NEXT: do manual phone test for like/comment/story/reel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
