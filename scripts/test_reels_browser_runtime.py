#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

BASE_URL = os.environ.get("NAMVIBE_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
VIEWPORTS = [
    {"width": 320, "height": 568},
    {"width": 375, "height": 667},
    {"width": 390, "height": 844},
    {"width": 430, "height": 932},
    {"width": 768, "height": 1024},
    {"width": 1440, "height": 900},
]
EMPTY_SHELL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="csrf-token" content="">
  <link rel="stylesheet" href="/static/css/reels.css?v=20260714-1">
</head>
<body>
<main id="reels-app" class="reels-fullscreen">
  <div id="reels-viewport" class="reels-viewport" data-next-cursor="" data-has-more="false">
    <div class="reels-empty">
      <i class="fas fa-film"></i>
      <h2>Loading Reels…</h2>
      <p>Fetching public Reels.</p>
      <a href="/reels/upload" class="px-btn px-btn--gold">Upload Reel</a>
    </div>
  </div>
  <div id="reels-feed-status" class="reels-feed-status" aria-live="polite" hidden></div>
  <div id="reel-comment-drawer" class="reel-drawer" style="display:none"></div>
  <div id="reel-share-drawer" class="reel-drawer" style="display:none"></div>
</main>
<script>window.__NAMVIBE_REELS_BROWSER_DEBUG__ = true;</script>
<script src="/static/js/reels.js?v=20260714-1"></script>
</body>
</html>"""


def wait_for_or_retry(page, script, timeout=8000):
    try:
        page.wait_for_function(script, timeout=timeout)
        return True
    except PlaywrightTimeoutError:
        return False


def run_viewport_check(playwright, size):
    console_errors = []
    page_errors = []
    failed_requests = []
    requests = []
    responses = []
    response_404s = []

    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport=size)
    page = context.new_page()

    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    page.on("requestfailed", lambda req: failed_requests.append({"url": req.url, "method": req.method, "resource_type": req.resource_type, "failure": req.failure, "frame_url": req.frame.url if req.frame else None}))
    page.on("request", lambda req: requests.append({"url": req.url, "method": req.method}))
    def on_response(resp):
        item = {"url": resp.url, "status": resp.status, "request_url": resp.request.url, "resource_type": resp.request.resource_type}
        responses.append(item)
        if resp.status == 404:
            response_404s.append(item)
    page.on("response", on_response)

    page.goto(f"{BASE_URL}/reels/", wait_until="commit", timeout=30000)
    page.wait_for_timeout(1500)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except PlaywrightTimeoutError:
        pass

    scripts = page.locator("script[src]").evaluate_all("(els) => els.map(el => el.getAttribute('src'))")
    styles = page.locator("link[rel='stylesheet']").evaluate_all("(els) => els.map(el => el.getAttribute('href'))")
    reels = page.locator(".reel-slide")
    reel_count = reels.count()
    assert any(src and "reels.js" in src for src in scripts), "Missing reels.js"
    assert sum(1 for src in scripts if src and "reels.js" in src) == 1, "Duplicate reels.js loaded"
    assert sum(1 for href in styles if href and "reels.css" in href) == 1, "Duplicate reels.css loaded"

    if reel_count == 0:
        empty = page.locator(".reels-empty")
        assert empty.count() == 1, "Expected clean empty state when no reels exist"
        browser.close()
        return {
            "viewport": size,
            "reel_count": 0,
            "playing": 0,
            "mounted": 0,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "failed_requests": failed_requests,
            "requests": [r["url"] for r in requests],
            "responses": [r for r in responses if "/reels/" in r["url"]],
        }

    ids = reels.evaluate_all("(els) => els.map(el => el.getAttribute('data-reel-id'))")
    assert len(ids) == len(set(ids)), "Duplicate reel IDs rendered"
    assert all(ids), "Missing reel IDs"

    active_debug = page.evaluate("window.NamVibeReels && window.NamVibeReels.debug ? window.NamVibeReels.debug() : null")
    assert active_debug is not None, "Missing reel controller debug hook"
    assert active_debug["mounted"] <= 24, f"Mounted reels exceeded limit: {active_debug['mounted']}"

    first = reels.first
    first.scroll_into_view_if_needed(timeout=10000)
    page.wait_for_timeout(800)

    first_video = first.locator(".reel-video")
    first_reel_id = ids[0]
    assert first_video.count() == 1, "Missing first reel video"
    assert first_video.get_attribute("playsinline") is not None, "Missing playsinline"
    assert first_video.get_attribute("webkit-playsinline") is not None, "Missing webkit-playsinline"
    assert first_video.get_attribute("muted") is not None, "Missing muted"
    assert first_video.get_attribute("controlslist") is not None, "Missing controlslist"
    assert first_video.get_attribute("disablepictureinpicture") is not None, "Missing disablepictureinpicture"

    poster = first.locator(".reel-poster")
    retry = first.locator(".reel-play-retry")
    assert page.locator(".reel-poster").count() >= 1, "Missing poster"
    assert retry.count() == 1, "Missing retry button"

    played = wait_for_or_retry(
        page,
        "() => { const v = document.querySelector('.reel-video'); return !!v && !v.paused && !v.ended && v.readyState > 2; }",
    )
    if not played:
        retry.evaluate("(el) => el.click()")
        page.wait_for_timeout(1500)
        played = wait_for_or_retry(
            page,
            "() => { const v = document.querySelector('.reel-video'); return !!v && !v.paused && !v.ended && v.readyState > 2; }",
        )
    assert played, "Reel did not start or recover playback"

    playing = page.evaluate(
        "() => Array.from(document.querySelectorAll('.reel-video')).filter(v => !v.paused && !v.ended && v.readyState > 2).length"
    )
    assert playing <= 1, f"More than one video playing: {playing}"

    active_state = page.evaluate(
        "() => { const v = document.querySelector('.reel-video'); return v ? { muted: v.muted, readyState: v.readyState, src: v.currentSrc || v.src, poster: v.poster || '' } : null; }"
    )
    assert active_state and active_state["muted"] is True, "Active reel must start muted"
    assert active_state["readyState"] >= 2, "Active reel must have data"
    assert active_state["src"], "Active reel missing source"

    # Poster/loading state should exist even if it has already faded out.
    assert page.locator(".reel-poster").count() >= 1
    assert page.locator(".reel-loading").count() >= 1

    # Verify the active reel is the first slide and one video is visible.
    assert active_debug["active"] == first_reel_id, "Active reel not first visible reel"

    # Verify layout stays within the viewport.
    overflow_ok = page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    assert overflow_ok, "Horizontal overflow detected"
    layout_ok = page.evaluate(
        """
        () => {
          const sidebar = document.querySelector('.reel-sidebar');
          const caption = document.querySelector('.reel-caption');
          const rail = document.querySelector('.reel-sidebar');
          if (!sidebar || !caption || !rail) return false;
          const s = sidebar.getBoundingClientRect();
          const c = caption.getBoundingClientRect();
          const vw = window.innerWidth;
          const vh = window.innerHeight;
          return s.right <= vw + 1 && s.bottom <= vh + 1 && c.right <= vw + 1 && c.bottom <= vh + 1 && s.width >= 44;
        }
        """
    )
    assert layout_ok, "Viewport controls/caption outside the usable viewport"

    feed_requests = [r for r in requests if "/reels/api/reels/feed?limit=5" in r["url"]]
    assert len(feed_requests) <= 1, f"Duplicate page-one request observed: {feed_requests}"

    # Open comments and ensure lazy loading.
    comment_req_before = len([r for r in requests if f"/reels/api/reels/{first_reel_id}/comments" in r["url"]])
    comment_btn = page.locator(".reel-slide").first.locator("[data-comment]").first
    comment_btn.click(force=True)
    page.wait_for_timeout(1000)
    comment_req_after = len([r for r in requests if f"/reels/api/reels/{first_reel_id}/comments" in r["url"]])
    assert comment_req_after == comment_req_before + 1, "Comments did not lazy-load exactly once"
    assert page.locator("#reel-comment-drawer").is_visible(), "Comments drawer did not open"
    assert page.evaluate("window.NamVibeReels.debug().active") == first_reel_id

    comment_btn.click(force=True)
    page.wait_for_timeout(500)
    comment_btn.click(force=True)
    page.wait_for_timeout(500)
    comment_req_after_reopen = len([r for r in requests if f"/reels/api/reels/{first_reel_id}/comments" in r["url"]])
    assert comment_req_after_reopen >= comment_req_after, "Comments request count regressed"

    # Scroll to the next reel and ensure a single active video remains.
    page.mouse.wheel(0, size["height"])
    page.wait_for_timeout(1500)
    new_debug = page.evaluate("window.NamVibeReels.debug ? window.NamVibeReels.debug() : null")
    assert new_debug and new_debug["mounted"] <= 24, "Mounted reels exceeded limit after scroll"
    new_playing = page.evaluate(
        "() => Array.from(document.querySelectorAll('.reel-video')).filter(v => !v.paused && !v.ended && v.readyState > 2).length"
    )
    assert new_playing <= 1, f"More than one video playing after scroll: {new_playing}"
    assert new_debug["active"] in ids, "Active reel after scroll not in rendered IDs"
    if reel_count > 1:
        assert new_debug["active"] != first_reel_id, "Active reel did not change after scrolling"

    browser.close()

    benign_failed = [
        r for r in failed_requests
        if r["failure"] == "net::ERR_ABORTED" and (r["url"].endswith(".mp4") or "/storage/v1/object/public/" in r["url"])
    ]
    failed_requests = [r for r in failed_requests if r not in benign_failed]
    if console_errors or failed_requests or response_404s:
        print(json.dumps({"console_errors": console_errors, "failed_requests": failed_requests, "response_404s": response_404s}, ensure_ascii=True))
    assert not console_errors, f"Browser reported console errors: {console_errors}"
    assert not page_errors, f"Browser reported page errors: {page_errors}"
    assert not failed_requests, f"Browser had failed requests: {failed_requests}"

    return {
        "viewport": size,
        "reel_count": reel_count,
        "playing": playing,
        "mounted": new_debug["mounted"],
        "console_errors": console_errors,
        "page_errors": page_errors,
        "failed_requests": failed_requests,
        "requests": [r["url"] for r in requests if "/reels/" in r["url"]],
        "responses": [r for r in responses if "/reels/" in r["url"]],
        "active": new_debug["active"],
    }


def run_empty_shell_hydration_check(playwright):
    console_errors = []
    page_errors = []
    requests = []
    responses = []
    response_404s = []

    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()

    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    page.on("request", lambda req: requests.append({"url": req.url, "method": req.method}))
    def on_response(resp):
        item = {"url": resp.url, "status": resp.status, "request_url": resp.request.url, "resource_type": resp.request.resource_type}
        responses.append(item)
        if resp.status == 404:
            response_404s.append(item)
    page.on("response", on_response)

    page.route("**/reels/", lambda route: route.fulfill(status=200, content_type="text/html", body=EMPTY_SHELL_HTML))
    page.goto(f"{BASE_URL}/reels/", wait_until="load", timeout=30000)
    page.wait_for_timeout(1500)

    feed_requests = [r for r in requests if "/reels/api/reels/feed?limit=5" in r["url"]]
    assert len(feed_requests) == 1, f"Expected one first-page request, saw {feed_requests}"

    page.wait_for_function(
        "() => { const d = window.NamVibeReels && window.NamVibeReels.debug ? window.NamVibeReels.debug() : null; return d && d.mounted >= 5 && d.firstPageRequested; }",
        timeout=15000,
    )
    debug = page.evaluate("window.__NAMVIBE_REELS_DEBUG__")
    assert debug, "Missing reel browser debug state"
    assert debug["initialServerItemCount"] == 0, "Expected empty server shell"
    assert debug["firstPageRequested"] is True, "First page was not requested"
    assert debug["firstPageStatus"] == 200, f"Unexpected first page status: {debug['firstPageStatus']}"
    assert debug["firstPageItemCount"] == 5, f"Unexpected first page item count: {debug['firstPageItemCount']}"
    assert debug["emptyStateVisible"] is False, "Empty state should be hidden after hydration"

    reel_count = page.locator(".reel-slide").count()
    empty_visible = page.locator(".reels-empty").is_visible()
    playing = page.evaluate(
        "() => Array.from(document.querySelectorAll('.reel-video')).filter(v => !v.paused && !v.ended && v.readyState > 2).length"
    )
    active_state = page.evaluate("window.NamVibeReels.debug()")

    assert reel_count == 5, f"Expected hydrated reels, saw {reel_count}"
    assert not empty_visible, "Empty state should not remain visible after hydration"
    assert active_state["active"] is not None, "Hydrated page missing active reel"
    assert playing <= 1, f"More than one video playing on hydrated shell: {playing}"

    browser.close()
    if console_errors or response_404s:
        print(json.dumps({"console_errors": console_errors, "response_404s": response_404s}, ensure_ascii=True))
    assert not console_errors, f"Browser reported console errors: {console_errors}"
    assert not page_errors, f"Browser reported page errors: {page_errors}"
    return {
        "hydration": True,
        "reel_count": reel_count,
        "playing": playing,
        "requests": [r["url"] for r in requests if "/reels/" in r["url"]],
        "responses": [r for r in responses if "/reels/" in r["url"]],
    }


def main() -> int:
    results = []
    with sync_playwright() as playwright:
        results.append(run_empty_shell_hydration_check(playwright))
        for viewport in VIEWPORTS:
            results.append(run_viewport_check(playwright, viewport))

    print(json.dumps({"base_url": BASE_URL, "results": results}, ensure_ascii=True))
    print("TEST_OK reels browser runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
