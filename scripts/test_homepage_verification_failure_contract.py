#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_homepage_verification_report.py"


def validate(run_dir: Path) -> int:
    cp = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(run_dir / "homepage_verification_results.json"),
            "--run-dir",
            str(run_dir),
            "--canonical-summary",
            str(run_dir / "homepage_verification_summary.txt"),
            "--legacy-json",
            str(run_dir / "homepage_report.json"),
            "--legacy-summary",
            str(run_dir / "homepage_report.txt"),
        ],
        capture_output=True,
        text=True,
    )
    return cp.returncode


def write_stub(run_dir: Path) -> None:
    payload = json.dumps({"stage": "homepage_report", "result": "PASS", "exit_code": 0})
    for name in ("homepage_verification_results.json", "homepage_report.json"):
        (run_dir / name).write_text(payload)
    for name in ("homepage_verification_summary.txt", "homepage_report.txt"):
        (run_dir / name).write_text("verified_commit=\n")


def main() -> int:
    with TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        write_stub(run_dir)
        assert validate(run_dir) != 0
    
    with TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        (run_dir / "homepage_verification_results.json").write_text("{}")
        assert validate(run_dir) != 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
