#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        raise ValueError(f"invalid_json:{path}:{exc}") from exc


def validate(report: dict, run_dir: Path) -> None:
    required = [
        "schema_version",
        "run_id",
        "branch",
        "commit",
        "generated_at",
        "host_exit_status",
        "stages",
        "browser",
        "runtime",
        "timings",
        "artifacts",
        "overall_status",
    ]
    for key in required:
        if key not in report:
            raise ValueError(f"missing_key:{key}")
    if report["schema_version"] != 1:
        raise ValueError("bad_schema_version")
    if not report["run_id"] or report["run_id"] != run_dir.name:
        raise ValueError("run_id_mismatch")
    if not report["branch"]:
        raise ValueError("empty_branch")
    if not report["commit"] or not COMMIT_RE.match(report["commit"]):
        raise ValueError("bad_commit")
    head_path = run_dir / "head.txt"
    branch_path = run_dir / "branch.txt"
    if head_path.exists() and head_path.read_text().strip() != report["commit"]:
        raise ValueError("report_commit_mismatch")
    if branch_path.exists() and branch_path.read_text().strip() != report["branch"]:
        raise ValueError("report_branch_mismatch")
    if report["host_exit_status"] != 0:
        raise ValueError("bad_host_exit_status")
    if report["overall_status"] != "PASS":
        raise ValueError("bad_overall_status")
    if not isinstance(report["stages"], dict) or not report["stages"]:
        raise ValueError("bad_stages")
    if not isinstance(report["runtime"], dict):
        raise ValueError("bad_runtime")
    if not isinstance(report["timings"], dict):
        raise ValueError("bad_timings")
    if not isinstance(report["artifacts"], dict):
        raise ValueError("bad_artifacts")
    browser = report["browser"]
    if not isinstance(browser, dict):
        raise ValueError("bad_browser")
    expected = {
        "desktop": {"width": 1440, "height": 900},
        "tablet": {"width": 768, "height": 1024},
        "mobile": {"width": 390, "height": 844},
        "small_mobile": {"width": 320, "height": 568},
    }
    for label, dims in expected.items():
        if label not in browser:
            raise ValueError(f"missing_viewport:{label}")
        vp = browser[label]
        if vp.get("status") != "PASS":
            raise ValueError(f"bad_viewport_status:{label}")
        if vp.get("viewport") != dims:
            raise ValueError(f"bad_viewport_dims:{label}")
        screenshot = vp.get("screenshot_path")
        if not screenshot:
            raise ValueError(f"missing_screenshot:{label}")
        screenshot_path = Path(screenshot)
        if not screenshot_path.exists():
            raise ValueError(f"missing_screenshot_file:{label}")
        if run_dir not in screenshot_path.parents:
            raise ValueError(f"cross_run_screenshot:{label}")
        for field in ("horizontal_overflow", "console_errors", "page_errors", "failed_first_party_requests", "duplicate_cards", "playing_videos"):
            value = vp.get(field)
            if not isinstance(value, int):
                raise ValueError(f"bad_numeric:{label}.{field}")
            if value < 0:
                raise ValueError(f"negative:{label}.{field}")
        for field in ("duplicate_cards", "playing_videos", "horizontal_overflow", "console_errors", "page_errors", "failed_first_party_requests"):
            if vp.get(field) != 0:
                raise ValueError(f"nonzero:{label}.{field}")
        for field in ("stories_row_client_width", "stories_row_scroll_width", "visible_story_count", "duplicate_story_count"):
            if field in vp and vp[field] is not None and not isinstance(vp[field], int):
                raise ValueError(f"bad_optional_numeric:{label}.{field}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report_json")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--legacy-json")
    parser.add_argument("--legacy-summary")
    parser.add_argument("--canonical-summary")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    report_path = Path(args.report_json)
    report = load_json(report_path)
    validate(report, run_dir)
    if args.legacy_json:
        legacy_json = load_json(Path(args.legacy_json))
        if legacy_json != report:
            raise ValueError("legacy_json_mismatch")
    if args.canonical_summary and args.legacy_summary:
        canonical_text = Path(args.canonical_summary).read_text()
        legacy_text = Path(args.legacy_summary).read_text()
        if canonical_text != legacy_text:
            raise ValueError("legacy_summary_mismatch")
        if "overall_status=PASS" not in canonical_text:
            raise ValueError("missing_text_summary_status")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        raise SystemExit(f"validation_failed:{exc}")
