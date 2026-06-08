"""
Phase 49: Enterprise scaling, background jobs, Redis hardening, workers, scheduler.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"

from app import create_app

PASS = 0
FAIL = 0


def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}")
        PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" - {detail}" if detail else ""))
        FAIL += 1


print("\n=== 1. MIGRATION ===")
sql_path = "sql/phase49_enterprise_scaling_jobs.sql"
sql = open(sql_path).read() if os.path.exists(sql_path) else ""
check("migration exists", bool(sql))
for token in [
    "chain_background_jobs",
    "chain_job_logs",
    "chain_scheduled_tasks",
    "chain_worker_heartbeats",
    "chain_system_health_events",
    "CREATE INDEX IF NOT EXISTS",
    "call_timeouts",
    "notification_delivery",
    "safety_scans",
    "payout_review",
    "media_cleanup",
    "trust_score_recalculation",
]:
    check(f"migration has {token}", token in sql)


print("\n=== 2. QUEUE SERVICE ===")
from services.job_queue_service import (
    cancel_job,
    cleanup_old_jobs,
    complete_job,
    enqueue_job,
    enqueue_unique_job,
    fail_job,
    get_job,
    get_jobs,
    get_next_job,
    get_queue_stats,
    lock_job,
    log_job_event,
    retry_job,
)

job_res = enqueue_job("security_event_digest", {"profile_id": "phase49"}, priority=3)
jid = job_res.get("job_id")
check("enqueue job", job_res.get("ok") and jid)
unique1 = enqueue_unique_job("safety_scan", {"profile_id": "phase49"}, unique_key="phase49-safety")
unique2 = enqueue_unique_job("safety_scan", {"profile_id": "phase49"}, unique_key="phase49-safety")
check("enqueue unique job", unique1.get("ok") and unique2.get("duplicate") is True)
next_job = get_next_job()
check("get next job", bool(next_job and next_job.get("id")))
locked = lock_job(next_job["id"], "phase49-worker")
check("lock job", locked.get("ok") and locked["job"]["status"] == "running")
completed = complete_job(next_job["id"], {"done": True})
check("complete job", completed.get("ok") and completed["job"]["status"] == "completed")
fail_res = enqueue_job("security_event_digest", {}, priority=9)
locked_fail = lock_job(fail_res["job_id"], "phase49-worker")
failed = fail_job(fail_res["job_id"], "phase49 failure", retry=False)
check("fail job", locked_fail.get("ok") and failed.get("ok") and failed["job"]["status"] == "failed")
retry_res = retry_job(fail_res["job_id"])
check("retry job", retry_res.get("ok") and retry_res["job"]["status"] == "queued")
cancel_res = cancel_job(fail_res["job_id"])
check("cancel job", cancel_res.get("ok") and cancel_res["job"]["status"] == "cancelled")
check("get job", bool(get_job(jid)))
check("get jobs", isinstance(get_jobs(limit=5), list))
check("log job event", log_job_event(jid, "security_event_digest", "info", "phase49_test").get("ok"))
stats = get_queue_stats()
check("queue stats", stats.get("ok") and "queued" in stats.get("stats", {}))
check("cleanup old jobs", cleanup_old_jobs(days=0).get("ok"))


print("\n=== 3. REDIS HARDENING ===")
from services.redis_hardening_service import (
    get_redis_health,
    redis_available,
    safe_redis_delete,
    safe_redis_get,
    safe_redis_lpush,
    safe_redis_publish,
    safe_redis_rpop,
    safe_redis_set,
    safe_redis_subscribe_health,
)

check("Redis fallback health works", get_redis_health().get("ok") is True)
check("redis_available returns bool", isinstance(redis_available(), bool))
check("safe set", safe_redis_set("phase49:key", "value").get("ok"))
check("safe get", safe_redis_get("phase49:key") == "value")
check("safe delete", safe_redis_delete("phase49:key").get("ok"))
check("safe lpush", safe_redis_lpush("phase49:list", "item").get("ok"))
check("safe rpop", safe_redis_rpop("phase49:list") == "item")
check("safe publish", safe_redis_publish("phase49", "event").get("ok"))
check("subscribe health", safe_redis_subscribe_health().get("ok"))


print("\n=== 4. WORKERS AND HANDLERS ===")
from services.job_handlers import (
    handle_call_timeout_check,
    handle_media_cleanup,
    handle_notification_delivery,
    handle_payout_review,
    handle_push_retry,
    handle_safety_scan,
    handle_security_event_digest,
    handle_trust_score_recalculation,
    handle_wallet_risk_scan,
)
from services.worker_service import (
    get_all_worker_statuses,
    get_worker_status,
    heartbeat_worker,
    mark_worker_offline,
    register_worker,
    run_worker_once,
)

check("worker register", register_worker("phase49-worker", "default").get("ok"))
check("worker heartbeat", heartbeat_worker("phase49-worker").get("ok"))
enqueue_job("media_cleanup", {"dry_run": True}, priority=1)
run_once = run_worker_once("phase49-worker", "default")
check("worker run once", run_once.get("ok") and not run_once.get("idle"))
check("worker status", bool(get_worker_status("phase49-worker")))
check("all worker statuses", isinstance(get_all_worker_statuses(), list))
check("mark worker offline", mark_worker_offline("phase49-worker").get("ok"))
check("notification handler works", handle_notification_delivery().get("ok") is True)
check("call timeout handler works", handle_call_timeout_check().get("ok") in (True, False))
check("payout review handler works", handle_payout_review().get("ok") is True)
check("wallet risk handler works", handle_wallet_risk_scan({"profile_id": "phase49"}).get("ok") is True)
check("safety scan handler works", handle_safety_scan().get("ok") is True)
check("trust score handler works", handle_trust_score_recalculation({"profile_id": "phase49"}).get("ok") is True)
check("media cleanup handler works", handle_media_cleanup().get("ok") is True)
check("push retry handler works", handle_push_retry().get("ok") is True)
check("security digest handler works", handle_security_event_digest({"profile_id": "phase49"}).get("ok") is True)


print("\n=== 5. SCHEDULER ===")
from services.scheduler_service import (
    disable_task,
    enable_task,
    get_due_tasks,
    get_scheduler_status,
    run_due_tasks,
    seed_default_tasks,
    update_next_run,
)

seeded = seed_default_tasks()
check("scheduler seed tasks", seeded.get("ok") and len(seeded.get("tasks", [])) >= 6)
check("scheduler due tasks", isinstance(get_due_tasks(), list))
run_due = run_due_tasks()
check("run due scheduler", run_due.get("ok"))
check("update next run", update_next_run("call_timeouts").get("ok"))
check("disable task", disable_task("call_timeouts").get("ok"))
check("enable task", enable_task("call_timeouts").get("ok"))
check("scheduler status", get_scheduler_status().get("ok"))


print("\n=== 6. ROUTES AND HEALTH ===")
app = create_app()
client = app.test_client()
routes = {rule.rule for rule in app.url_map.iter_rules()}
for route in [
    "/system/api/health",
    "/system/api/queue/stats",
    "/system/api/workers",
    "/system/api/scheduled-tasks",
    "/system/api/scheduled-tasks/<task_name>/enable",
    "/system/api/scheduled-tasks/<task_name>/disable",
    "/system/api/jobs/enqueue-test",
    "/system/api/jobs/<job_id>",
    "/system/api/jobs/<job_id>/retry",
    "/system/api/jobs/<job_id>/cancel",
]:
    check(f"system route exists {route}", route in routes)

health = client.get("/system/api/health")
check("system health endpoint 200", health.status_code == 200)
health_json = health.get_json() or {}
check("health endpoint includes queue info", "job_queue" in (health_json.get("components") or {}))
healthz = client.get("/healthz")
check("healthz includes components", healthz.status_code == 200 and "components" in (healthz.get_json() or {}))
enqueue_api = client.post("/system/api/jobs/enqueue-test", json={"job_type": "media_cleanup"})
check("enqueue-test endpoint", enqueue_api.status_code == 200 and (enqueue_api.get_json() or {}).get("ok"))


print("\n=== 7. FILES AND INTEGRATIONS ===")
for path in [
    "scripts/run_worker.py",
    "scripts/run_scheduler.py",
    "scripts/queue_health.py",
    "templates/admin/system_health.html",
    "templates/admin/queue_dashboard.html",
    "templates/admin/workers.html",
    "templates/admin/scheduled_tasks.html",
    "docs/phase49_worker_deployment.md",
]:
    check(f"{path} exists", os.path.exists(path))

checks = [
    ("services/push_notification_service.py", "notification_delivery"),
    ("services/payout_service.py", "payout_review"),
    ("services/moderation_service.py", "safety_scan"),
    ("services/creator_monetization_service.py", "wallet_risk_scan"),
    ("services/message_delivery_service.py", "safety_scan"),
    ("services/socket_events.py", "message:send"),
]
for path, token in checks:
    src = open(path).read()
    check(f"{path} has {token}", token in src)

check("Phase 48 test file exists", os.path.exists("scripts/test_phase48_trust_safety.py"))
check("Phase 47 test file exists", os.path.exists("scripts/test_phase47_creator_wallet.py"))

total = PASS + FAIL
print("\n=== PHASE 49 SUMMARY ===")
print(f"  PASS: {PASS}/{total}  FAIL: {FAIL}/{total}")
if FAIL:
    raise SystemExit(1)
print("  All Phase 49 enterprise scaling tests passed!")
