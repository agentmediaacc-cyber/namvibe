#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    run_dir = os.environ.get("RUN_DIR")
    if not run_dir:
        raise SystemExit("RUN_DIR is required")
    root = Path(run_dir)
    results_path = root / "homepage_verification_results.json"
    summary_path = root / "homepage_verification_summary.txt"

    assert_true(results_path.exists(), f"missing report json: {results_path}")
    assert_true(summary_path.exists(), f"missing summary txt: {summary_path}")

    data = json.loads(results_path.read_text())
    for key in ("run_dir", "verified_commit", "local_health", "local_home", "local_feed", "public_health", "public_home", "gunicorn_pids", "cloudflared_pids", "browser_viewports"):
        assert_true(key in data, f"missing key: {key}")

    for key in ("local_health", "local_home", "local_feed", "public_health", "public_home"):
        stat = data[key]
        for subkey in ("samples", "min", "median", "p95", "max"):
            assert_true(subkey in stat, f"missing {key}.{subkey}")
        assert_true(isinstance(stat["samples"], list), f"{key}.samples must be a list")
        for sample in stat["samples"]:
            assert_true("http_code" in sample and "time_total" in sample, f"sample shape invalid for {key}")

    viewports = data["browser_viewports"]
    expected = {"browser_desktop", "browser_tablet", "browser_mobile", "browser_small_mobile"}
    assert_true(expected.issubset(viewports.keys()), f"missing browser viewport keys: {sorted(expected - set(viewports.keys()))}")

    for key in expected:
        vp = viewports[key]
        assert_true(vp.get("result") in {"PASS", "FAIL", "NOT_RUN", "MISSING_ARTIFACT"}, f"bad viewport result enum for {key}")
        for field in ("viewport", "screenshot_path", "console_error_count", "page_error_count", "failed_first_party_request_count", "horizontal_overflow", "duplicate_feed_card_count", "playing_video_count"):
            assert_true(field in vp, f"missing {key}.{field}")

    summary_text = summary_path.read_text()
    for marker in ("browser_tablet_", "browser_small_mobile_"):
        assert_true(marker in summary_text, f"summary missing marker: {marker}")
    assert_true("secret" not in summary_text.lower(), "summary leaked secret-like text")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
