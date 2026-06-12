#!/usr/bin/env python3
import contextlib
import io
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check(name, ok, detail=""):
    print(("PASS" if ok else "FAIL") + f": {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        raise AssertionError(name)


def timed(client, path, repeats=3, setup_session=None):
    samples = []
    statuses = []
    for _ in range(repeats):
        if setup_session:
            setup_session(client)
        started = time.perf_counter()
        response = client.get(path, follow_redirects=False)
        samples.append((time.perf_counter() - started) * 1000)
        statuses.append(response.status_code)
    return {
        "path": path,
        "statuses": statuses,
        "samples_ms": [round(v, 2) for v in samples],
        "best_ms": round(min(samples), 2),
        "median_ms": round(statistics.median(samples), 2),
    }


def apply_sql():
    sql_path = ROOT / "sql" / "phase_performance_hotfix.sql"
    check("performance SQL exists", sql_path.exists())
    sql = sql_path.read_text(encoding="utf-8")
    check("performance SQL is idempotent", "IF NOT EXISTS" in sql)
    from services.neon_service import write_query
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        write_query(stmt + ";", timeout_ms=20000)
    print("PASS: performance hotfix SQL applied")


def verify_indexes():
    from services.neon_service import fast_query
    rows = fast_query(
        """
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname IN (
            'idx_profiles_username',
            'idx_profiles_email',
            'idx_profiles_auth_user',
            'idx_follows_pair',
            'idx_jobs_status_run_after'
          )
        """,
        timeout_ms=5000,
        default=[],
    )
    found = {r.get("indexname") for r in rows}
    for name in {
        "idx_profiles_username",
        "idx_profiles_email",
        "idx_profiles_auth_user",
        "idx_follows_pair",
        "idx_jobs_status_run_after",
    }:
        check(f"index {name} exists", name in found)


def first_profile_id():
    from services.neon_service import fast_query
    rows = fast_query(
        "SELECT id, auth_user_id, email, username FROM chain_profiles WHERE deleted_at IS NULL ORDER BY created_at DESC NULLS LAST LIMIT 1",
        timeout_ms=5000,
        default=[],
    )
    return rows[0] if rows else None


def verify_scheduler_static():
    src = (ROOT / "services" / "job_queue_service.py").read_text(encoding="utf-8")
    check("scheduler insert uses ON CONFLICT DO NOTHING", "ON CONFLICT DO NOTHING" in src)
    check("scheduler unique enqueue avoids duplicate active jobs", "WHERE NOT EXISTS" in src and "payload->>'_unique_key'" in src)


def verify_scheduler_memory_dedupe():
    os.environ["CHAIN_TEST_FAKE_DB"] = "1"
    from services import job_queue_service
    job_queue_service._JOBS.clear()
    first = job_queue_service.enqueue_unique_job("perf_hotfix_test", payload={"x": 1}, unique_key="perf_hotfix")
    second = job_queue_service.enqueue_unique_job("perf_hotfix_test", payload={"x": 1}, unique_key="perf_hotfix")
    check("scheduler duplicate returns existing job", second.get("duplicate") is True and first.get("job_id") == second.get("job_id"))
    os.environ.pop("CHAIN_TEST_FAKE_DB", None)


def measure_routes(app):
    os.environ.setdefault("FLASK_TESTING", "1")
    app.config["TESTING"] = True
    profile = first_profile_id()
    check("profile available for friends timing", bool(profile and profile.get("id")))

    def set_profile_session(client):
        with client.session_transaction() as sess:
            sess["auth_user_id"] = profile.get("auth_user_id") or profile.get("id")
            sess["user_id"] = profile.get("auth_user_id") or profile.get("id")
            sess["auth_email"] = profile.get("email") or "perf@example.com"
            sess["email"] = profile.get("email") or "perf@example.com"
            sess["profile_id"] = profile.get("id")
            sess["username"] = profile.get("username") or "perf"

    captured = io.StringIO()
    with app.test_client() as client, contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        login = timed(client, "/auth/login", repeats=3)
        friends = timed(client, "/messages/api/friends", repeats=3, setup_session=set_profile_session)

    print(f"INFO: observed baseline login before hotfix: 1500-2500ms")
    print(f"INFO: observed baseline friends before hotfix: 2000ms+")
    print(f"INFO: login after hotfix samples ms: {login['samples_ms']} best={login['best_ms']} median={login['median_ms']}")
    print(f"INFO: friends after hotfix samples ms: {friends['samples_ms']} best={friends['best_ms']} median={friends['median_ms']}")
    check("/auth/login returns safely", all(s in {200, 302} for s in login["statuses"]), str(login["statuses"]))
    check("/messages/api/friends returns safely", all(s == 200 for s in friends["statuses"]), str(friends["statuses"]))
    check("login best timing below 700ms", login["best_ms"] < 700, str(login))
    check("friends best timing below 700ms", friends["best_ms"] < 700, str(friends))
    logs = captured.getvalue()
    check("no duplicate scheduler enqueue spam in route logs", "duplicate scheduler" not in logs.lower())
    return login, friends


def main():
    os.chdir(ROOT)
    os.environ.setdefault("FLASK_TESTING", "1")
    from app import app
    apply_sql()
    verify_indexes()
    verify_scheduler_static()
    verify_scheduler_memory_dedupe()
    measure_routes(app)
    print("PASS: performance hotfix checks complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
