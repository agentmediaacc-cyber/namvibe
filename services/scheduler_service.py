import os
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from services.job_queue_service import active_unique_job_exists, enqueue_unique_job

_TASKS = {}

DEFAULT_TASKS = [
    ("homepage_cache_warmup", "homepage_cache_warmup", 30),
    ("call_timeouts", "call_timeout_check", 30),
    ("notification_delivery", "notification_delivery", 15),
    ("safety_scans", "safety_scan", 60),
    ("payout_review", "payout_review", 300),
    ("media_cleanup", "media_cleanup", 3600),
    ("trust_score_recalculation", "trust_score_recalculation", 600),
]


def _now():
    return datetime.now(timezone.utc)


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _parse(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return _now()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return _now()


def _task(task_name, job_type, interval_seconds, payload=None, enabled=True):
    now = _now()
    return {
        "id": str(uuid.uuid4()),
        "task_name": task_name,
        "job_type": job_type,
        "schedule_type": "interval",
        "interval_seconds": int(interval_seconds),
        "payload": payload or {},
        "enabled": bool(enabled),
        "last_run_at": None,
        "next_run_at": _iso(now),
        "created_at": _iso(now),
        "updated_at": _iso(now),
    }


def _scheduled_unique_key(task):
    return f"scheduled:{task.get('job_type') or task['task_name']}"


def seed_default_tasks():
    for task_name, job_type, interval in DEFAULT_TASKS:
        _TASKS.setdefault(task_name, _task(task_name, job_type, interval))
    return {"ok": True, "tasks": list(deepcopy(_TASKS).values())}


def get_due_tasks():
    seed_default_tasks()
    now = _now()
    return [deepcopy(t) for t in _TASKS.values() if t.get("enabled") and _parse(t.get("next_run_at")) <= now]


def update_next_run(task_name):
    task = _TASKS.get(task_name)
    if not task:
        return {"ok": False, "error": "task_not_found"}
    now = _now()
    task["last_run_at"] = _iso(now)
    task["next_run_at"] = _iso(now + timedelta(seconds=int(task.get("interval_seconds") or 60)))
    task["updated_at"] = _iso(now)
    return {"ok": True, "task": deepcopy(task)}


def run_due_tasks():
    due = get_due_tasks()
    enqueued = []
    for task in due:
        unique_key = _scheduled_unique_key(task)
        if active_unique_job_exists(unique_key, job_type=task["job_type"]):
            enqueued.append({
                "ok": True,
                "job_id": None,
                "duplicate": False,
                "skipped": True,
                "reason": "active_job_exists",
                "unique_key": unique_key,
            })
            update_next_run(task["task_name"])
            continue
        result = enqueue_unique_job(
            task["job_type"],
            payload={**(task.get("payload") or {}), "_scheduled_task": task["task_name"]},
            unique_key=unique_key,
            priority=5,
        )
        enqueued.append(result)
        update_next_run(task["task_name"])
    return {"ok": True, "due_count": len(due), "enqueued": enqueued}


def enable_task(task_name):
    seed_default_tasks()
    task = _TASKS.get(task_name)
    if not task:
        return {"ok": False, "error": "task_not_found"}
    task["enabled"] = True
    task["updated_at"] = _iso(_now())
    return {"ok": True, "task": deepcopy(task)}


def disable_task(task_name):
    seed_default_tasks()
    task = _TASKS.get(task_name)
    if not task:
        return {"ok": False, "error": "task_not_found"}
    task["enabled"] = False
    task["updated_at"] = _iso(_now())
    return {"ok": True, "task": deepcopy(task)}


def get_scheduler_status():
    seed_default_tasks()
    return {
        "ok": True,
        "enabled": [deepcopy(t) for t in _TASKS.values() if t.get("enabled")],
        "tasks": list(deepcopy(_TASKS).values()),
        "fake_mode": os.getenv("CHAIN_TEST_FAKE_DB") == "1" or os.getenv("FLASK_TESTING") == "1",
    }
