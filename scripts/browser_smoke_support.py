#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from typing import Iterable

BROWSER_CANDIDATES = [
    os.getenv("PLAYWRIGHT_CHROME_PATH"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    None,
]


def _browser_name(path):
    if not path:
        return "playwright-default"
    return os.path.basename(path)


def choose_browser(p, retries: int = 3):
    tried = []
    last_error = None
    for candidate in BROWSER_CANDIDATES:
        tried.append(_browser_name(candidate))
        for attempt in range(1, retries + 1):
            browser = None
            context = None
            page = None
            try:
                browser = p.chromium.launch(headless=True, executable_path=candidate) if candidate else p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                page.goto('data:text/html,<html><body>smoke</body></html>', wait_until='domcontentloaded')
                return browser, tried, candidate or 'playwright-default'
            except Exception as exc:
                last_error = exc
                print(json.dumps({"browser_probe_candidate": _browser_name(candidate), "attempt": attempt, "error": type(exc).__name__, "stage": "probe"}))
                try:
                    if page is not None and not page.is_closed():
                        page.close()
                except Exception:
                    pass
                try:
                    if context is not None:
                        context.close()
                except Exception:
                    pass
                try:
                    if browser is not None:
                        browser.close()
                except Exception:
                    pass
    return None, tried, type(last_error).__name__ if last_error else 'browser_launch_failed'


def exercise_routes(page, base: str, routes: Iterable[str]):
    failures = []
    for route in routes:
        try:
            resp = page.goto(f"{base}{route}", wait_until="domcontentloaded")
            if resp is not None and resp.status >= 500:
                failures.append((route, f"http_{resp.status}"))
                continue
            page.wait_for_timeout(2500 if route == "/" else 800)
        except Exception as exc:
            failures.append((route, type(exc).__name__))
    return failures


def run_smoke(routes, extra_assert=None):
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
        browser, tried, selected = choose_browser(p)
        if not browser:
            print(json.dumps({"result": "BLOCKED_EXTERNAL", "reason": selected, "tried": tried}))
            return 3
        print(json.dumps({"browser": selected}))
        try:
            for label, vp in pages:
                context = None
                page = None
                try:
                    context = browser.new_context(viewport={k: v for k, v in vp.items() if k in {"width", "height"}})
                    page = context.new_page()
                    page.set_default_timeout(20000)
                    errors = []
                    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" and all(code not in msg.text for code in ("429", "401", "404", "[NV Stories] feed error")) else None)
                    failures = exercise_routes(page, base, routes)
                    if extra_assert:
                        extra_assert(page, label)
                    if errors:
                        raise AssertionError(f"console_errors={errors[:3]}")
                    if failures:
                        raise AssertionError(f"route_failures={failures[:3]}")
                    print(json.dumps({"result": "PASS", "stage": f"browser_{label}"}))
                finally:
                    try:
                        if page is not None and not page.is_closed():
                            page.close()
                    except Exception:
                        pass
                    try:
                        if context is not None:
                            context.close()
                    except Exception:
                        pass
            print(json.dumps({"result": "PASS", "stage": "summary"}))
            return 0
        finally:
            try:
                browser.close()
            except Exception:
                pass
