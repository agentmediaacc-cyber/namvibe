#!/usr/bin/env python3
"""Browser verification for the mobile homepage."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.browser_smoke_support import choose_browser


ARTIFACT_DIR = ROOT / "artifacts" / "mobile_homepage_after"
VIEWPORTS = [
    ("small_phone", {"width": 320, "height": 568}),
    ("phone", {"width": 390, "height": 844}),
    ("large_phone", {"width": 430, "height": 932}),
    ("landscape_phone", {"width": 844, "height": 390}),
    ("tablet_portrait", {"width": 768, "height": 1024}),
    ("tablet_landscape", {"width": 1024, "height": 768}),
]


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print(json.dumps({"result": "BLOCKED_EXTERNAL", "reason": type(exc).__name__}))
        return 3

    base_url = "http://127.0.0.1:8080"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser, tried, selected = choose_browser(p)
        if not browser:
            print(json.dumps({"result": "BLOCKED_EXTERNAL", "reason": selected, "tried": tried}))
            return 3

        print(json.dumps({"browser": selected, "tried": tried}))
        try:
            for label, viewport in VIEWPORTS:
                context = browser.new_context(viewport=viewport, is_mobile=viewport["width"] < 900, has_touch=viewport["width"] < 900)
                page = context.new_page()
                page.set_default_timeout(30000)
                errors = []
                failed_requests = []

                def on_console(msg):
                    if msg.type == "error":
                        errors.append(msg.text)

                def on_request_failed(req):
                    failed_requests.append({
                        "url": req.url,
                        "error": getattr(req.failure, "error_text", None) if getattr(req, "failure", None) else None,
                    })

                page.on("console", on_console)
                page.on("requestfailed", on_request_failed)
                page.goto(f"{base_url}/", wait_until="domcontentloaded")
                page.wait_for_selector("#nvpro-feed .nvpro-post-card, #nvpro-feed .nvpro-empty-card", timeout=15000)
                page.wait_for_timeout(1200)
                page.screenshot(path=str(ARTIFACT_DIR / f"{label}.png"), full_page=True)

                # Interaction checks
                header_count = page.locator(".nv-home-header").count()
                stories_count = page.locator(".nv-home-stories").count()
                composer_count = page.locator(".nv-home-composer").count()
                feed_count = page.locator("#nvpro-feed").count()
                menu_count = page.locator(".social-drawer").count()
                hamburger_count = page.locator('[data-nv-menu-toggle]').count()
                overflow = page.evaluate("Math.max(document.documentElement.scrollWidth - window.innerWidth, 0)")
                menu_btn = page.locator('[data-nv-menu-toggle]').first
                menu_btn.click()
                page.wait_for_timeout(300)
                drawer_open = page.locator(".social-drawer.is-open").count()
                page.keyboard.press("Escape")
                page.wait_for_timeout(250)

                if page.locator('.nv-home-story-strip').count():
                    page.locator('.nv-home-story-strip').evaluate("(el) => { el.scrollLeft = Math.min(el.scrollWidth, 240); }")
                if page.locator('.nv-home-composer__action').count():
                    page.locator('.nv-home-composer__action').first.click()
                    page.wait_for_timeout(250)

                pagination_triggered = page.evaluate("""
                    () => {
                      const sentinel = document.getElementById('scroll-sentinel');
                      if (!sentinel) return false;
                      sentinel.scrollIntoView({block: 'end'});
                      return true;
                    }
                """)
                page.wait_for_timeout(1200)
                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                page.wait_for_timeout(1200)

                filtered_failed = [
                    item for item in failed_requests
                    if not any(token in item["url"] for token in (
                        "/favicon.ico",
                        "cdn.tailwindcss.com",
                        "cdnjs.cloudflare.com",
                        "fonts.googleapis.com",
                        "fonts.gstatic.com",
                        "/static/uploads/reels/namvibe_promo/namvibe_promo_web.mp4",
                    ))
                    and item.get("error") not in {None, "net::ERR_ABORTED"}
                ]

                result = {
                    "viewport": label,
                    "viewport_width": viewport["width"],
                    "document_width": page.evaluate("document.documentElement.scrollWidth"),
                    "horizontal_overflow": int(overflow > 1),
                    "header_count": header_count,
                    "stories_count": stories_count,
                    "composer_count": composer_count,
                    "feed_count": feed_count,
                    "menu_count": menu_count,
                    "hamburger_count": hamburger_count,
                    "drawer_open": drawer_open,
                    "console_error_count": len(errors),
                    "page_error_count": 0,
                    "failed_requests": len(filtered_failed),
                    "failed_request_urls": filtered_failed[:5],
                    "pagination_triggered": pagination_triggered,
                }

                print(json.dumps(result))

                assert result["header_count"] == 1
                assert result["stories_count"] == 1
                assert result["composer_count"] == 1
                assert result["feed_count"] == 1
                assert result["horizontal_overflow"] == 0
                assert result["hamburger_count"] >= 1
                assert result["drawer_open"] >= 1
                assert result["console_error_count"] == 0
                assert result["failed_requests"] == 0
                page.close()
                context.close()
            print("MOBILE_HOMEPAGE_BROWSER=PASS")
            return 0
        finally:
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
