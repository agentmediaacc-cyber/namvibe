#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


BASE_URL = os.environ.get("NAMVIBE_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def main() -> int:
    console_errors = []
    page_errors = []
    failed_requests = []
    requests = []
    responses = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()

        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on("requestfailed", lambda req: failed_requests.append({"url": req.url, "method": req.method, "failure": req.failure}))
        page.on("request", lambda req: requests.append({"url": req.url, "method": req.method}))
        page.on("response", lambda resp: responses.append({"url": resp.url, "status": resp.status}))

        page.goto(f"{BASE_URL}/reels/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # Basic asset and DOM checks
        scripts = page.locator("script[src]").evaluate_all("(els) => els.map(el => el.getAttribute('src'))")
        styles = page.locator("link[rel='stylesheet']").evaluate_all("(els) => els.map(el => el.getAttribute('href'))")
        reels = page.locator(".reel-slide")
        reel_count = reels.count()
        if reel_count == 0:
            empty = page.locator(".reels-empty")
            assert empty.count() == 1, "Expected a clean empty state when no reels exist"
        else:
            assert reels.count() > 0, "Expected at least one reel slide"
            ids = reels.evaluate_all("(els) => els.map(el => el.getAttribute('data-reel-id'))")
            assert len(ids) == len(set(ids)), "Duplicate reel IDs rendered"
            assert all(ids), "Missing reel IDs"
            videos = page.locator(".reel-video")
            active_debug = page.evaluate("window.NamVibeReels && window.NamVibeReels.debug ? window.NamVibeReels.debug() : null")
            assert active_debug is not None, "Missing reel controller debug hook"
            assert active_debug["mounted"] <= 24, f"Mounted reels exceeded limit: {active_debug['mounted']}"
            assert videos.count() <= 24, "Mounted videos exceeded limit"
            playing = page.evaluate("""
                () => Array.from(document.querySelectorAll('.reel-video')).filter(v => !v.paused && !v.ended && v.readyState > 2).length
            """)
            assert playing <= 1, f"More than one video playing: {playing}"
            assert active_debug["active"] in ids, "Active reel not in rendered IDs"

            # Initial feed should not duplicate the first page.
            feed_requests = [r for r in requests if "/reels/api/reels/feed?limit=5" in r["url"]]
            assert len(feed_requests) <= 1, f"Duplicate page-one request observed: {feed_requests}"

            # Open comments and ensure lazy loading.
            first_id = ids[0]
            comment_req_before = len([r for r in requests if f"/reels/api/reels/{first_id}/comments" in r["url"]])
            comment_btn = page.locator(".reel-slide").first.locator("[data-comment]").first
            comment_btn.click(force=True)
            page.wait_for_timeout(1000)
            comment_req_after = len([r for r in requests if f"/reels/api/reels/{first_id}/comments" in r["url"]])
            assert comment_req_after == comment_req_before + 1, "Comments did not lazy-load exactly once"
            assert page.locator("#reel-comment-drawer").is_visible(), "Comments drawer did not open"
            assert page.evaluate("window.NamVibeReels.debug().active") == first_id

            # Verify no second duplicate request for the same comments open.
            comment_btn.click(force=True)  # close
            page.wait_for_timeout(500)
            comment_btn.click(force=True)  # reopen
            page.wait_for_timeout(500)
            comment_req_after_reopen = len([r for r in requests if f"/reels/api/reels/{first_id}/comments" in r["url"]])
            assert comment_req_after_reopen >= comment_req_after, "Comments request count regressed"

            # Reels should remain bounded after scroll/load.
            page.mouse.wheel(0, 2400)
            page.wait_for_timeout(1500)
            assert page.evaluate("window.NamVibeReels.debug().mounted") <= 24, "Mounted reels exceeded limit after scroll"

        # Asset sanity.
        assert any(src and "reels.js" in src for src in scripts), "Missing reels.js"
        assert sum(1 for src in scripts if src and "reels.js" in src) == 1, "Duplicate reels.js loaded"
        assert sum(1 for href in styles if href and "reels.css" in href) == 1, "Duplicate reels.css loaded"

        print(json.dumps({
            "reel_count": reel_count,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "failed_requests": failed_requests,
            "requests": [r["url"] for r in requests if "/reels/" in r["url"]],
            "responses": [r for r in responses if "/reels/" in r["url"]],
            "playing": playing if reel_count else 0,
            "mounted": active_debug["mounted"] if reel_count else 0,
            "active": active_debug["active"] if reel_count else None,
        }, ensure_ascii=True))
        browser.close()

    benign_failed = [
        r for r in failed_requests
        if r["failure"] == "net::ERR_ABORTED" and (r["url"].endswith(".mp4") or "/storage/v1/object/public/" in r["url"])
    ]
    failed_requests = [r for r in failed_requests if r not in benign_failed]

    if console_errors or page_errors:
        raise SystemExit("Browser reported console/page errors")
    if failed_requests:
        raise SystemExit("Browser had failed requests")
    print("TEST_OK reels browser runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
