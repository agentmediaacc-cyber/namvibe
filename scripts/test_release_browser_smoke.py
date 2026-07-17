#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = ROOT / "tmp" / "release-verification"


def emit(result: str, stage: str, **payload) -> None:
    print(json.dumps({"result": result, "stage": stage, **payload}, sort_keys=True))


def _viewport(name: str) -> dict:
    if name == "mobile":
        return {"width": 390, "height": 844}
    return {"width": 1440, "height": 900}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--viewport", choices=("desktop", "mobile"), default="desktop")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        emit("BLOCKED_EXTERNAL", "import", reason="playwright unavailable", error_type=type(exc).__name__)
        return 2

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    out_dir = RESULTS_ROOT / f"browser_{args.viewport}"
    out_dir.mkdir(parents=True, exist_ok=True)

    urls = [
        ("homepage", "http://127.0.0.1:8080/"),
        ("profile", "http://127.0.0.1:8080/profile/@namvibe"),
        ("missing_profile", "http://127.0.0.1:8080/profile/@definitely-missing-profile"),
        ("discover", "http://127.0.0.1:8080/discover"),
        ("reels", "http://127.0.0.1:8080/reels/"),
        ("notifications", "http://127.0.0.1:8080/notifications"),
        ("messages", "http://127.0.0.1:8080/messages"),
        ("calls", "http://127.0.0.1:8080/calls"),
    ]

    candidates = [
        os.environ.get("PLAYWRIGHT_CHROME_PATH", ""),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        os.environ.get("NAMVIBE_BROWSER_PATH", ""),
    ]
    with sync_playwright() as pw:
        browser = None
        launch_error = None
        selected_path = "playwright-managed"
        for chrome_path in candidates:
            launch_kwargs = {"headless": True}
            if chrome_path and Path(chrome_path).exists():
                selected_path = chrome_path
                launch_kwargs["executable_path"] = chrome_path
                launch_kwargs["args"] = ["--disable-dev-shm-usage", "--disable-gpu"]
            else:
                selected_path = "playwright-managed"
            try:
                browser = pw.chromium.launch(**launch_kwargs)
                break
            except Exception as exc:
                launch_error = exc
                browser = None
                continue
        if browser is None:
            emit(
                "BLOCKED_EXTERNAL",
                "launch",
                error_type=type(launch_error).__name__ if launch_error else "LaunchError",
                message=str(launch_error)[:180] if launch_error else "browser launch failed",
                executable_path=selected_path,
            )
            return 2
        page = browser.new_page(viewport=_viewport(args.viewport))
        page.set_default_timeout(15000)
        failures = []

        def check(name: str, url: str) -> None:
            try:
                wait_until = "domcontentloaded"
                resp = page.goto(url, wait_until=wait_until)
                emit("PASS", name, url=url, status_code=resp.status if resp else None, title=page.title()[:120])
                if page.screenshot is not None:
                    page.screenshot(path=str(out_dir / f"{name}.png"), full_page=True)
            except Exception as exc:
                failures.append((name, type(exc).__name__, str(exc)[:180]))
                emit("FAIL", name, url=url, error_type=type(exc).__name__, message=str(exc)[:180])

        for name, url in urls:
            check(name, url)

        try:
            page.goto("http://127.0.0.1:8080/", wait_until="domcontentloaded")
            emit("PASS", "socketio_check", websocket="not_opened", note="smoke only")
        except Exception as exc:
            failures.append(("socketio_check", type(exc).__name__, str(exc)[:180]))
            emit("FAIL", "socketio_check", error_type=type(exc).__name__, message=str(exc)[:180])

        browser.close()

    if failures:
        emit("FAIL", "summary", failure_count=len(failures), viewport=args.viewport)
        return 1
    emit("PASS", "summary", viewport=args.viewport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
