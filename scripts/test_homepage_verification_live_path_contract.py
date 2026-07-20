#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_homepage_verification_report.py"


def run_validator(run_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(run_dir / "homepage_verification_results.json"),
            "--run-dir",
            str(run_dir),
            "--legacy-json",
            str(run_dir / "homepage_report.json"),
            "--legacy-summary",
            str(run_dir / "homepage_report.txt"),
            "--canonical-summary",
            str(run_dir / "homepage_verification_summary.txt"),
        ],
        capture_output=True,
        text=True,
    )


def main() -> int:
    with TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        (run_dir / "desktop.png").write_bytes(b"stub")
        report = {
            "schema_version": 1,
            "run_id": run_dir.name,
            "branch": "phase-homepage-production-fix",
            "commit": "b27f3f5b3b5ce2dd7d0f8c5a0d47fd4fda9d7b76",
            "generated_at": "2026-07-20T13:00:00Z",
            "host_exit_status": 0,
            "stages": {"runtime_log_scan": {"status": "PASS", "result": "PASS"}},
            "browser": {
                "desktop": {
                    "status": "PASS",
                    "viewport": {"width": 1440, "height": 900},
                    "url": "http://127.0.0.1:8080/",
                    "screenshot_path": str(run_dir / "desktop.png"),
                    "horizontal_overflow": 0,
                    "console_errors": 0,
                    "page_errors": 0,
                    "failed_first_party_requests": 0,
                    "duplicate_cards": 0,
                    "playing_videos": 0,
                }
            },
            "runtime": {"gunicorn_pids": [], "cloudflared_pids": []},
            "timings": {},
            "artifacts": {},
            "overall_status": "PASS",
        }
        payload = json.dumps(report)
        for name in ("homepage_verification_results.json", "homepage_report.json"):
            (run_dir / name).write_text(payload)
        (run_dir / "homepage_verification_summary.txt").write_text("ok\n")
        (run_dir / "homepage_report.txt").write_text("ok\n")
        completed = run_validator(run_dir)
        assert completed.returncode != 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
