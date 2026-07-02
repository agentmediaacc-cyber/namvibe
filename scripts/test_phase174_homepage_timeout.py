#!/usr/bin/env python3
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app


HOMEPAGE_LIMIT_SECONDS = 3.0
HEALTH_LIMIT_SECONDS = 1.0
HOMEPAGE_RUNS = 3


def timed_get(client, path):
    started = time.perf_counter()
    response = client.get(path, follow_redirects=True)
    elapsed = time.perf_counter() - started
    return response, elapsed


def main():
    homepage_times = []

    with app.test_client() as client:
        for index in range(HOMEPAGE_RUNS):
            response, elapsed = timed_get(client, "/")
            homepage_times.append(elapsed)
            if response.status_code not in {200, 302}:
                print(f"FAIL homepage run {index + 1}: status={response.status_code} time={elapsed:.3f}s")
                return 1

        health_response, health_elapsed = timed_get(client, "/healthz")
        if health_response.status_code != 200:
            print(f"FAIL healthz: status={health_response.status_code} time={health_elapsed:.3f}s")
            return 1

    print("Homepage timings:", ", ".join(f"{value:.3f}s" for value in homepage_times))
    print(f"Homepage avg: {statistics.mean(homepage_times):.3f}s")
    print(f"Healthz: {health_elapsed:.3f}s")

    failures = []
    for index, elapsed in enumerate(homepage_times, start=1):
        if elapsed >= HOMEPAGE_LIMIT_SECONDS:
            failures.append(f"homepage run {index} exceeded {HOMEPAGE_LIMIT_SECONDS:.1f}s ({elapsed:.3f}s)")
    if health_elapsed >= HEALTH_LIMIT_SECONDS:
        failures.append(f"healthz exceeded {HEALTH_LIMIT_SECONDS:.1f}s ({health_elapsed:.3f}s)")

    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
