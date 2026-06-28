#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("FLASK_ENV", "development")

from app import create_app

ROUTES = [
    "/",
    "/reels/",
    "/search",
    "/healthz",
    "/health/db",
    "/health/redis",
    "/health/supabase",
]

REQUIRED_ENV_VARS = [
    "SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
]


def _benchmark_route(client, path, runs=3):
    timings = []
    statuses = []
    for _ in range(runs):
        started = time.perf_counter()
        response = client.get(path, follow_redirects=False)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        timings.append(elapsed_ms)
        statuses.append(response.status_code)
    return {
        "path": path,
        "runs": runs,
        "statuses": statuses,
        "min_ms": min(timings),
        "max_ms": max(timings),
        "avg_ms": round(sum(timings) / len(timings), 2),
        "last_ms": timings[-1],
    }


def main():
    app = create_app()
    failures = []

    print("ENV")
    for key in REQUIRED_ENV_VARS:
        present = bool(os.environ.get(key))
        print(f"[{'PASS' if present else 'WARN'}] {key}")

    dockerfile = ROOT / "Dockerfile"
    render_yaml = ROOT / "render.yaml"
    print("DEPLOY")
    print(f"[{'PASS' if dockerfile.exists() else 'WARN'}] Dockerfile")
    print(f"[{'PASS' if render_yaml.exists() else 'WARN'}] render.yaml")

    print("BENCHMARK")
    with app.test_client() as client:
        for path in ROUTES:
            result = _benchmark_route(client, path)
            ok = all(status != 500 for status in result["statuses"])
            print(
                f"[{'PASS' if ok else 'FAIL'}] {path} "
                f"avg={result['avg_ms']}ms min={result['min_ms']}ms max={result['max_ms']}ms "
                f"statuses={result['statuses']}"
            )
            if not ok:
                failures.append(path)

    if failures:
        print("FAIL")
        for path in failures:
            print(path)
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
