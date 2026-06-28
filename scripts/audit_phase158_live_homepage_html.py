#!/usr/bin/env python3
from __future__ import annotations

import subprocess


BANNED_STRINGS = [
    "Special homepage",
    "Your NamVibe feed is ready",
    "No reels yet",
    "No stories yet",
    "Privacy  Public Followers Private",
    'data-namvibe-build="phase141"',
]

TARGETS = [
    ("local_root", "http://127.0.0.1:8080/"),
    ("local_home", "http://127.0.0.1:8080/home"),
    ("live_root", "https://namvibe.com/"),
    ("live_home", "https://namvibe.com/home"),
]


def fetch_html(url: str) -> str:
    result = subprocess.run(
        [
            "curl",
            "-sS",
            "--max-time",
            "20",
            "-H",
            "Cache-Control: no-cache",
            "-H",
            "Pragma: no-cache",
            "-A",
            "phase158-homepage-audit/1.0",
            url,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"curl exited {result.returncode}")
    return result.stdout


def main() -> int:
    failures = []
    for label, url in TARGETS:
        try:
            html = fetch_html(url)
        except Exception as exc:
            failures.append(f"{label}: fetch failed for {url}: {exc}")
            continue

        for banned in BANNED_STRINGS:
            if banned in html:
                failures.append(f"{label}: found banned text {banned!r} in {url}")

    if failures:
        print("PHASE158_AUDIT_FAILED")
        for failure in failures:
            print(failure)
        return 1

    print("PHASE158_AUDIT_OK")
    for label, url in TARGETS:
        print(f"{label}: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
