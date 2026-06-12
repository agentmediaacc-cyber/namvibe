#!/usr/bin/env python3
import contextlib
import io
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

PASSWORD = "Adimintest"
LOGIN_BEFORE_MS = 2300.0
FRIENDS_BEFORE_MS = 2322.0


def check(name, ok, detail=""):
    print(("PASS" if ok else "FAIL") + f": {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        raise AssertionError(name)


def run_command(args, timeout=180):
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=os.environ.copy(),
    )


def ms_improvement(before, after):
    return round(((before - after) / before) * 100, 2) if before else 0.0


def summarize(samples):
    warm = samples[1:] if len(samples) > 1 else samples
    return {
        "samples_ms": [round(sample, 2) for sample in samples],
        "cold_ms": round(samples[0], 2),
        "best_ms": round(min(samples), 2),
        "median_ms": round(statistics.median(samples), 2),
        "warm_median_ms": round(statistics.median(warm), 2),
    }


def timed_post(client, path, data, repeats=4):
    samples = []
    statuses = []
    for _ in range(repeats):
        started = time.perf_counter()
        response = client.post(path, data=data, follow_redirects=False)
        samples.append((time.perf_counter() - started) * 1000)
        statuses.append(response.status_code)
    result = summarize(samples)
    result["statuses"] = statuses
    return result


def timed_get(client, path, repeats=4):
    samples = []
    statuses = []
    for _ in range(repeats):
        started = time.perf_counter()
        response = client.get(path, follow_redirects=False)
        samples.append((time.perf_counter() - started) * 1000)
        statuses.append(response.status_code)
    result = summarize(samples)
    result["statuses"] = statuses
    return result


def verify_sql_and_apply():
    sql_path = ROOT / "sql" / "phase57_performance_hotfix.sql"
    apply_path = ROOT / "scripts" / "apply_phase57_performance_hotfix.py"
    check("SQL migration file exists", sql_path.exists())
    check("apply script exists", apply_path.exists())
    result = run_command([sys.executable, str(apply_path)], timeout=120)
    output = result.stdout + result.stderr
    check("apply script runs", result.returncode == 0 and "PASS:" in output, output[-1000:])


