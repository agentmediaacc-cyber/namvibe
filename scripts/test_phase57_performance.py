#!/usr/bin/env python3
import contextlib
import io
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

LOGIN_BEFORE_MS = 2000.0
FRIENDS_BEFORE_MS = 2000.0
SCHEDULER_DUPLICATES_BEFORE = 4
PASSWORD = "Adimintest"


def check(name, ok, detail=""):
    print(("PASS" if ok else "FAIL") + f": {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        raise AssertionError(name)


def improvement(before, after):
    if not before:
        return 0.0
    return round(((before - after) / before) * 100, 2)


def timed_get(client, path, repeats=5, setup_session=None):
    samples = []
    statuses = []
    for _ in range(repeats):
        if setup_session:
            setup_session(client)
        started = time.perf_counter()
        response = client.get(path, follow_redirects=False)
        samples.append((time.perf_counter() - started) * 1000)
        statuses.append(response.status_code)
    return summarize(path, statuses, samples)


def timed_post(client, path, data, repeats=5):
    samples = []
    statuses = []
    for _ in range(repeats):
        started = time.perf_counter()
        response = client.post(path, data=data, follow_redirects=False)
        samples.append((time.perf_counter() - started) * 1000)
        statuses.append(response.status_code)
    return summarize(path, statuses, samples)


def summarize(path, statuses, samples):
    warm = samples[1:] if len(samples) > 1 else samples
    return {
        "path": path,
        "statuses": statuses,
        "samples_ms": [round(v, 2) for v in samples],
        "cold_ms": round(samples[0], 2),
        "best_ms": round(min(samples), 2),
        "median_ms": round(statistics.median(samples), 2),
        "warm_median_ms": round(statistics.median(warm), 2),
    }


def apply_sql():
    sql_path = ROOT / "sql" / "phase57_performance_hardening.sql"
    check("phase57 SQL exists", sql_path.exists())
    sql = sql_path.read_text(encoding="utf-8")
    check("phase57 SQL is idempotent", "IF NOT EXISTS" in sql)
    from services.neon_service import write_query
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        write_query(stmt + ";", timeout_ms=20000)
    print("PASS: phase57 indexes applied")


def verify_indexes():
    from services.neon_service import fast_query
    expected = {
        "idx_chain_follows_pair",
        "idx_chain_follows_follower",
        "idx_chain_follows_following",
    }
    rows = fast_query(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'chain_follows'
          AND indexname = ANY(%s)
        """,
        (list(expected),),
        timeout_ms=5000,
        default=[],
    )
    found = {row.get("indexname") for row in rows}
    for name in sorted(expected):
        check(f"index {name} exists", name in found)


def phase57_profile():
    from services.neon_service import fast_query
    rows = fast_query(
        """
        SELECT id, auth_user_id, email, username
        FROM chain_profiles
        WHERE username = 'chain_star'
        LIMIT 1
        """,
        timeout_ms=5000,
        default=[],
    )
    if rows:
        return rows[0]
    rows = fast_query(
        """
        SELECT id, auth_user_id, email, username
        FROM chain_profiles
        WHERE deleted_at IS NULL
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
        """,
        timeout_ms=5000,
        default=[],
    )
    return rows[0] if rows else None


FRIENDS_SQL = """
SELECT p.id, p.username, p.full_name, p.avatar_url,
       p.is_verified, p.is_online
FROM chain_follows f1
JOIN chain_follows f2
    ON f1.follower_profile_id = f2.following_profile_id
   AND f1.following_profile_id = f2.follower_profile_id
JOIN chain_profiles p ON f1.following_profile_id = p.id
WHERE f1.follower_profile_id = %s
ORDER BY p.is_online DESC, p.full_name ASC
LIMIT 50
"""


def explain_friends(profile_id):
    from services.neon_service import fast_query
    rows = fast_query(
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + FRIENDS_SQL,
        (profile_id,),
        timeout_ms=5000,
        default=[],
    )
    check("EXPLAIN ANALYZE returned plan", bool(rows), str(rows))
    plan = rows[0].get("QUERY PLAN") if isinstance(rows[0], dict) else None
    if isinstance(plan, str):
        plan = json.loads(plan)
    if isinstance(plan, list) and plan:
        execution_ms = float(plan[0].get("Execution Time", 0.0))
        print(f"INFO: friends EXPLAIN ANALYZE execution_ms={round(execution_ms, 3)}")
        check("friends EXPLAIN ANALYZE below 300ms", execution_ms < 300, str(execution_ms))
        return execution_ms
    print(f"INFO: friends EXPLAIN ANALYZE raw={rows[:1]}")
    return None


def measure_routes(app, profile):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["CSRF_ENABLED"] = False

    def set_profile_session(client):
        with client.session_transaction() as sess:
            sess["auth_user_id"] = profile.get("auth_user_id") or profile.get("id")
            sess["user_id"] = profile.get("auth_user_id") or profile.get("id")
            sess["auth_email"] = profile.get("email") or "phase57@example.com"
            sess["email"] = profile.get("email") or "phase57@example.com"
            sess["profile_id"] = profile.get("id")
            sess["username"] = profile.get("username") or "phase57"

    from engines.cache_engine import cache_key, delete_cache
    delete_cache(cache_key("friends_list", profile.get("id")))

    captured = io.StringIO()
    with app.test_client() as client, contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        login = timed_post(client, "/auth/login", {"login_id": "chain_star", "password": PASSWORD}, repeats=5)
        friends = timed_get(client, "/messages/api/friends", repeats=5, setup_session=set_profile_session)

    print(f"INFO: login before_ms={LOGIN_BEFORE_MS} after_warm_median_ms={login['warm_median_ms']} improvement_pct={improvement(LOGIN_BEFORE_MS, login['warm_median_ms'])}")
    print(f"INFO: login samples={login['samples_ms']} statuses={login['statuses']}")
    print(f"INFO: friends before_ms={FRIENDS_BEFORE_MS} after_warm_median_ms={friends['warm_median_ms']} improvement_pct={improvement(FRIENDS_BEFORE_MS, friends['warm_median_ms'])}")
    print(f"INFO: friends samples={friends['samples_ms']} statuses={friends['statuses']}")

    logs = captured.getvalue().lower()
    check("POST /auth/login returns safely", all(status in {200, 302} for status in login["statuses"]), str(login))
    check("GET /messages/api/friends returns safely", all(status == 200 for status in friends["statuses"]), str(friends))
    check("login below 700ms", login["warm_median_ms"] < 700, str(login))
    check("friends below 500ms", friends["warm_median_ms"] < 500, str(friends))
    check("no duplicate=True route log spam", "duplicate=true" not in logs)
    return login, friends


def scheduler_duplicate_check():
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
    duplicate_count = sum(1 for item in results if item.get("duplicate") is True)
    skipped_count = sum(1 for item in second.get("enqueued") or [] if item.get("skipped") is True)
    after = float(duplicate_count)
    print(
        "INFO: scheduler before_duplicates="
        f"{SCHEDULER_DUPLICATES_BEFORE} after_duplicates={duplicate_count} "
        f"improvement_pct={improvement(float(SCHEDULER_DUPLICATES_BEFORE), after)} skipped_existing={skipped_count}"
    )
    check("scheduler duplicate count = 0", duplicate_count == 0, str(results))
    check("scheduler skipped active scheduled jobs", skipped_count >= 4, str(second))
    os.environ.pop("CHAIN_TEST_FAKE_DB", None)
    return duplicate_count


def verify_static_changes():
    auth_src = (ROOT / "services" / "auth_service.py").read_text(encoding="utf-8")
    scheduler_src = (ROOT / "services" / "scheduler_service.py").read_text(encoding="utf-8")
    jobs_src = (ROOT / "services" / "job_queue_service.py").read_text(encoding="utf-8")
    check("login lookup no longer selects wildcard in _find_login_profile", 'columns="*"' not in auth_src.split("def _find_login_profile", 1)[1].split("def _ensure_username", 1)[0])
    check("login has minimal credential column set", "LOGIN_PROFILE_COLUMNS" in auth_src and "password_hash" in auth_src and "is_active" in auth_src)
    check("scheduler preflights active scheduled jobs", "active_unique_job_exists" in scheduler_src)
    check("scheduler insert remains conflict-safe", "ON CONFLICT DO NOTHING" in jobs_src)


def main():
    os.chdir(ROOT)
    from app import app

    apply_sql()
    verify_indexes()
    verify_static_changes()
    profile = phase57_profile()
    check("profile available for phase57 benchmarks", bool(profile and profile.get("id")))
    explain_friends(profile["id"])
    measure_routes(app, profile)
    scheduler_duplicate_check()
    print("PASS: PHASE 57 PERFORMANCE HARDENING GO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
