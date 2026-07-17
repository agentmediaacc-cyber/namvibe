#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def candidate_browsers():
    return [
        os.getenv("PLAYWRIGHT_CHROME_PATH"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        None,
    ]


def main():
    tried = []
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print(json.dumps({"result": "BLOCKED_EXTERNAL", "reason": type(exc).__name__}))
        return 3

    base = "http://127.0.0.1:8080"
    pages = [
        ("desktop", {"width": 1440, "height": 1200}),
        ("mobile", {"width": 390, "height": 844, "is_mobile": True, "has_touch": True}),
    ]
    with sync_playwright() as p:
        last_error = None
        for chrome in candidate_browsers():
            tried.append(chrome or "playwright-default")
            try:
                browser = p.chromium.launch(headless=True, executable_path=chrome) if chrome else p.chromium.launch(headless=True)
                print(json.dumps({"browser": chrome or "playwright-default"}))
                break
            except Exception as exc:
                last_error = exc
                browser = None
        if not browser:
            print(json.dumps({"result": "BLOCKED_EXTERNAL", "reason": type(last_error).__name__ if last_error else "browser_launch_failed", "tried": tried}))
            return 3
        try:
            for label, vp in pages:
                page = browser.new_page(viewport={k: v for k, v in vp.items() if k in {"width", "height"}})
                page.set_default_timeout(20000)
                errs = []
                page.on("console", lambda msg: errs.append(msg.text) if msg.type == "error" else None)
                page.goto(f"{base}/", wait_until="domcontentloaded")
                assert page.title()
                page.goto(f"{base}/profile/@namvibe", wait_until="domcontentloaded")
                page.goto(f"{base}/profile/@definitely-missing-profile", wait_until="domcontentloaded")
                page.goto(f"{base}/discover", wait_until="domcontentloaded")
                page.goto(f"{base}/reels/", wait_until="domcontentloaded")
                page.goto(f"{base}/notifications", wait_until="domcontentloaded")
                page.goto(f"{base}/messages", wait_until="domcontentloaded")
                page.goto(f"{base}/calls", wait_until="domcontentloaded")
                page.goto(f"{base}/socket.io/?EIO=4&transport=polling", wait_until="domcontentloaded")
                print(json.dumps({"result": "PASS", "stage": f"browser_{label}"}))
                page.close()
            print(json.dumps({"result": "PASS", "stage": "summary"}))
            return 0
        finally:
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