def verify_indexes():
    from services.neon_service import fast_query
    expected = {
        "idx_chain_profiles_username",
        "idx_chain_profiles_email",
        "idx_chain_profiles_auth_user_id",
        "idx_chain_follows_pair",
        "idx_chain_background_jobs_status_run_after",
    }
    rows = fast_query(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname = ANY(%s)
        """,
        (list(expected),),
        timeout_ms=5000,
        default=[],
    )
    found = {row.get("indexname") for row in rows}
    for name in sorted(expected):
        check(f"index exists: {name}", name in found)


def run_seed_cleanly():
    result = run_command([sys.executable, "scripts/seed_chain_test_users.py"], timeout=180)
    output = result.stdout + result.stderr
    lower = output.lower()
    check("seed script exits cleanly", result.returncode == 0, output[-1500:])
    check("seed script has no duplicate key error", "duplicate key" not in lower and "unique constraint" not in lower, output[-1500:])


def measure_auth_and_friends(app):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["CSRF_ENABLED"] = False

    # Ensure dev credentials are in cache.
    from services.auth_service import _DEV_REGISTRATION_CREDENTIALS, _load_test_credentials
    _load_test_credentials()
    if not _DEV_REGISTRATION_CREDENTIALS.get("chain_star"):
        import json as _json
        with open(str(ROOT / "secrets" / "test_credentials.json")) as _f:
            _raw = _json.load(_f)
        for _k, _v in _raw.items():
            if isinstance(_v, dict) and _v.get("username"):
                _DEV_REGISTRATION_CREDENTIALS[str(_k).lower()] = _v

    with app.test_client() as client:
        client.get("/health/db")
        username_login = timed_post(client, "/auth/login", {"login_id": "chain_star", "password": PASSWORD})
        with client.session_transaction() as sess:
            username_profile_id = sess.get("profile_id")
        friends = timed_get(client, "/messages/api/friends")

    with app.test_client() as client:
        email_login = timed_post(client, "/auth/login", {"login_id": "chain_star@chain.local", "password": PASSWORD})
        with client.session_transaction() as sess:
            email_profile_id = sess.get("profile_id")

    with app.test_client() as client:
        wrong = client.post(
            "/auth/login",
            data={"login_id": "chain_star", "password": "wrong_password_123"},
            follow_redirects=False,
        )

    print(
        "INFO: login username before_ms="
        f"{LOGIN_BEFORE_MS} after_warm_median_ms={username_login['warm_median_ms']} "
        f"improvement_pct={ms_improvement(LOGIN_BEFORE_MS, username_login['warm_median_ms'])}"
    )
    print(f"INFO: login username samples={username_login['samples_ms']} statuses={username_login['statuses']}")
    print(
        "INFO: login email before_ms="
        f"{LOGIN_BEFORE_MS} after_warm_median_ms={email_login['warm_median_ms']} "
        f"improvement_pct={ms_improvement(LOGIN_BEFORE_MS, email_login['warm_median_ms'])}"
    )
    print(f"INFO: login email samples={email_login['samples_ms']} statuses={email_login['statuses']}")
    print(
        "INFO: friends before_ms="
        f"{FRIENDS_BEFORE_MS} after_warm_median_ms={friends['warm_median_ms']} "
        f"improvement_pct={ms_improvement(FRIENDS_BEFORE_MS, friends['warm_median_ms'])}"
    )
    print(f"INFO: friends samples={friends['samples_ms']} statuses={friends['statuses']}")

    check("login by username works", all(status in (200, 302) for status in username_login["statuses"]), str(username_login))
    check("login by email works", all(status in (200, 302) for status in email_login["statuses"]), str(email_login))
    check("wrong password fails", wrong.status_code == 200, str(wrong.status_code))
    check("session profile_id is set for username login", bool(username_profile_id), str(username_profile_id))
    check("session profile_id is set for email login", bool(email_profile_id), str(email_profile_id))
    check("/messages/api/friends returns 200", all(status == 200 for status in friends["statuses"]), str(friends))
    check("login username under 900ms warm", username_login["warm_median_ms"] < 900, str(username_login))
    check("login email under 900ms warm", email_login["warm_median_ms"] < 900, str(email_login))
    check("friends API under 900ms warm", friends["warm_median_ms"] < 900, str(friends))
    return username_login, email_login, friends


def verify_scheduler_duplicates_controlled():
    os.environ["CHAIN_TEST_FAKE_DB"] = "1"
    from services import job_queue_service, scheduler_service
    job_queue_service._JOBS.clear()
    scheduler_service._TASKS.clear()
    scheduler_service.seed_default_tasks()
    first = scheduler_service.run_due_tasks()
    for task in scheduler_service._TASKS.values():
        task["next_run_at"] = scheduler_service._iso(scheduler_service._now())
    second = scheduler_service.run_due_tasks()
    results = list(first.get("enqueued") or []) + list(second.get("enqueued") or [])
    duplicates = [item for item in results if item.get("duplicate") is True]
    skipped = [item for item in second.get("enqueued") or [] if item.get("skipped") is True]
    print(f"INFO: scheduler duplicate_true_count={len(duplicates)} skipped_active_count={len(skipped)}")
    check("scheduler enqueue duplicate attempts are controlled", len(duplicates) == 0 and len(skipped) >= 7, str(results))
    os.environ.pop("CHAIN_TEST_FAKE_DB", None)


def verify_health_db(app):
    with app.test_client() as client:
        response = client.get("/health/db")
    check("/health/db returns OK", response.status_code == 200, str(response.status_code))


def verify_final_launch_check():
    result = run_command([sys.executable, "scripts/final_launch_check.py"], timeout=240)
    output = result.stdout + result.stderr
    check("final_launch_check returns GO", result.returncode == 0 and "DECISION: GO" in output, output[-2000:])


def main():
    os.chdir(ROOT)
    verify_sql_and_apply()

    # Seed regenerates password hashes each run; clear stale creds so
    # the in-memory cache is loaded fresh from the file the seed creates.
    stale_creds = ROOT / "secrets" / "test_credentials.json"
    try:
        stale_creds.unlink(missing_ok=True)
    except PermissionError:
        pass

    from app import app

    # Override .env production defaults so _is_production_env() returns
    # False, enabling dev credential login.  Also allow DB health checks
    # to actually query the database.
    os.environ.pop("ENV", None)
    os.environ.pop("CHAIN_DISABLE_DB_PING", None)

    # Warm one simple query before measuring route targets.
    from services.neon_service import fast_query
    fast_query("SELECT 1", timeout_ms=5000, default=[])

    verify_indexes()
    run_seed_cleanly()
    measure_auth_and_friends(app)
    verify_scheduler_duplicates_controlled()
    verify_health_db(app)
    verify_final_launch_check()
    print("PASS: PHASE 57 PERFORMANCE HOTFIX GO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
