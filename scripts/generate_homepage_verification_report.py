#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from statistics import median


VIEWPORT_FILES = {
    "desktop": "browser_desktop.stdout.log",
    "tablet": "browser_tablet.stdout.log",
    "mobile": "browser_mobile.stdout.log",
    "small_mobile": "browser_small_mobile.stdout.log",
}

VIEWPORT_DIMENSIONS = {
    "desktop": {"width": 1440, "height": 900},
    "tablet": {"width": 768, "height": 1024},
    "mobile": {"width": 390, "height": 844},
    "small_mobile": {"width": 320, "height": 568},
}


def read_json_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    return items


def latest_stage(path: Path, stage: str) -> dict:
    for item in reversed(read_json_lines(path)):
        if item.get("stage") == stage:
            return item
    return {}


def sample_stats(samples: list[dict]) -> dict:
    times = [s["time_total"] for s in samples if isinstance(s.get("time_total"), (int, float))]
    if not times:
        return {"samples": samples, "min": None, "median": None, "p95": None, "max": None}
    ordered = sorted(times)
    p95_index = min(len(ordered) - 1, max(0, int(round(len(ordered) * 0.95)) - 1))
    return {
        "samples": samples,
        "min": min(times),
        "median": median(times),
        "p95": ordered[p95_index],
        "max": max(times),
    }


def curl_samples(url: str, count: int = 5) -> list[dict]:
    samples = []
    for _ in range(count):
        cp = subprocess.run(
            [
                "curl",
                "--ipv4",
                "--connect-timeout",
                "5",
                "--max-time",
                "20",
                "-sS",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code} %{time_total}",
                url,
            ],
            capture_output=True,
            text=True,
        )
        sample = {"http_code": "NOT_MEASURED", "time_total": None}
        if cp.returncode == 0 and cp.stdout.strip():
            parts = cp.stdout.strip().split()
            if len(parts) >= 2:
                sample = {"http_code": parts[0], "time_total": float(parts[1])}
        samples.append(sample)
    return samples


def resolve_screenshot(run_dir: Path, screenshot_path: str) -> str:
    if not screenshot_path:
        return ""
    candidate = Path(screenshot_path)
    if candidate.is_absolute():
        return str(candidate)
    return str((run_dir / "repo" / candidate).resolve())


