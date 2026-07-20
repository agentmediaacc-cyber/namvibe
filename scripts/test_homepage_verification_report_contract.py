#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_homepage_verification_report.py"


def run_validator(run_dir: Path, report_path: Path, legacy_json: Path | None = None, legacy_summary: Path | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(VALIDATOR),
        str(report_path),
        "--run-dir",
        str(run_dir),
        "--canonical-summary",
        str(run_dir / "homepage_verification_summary.txt"),
    ]
    if legacy_json is not None:
        cmd.extend(["--legacy-json", str(legacy_json)])
    if legacy_summary is not None:
        cmd.extend(["--legacy-summary", str(legacy_summary)])
    return subprocess.run(cmd, capture_output=True, text=True)


def screenshot(run_dir: Path, name: str) -> Path:
    path = run_dir / name
    path.write_bytes(b"stub")
    return path


def valid_report(run_dir: Path) -> dict:
    screenshots = {
        "desktop": screenshot(run_dir, "desktop.png"),
        "tablet": screenshot(run_dir, "tablet.png"),
        "mobile": screenshot(run_dir, "mobile.png"),
        "small_mobile": screenshot(run_dir, "small_mobile.png"),
    }
    browser = {}
    dimensions = {
        "desktop": {"width": 1440, "height": 900},
        "tablet": {"width": 768, "height": 1024},
        "mobile": {"width": 390, "height": 844},
        "small_mobile": {"width": 320, "height": 568},
    }
    for label, dims in dimensions.items():
        browser[label] = {
            "status": "PASS",
            "result": "PASS",
            "viewport": dims,
            "url": "http://127.0.0.1:8080/",
            "screenshot_path": str(screenshots[label]),
            "horizontal_overflow": 0,
            "console_errors": 0,
            "page_errors": 0,
            "failed_first_party_requests": 0,
            "duplicate_cards": 0,
            "playing_videos": 0,
            "stories_row_client_width": None,
            "stories_row_scroll_width": None,
            "visible_story_count": None,
            "duplicate_story_count": None,
        }
    return {
        "schema_version": 1,
        "run_id": run_dir.name,
        "branch": "phase-homepage-production-fix",
        "commit": "b27f3f5b3b5ce2dd7d0f8c5a0d47fd4fda9d7b76",
        "generated_at": "2026-07-20T13:00:00Z",
        "host_exit_status": 0,
        "stages": {"runtime_log_scan": {"status": "PASS", "result": "PASS"}},
        "browser": browser,
        "runtime": {"gunicorn_pids": ["gunicorn 1"], "cloudflared_pids": ["cloudflared 2"]},
        "timings": {
            "local_health": {"samples": [{"http_code": "200", "time_total": 0.11}], "min": 0.11, "median": 0.11, "p95": 0.11, "max": 0.11},
            "local_home": {"samples": [{"http_code": "200", "time_total": 0.21}], "min": 0.21, "median": 0.21, "p95": 0.21, "max": 0.21},
            "local_feed": {"samples": [{"http_code": "200", "time_total": 0.31}], "min": 0.31, "median": 0.31, "p95": 0.31, "max": 0.31},
            "public_health": {"samples": [{"http_code": "200", "time_total": 0.41}], "min": 0.41, "median": 0.41, "p95": 0.41, "max": 0.41},
            "public_home": {"samples": [{"http_code": "200", "time_total": 0.51}], "min": 0.51, "median": 0.51, "p95": 0.51, "max": 0.51},
        },
        "artifacts": {
            "homepage_verification_results_json": str(run_dir / "homepage_verification_results.json"),
            "homepage_verification_summary_txt": str(run_dir / "homepage_verification_summary.txt"),
            "homepage_report_json": str(run_dir / "homepage_report.json"),
            "homepage_report_txt": str(run_dir / "homepage_report.txt"),
        },
        "overall_status": "PASS",
    }


def write_report(run_dir: Path, report: dict) -> None:
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    (run_dir / "homepage_verification_results.json").write_text(payload)
    (run_dir / "homepage_report.json").write_text(payload)
    summary = "\n".join(
        [
            f"run_id={report['run_id']}",
            f"branch={report['branch']}",
            f"commit={report['commit']}",
            f"host_exit_status={report['host_exit_status']}",
            f"overall_status={report['overall_status']}",
        ]
    ) + "\n"
    (run_dir / "homepage_verification_summary.txt").write_text(summary)
    (run_dir / "homepage_report.txt").write_text(summary)


def main() -> int:
    with TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        report = valid_report(run_dir)
        write_report(run_dir, report)
        completed = run_validator(run_dir, run_dir / "homepage_verification_results.json", run_dir / "homepage_report.json", run_dir / "homepage_report.txt")
        assert completed.returncode == 0, completed.stderr

    with TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        report = valid_report(run_dir)
        report["browser"].pop("tablet")
        write_report(run_dir, report)
        completed = run_validator(run_dir, run_dir / "homepage_verification_results.json", run_dir / "homepage_report.json", run_dir / "homepage_report.txt")
        assert completed.returncode != 0

    with TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        (run_dir / "homepage_verification_results.json").write_text(json.dumps({"stage": "homepage_report", "result": "PASS"}) + "\n")
        (run_dir / "homepage_report.json").write_text(json.dumps({"stage": "homepage_report", "result": "PASS"}) + "\n")
        (run_dir / "homepage_verification_summary.txt").write_text("verified_commit=\n")
        (run_dir / "homepage_report.txt").write_text("verified_commit=\n")
        completed = run_validator(run_dir, run_dir / "homepage_verification_results.json", run_dir / "homepage_report.json", run_dir / "homepage_report.txt")
        assert completed.returncode != 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