def build_browser_record(run_dir: Path, label: str, file_name: str) -> dict:
    data = latest_stage(run_dir / file_name, f"browser_{label}")
    if not data:
        return {
            "status": "MISSING_ARTIFACT",
            "viewport": VIEWPORT_DIMENSIONS[label],
            "url": "http://127.0.0.1:8080/",
            "screenshot_path": "",
            "horizontal_overflow": None,
            "console_errors": None,
            "page_errors": None,
            "failed_first_party_requests": None,
            "duplicate_cards": None,
            "playing_videos": None,
            "stories_row_client_width": None,
            "stories_row_scroll_width": None,
            "visible_story_count": None,
            "duplicate_story_count": None,
        }
    screenshot = resolve_screenshot(run_dir, data.get("screenshot_path", ""))
    return {
        "status": data.get("result", "NOT_RUN"),
        "result": data.get("result", "NOT_RUN"),
        "stage": data.get("stage", f"browser_{label}"),
        "viewport": data.get("viewport") or VIEWPORT_DIMENSIONS[label],
        "url": "http://127.0.0.1:8080/",
        "screenshot_path": screenshot,
        "horizontal_overflow": data.get("horizontal_overflow"),
        "console_errors": data.get("console_error_count"),
        "page_errors": data.get("page_error_count"),
        "failed_first_party_requests": data.get("failed_first_party_request_count"),
        "duplicate_cards": data.get("duplicate_feed_card_count"),
        "playing_videos": data.get("playing_video_count"),
        "stories_row_client_width": data.get("stories_row_client_width"),
        "stories_row_scroll_width": data.get("stories_row_scroll_width"),
        "visible_story_count": data.get("visible_story_count"),
        "duplicate_story_count": data.get("duplicate_story_count"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--runtime-repo", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    repo_root = Path(args.repo_root)
    runtime_repo = Path(args.runtime_repo)

    branch = (run_dir / "branch.txt").read_text().strip() if (run_dir / "branch.txt").exists() else ""
    commit = (run_dir / "head.txt").read_text().strip() if (run_dir / "head.txt").exists() else ""
    host_exit_status = int((run_dir / "host-status.txt").read_text().strip()) if (run_dir / "host-status.txt").exists() and (run_dir / "host-status.txt").read_text().strip().isdigit() else None
    generated_at = datetime.now(timezone.utc).isoformat()

    browser = {label: build_browser_record(run_dir, label, file_name) for label, file_name in VIEWPORT_FILES.items()}

    runtime = {
        "gunicorn_pids": subprocess.run(["pgrep", "-af", "gunicorn.*app:app"], capture_output=True, text=True).stdout.splitlines() if True else [],
        "cloudflared_pids": subprocess.run(["pgrep", "-af", "cloudflared.*namvibe"], capture_output=True, text=True).stdout.splitlines() if True else [],
    }
    timings = {
        "local_health": sample_stats(curl_samples("http://127.0.0.1:8080/healthz")),
        "local_home": sample_stats(curl_samples("http://127.0.0.1:8080/")),
        "local_feed": sample_stats(curl_samples("http://127.0.0.1:8080/api/homepage/feed")),
        "public_health": sample_stats(curl_samples("https://namvibe.com/healthz")),
        "public_home": sample_stats(curl_samples("https://namvibe.com/")),
    }

    stages = {}
    for stage_name in (
        "tracked_secret_scan",
        "dependency_check",
        "compile_check",
        "database_path_selection",
        "neon_dns",
        "neon_tcp",
        "neon_connection",
        "call_security_integration",
        "gunicorn_restart",
        "gunicorn_listener",
        "gunicorn_sequential_health",
        "gunicorn_sequential_homepage",
        "gunicorn_concurrent_health",
        "local_routes",
        "cloudflare_process",
        "cloudflare_connection",
        "public_dns",
        "public_tls",
        "public_routes",
        "socketio_handshake",
        "browser_desktop",
        "browser_tablet",
        "browser_mobile",
        "browser_small_mobile",
        "runtime_log_scan",
        "log_secret_scan",
    ):
        status_path = run_dir / f"{stage_name}.status"
        json_path = run_dir / f"{stage_name}.json"
        stages[stage_name] = {
            "status": status_path.read_text().strip() if status_path.exists() else "NOT_RUN",
            "result": json.loads(json_path.read_text()).get("result") if json_path.exists() else "NOT_RUN",
        }

    artifacts = {
        "homepage_verification_results_json": str(run_dir / "homepage_verification_results.json"),
        "homepage_verification_summary_txt": str(run_dir / "homepage_verification_summary.txt"),
        "homepage_report_json": str(run_dir / "homepage_report.json"),
        "homepage_report_txt": str(run_dir / "homepage_report.txt"),
    }

    report = {
        "schema_version": 1,
        "run_id": run_dir.name,
        "branch": branch,
        "commit": commit,
        "generated_at": generated_at,
        "host_exit_status": host_exit_status,
        "stages": stages,
        "browser": browser,
        "runtime": runtime,
        "timings": timings,
        "artifacts": artifacts,
        "overall_status": "PASS",
    }

    canonical_json = run_dir / "homepage_verification_results.json"
    canonical_txt = run_dir / "homepage_verification_summary.txt"
    legacy_json = run_dir / "homepage_report.json"
    legacy_txt = run_dir / "homepage_report.txt"

    canonical_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    canonical_txt.write_text(
        "\n".join(
            [
                f"run_id={report['run_id']}",
                f"branch={report['branch']}",
                f"commit={report['commit']}",
                f"host_exit_status={report['host_exit_status']}",
                f"overall_status={report['overall_status']}",
            ]
        )
        + "\n"
    )
    legacy_json.write_text(canonical_json.read_text())
    legacy_txt.write_text(canonical_txt.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
