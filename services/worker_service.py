import os
import time
from copy import deepcopy
from datetime import datetime, timezone

from services.job_handlers import HANDLERS
from services.job_queue_service import (
    complete_job,
    fail_job,
    get_next_job,
    lock_job,
    log_job_event,
)

_WORKERS = {}
_STOP = False


def _now():
    return datetime.now(timezone.utc).isoformat()


def _testing():
    return (
        os.getenv("FLASK_TESTING") == "1"
        or os.getenv("CHAIN_FAST_LOCAL") == "1"
        or os.getenv("CHAIN_TEST_FAKE_DB") == "1"
    )


def register_worker(worker_name, worker_type="default", metadata=None):
    worker = {
        "worker_name": worker_name,
        "worker_type": worker_type or "default",
        "status": "online",
        "current_job_id": None,
        "last_seen_at": _now(),
        "metadata": metadata or {},
        "created_at": _now(),
    }
    _WORKERS[worker_name] = worker
    return {"ok": True, "worker": deepcopy(worker)}


def heartbeat_worker(worker_name, current_job_id=None, status="online", metadata=None):
    worker = _WORKERS.get(worker_name) or register_worker(worker_name, "default").get("worker")
    worker["status"] = status or "online"
    worker["current_job_id"] = current_job_id
    worker["last_seen_at"] = _now()
    if metadata:
        worker["metadata"] = {**(worker.get("metadata") or {}), **metadata}
    _WORKERS[worker_name] = worker
    return {"ok": True, "worker": deepcopy(worker)}


def mark_worker_offline(worker_name):
    worker = _WORKERS.get(worker_name) or register_worker(worker_name, "default").get("worker")
    worker["status"] = "offline"
    worker["current_job_id"] = None
    worker["last_seen_at"] = _now()
    _WORKERS[worker_name] = worker
    return {"ok": True, "worker": deepcopy(worker)}


def dispatch_job(job):
    if not job:
        return {"ok": False, "error": "job_required"}
    handler = HANDLERS.get(job.get("job_type"))
    if not handler:
        return {"ok": False, "error": "unknown_job_type", "job_type": job.get("job_type")}
    return handler(job.get("payload") or {})


def run_worker_once(worker_name="worker-1", worker_type="default", queues=None):
    register_worker(worker_name, worker_type)
    heartbeat_worker(worker_name, status="online")
    job = get_next_job(queues=queues)
    if not job:
        return {"ok": True, "idle": True, "worker_name": worker_name}
    locked = lock_job(job["id"], worker_name)
    if not locked.get("ok"):
        return {"ok": False, "error": locked.get("error"), "worker_name": worker_name}
    job = locked["job"]
    heartbeat_worker(worker_name, current_job_id=job["id"], status="running")
    try:
        result = dispatch_job(job)
        if result.get("ok"):
            complete_job(job["id"], result)
        else:
            fail_job(job["id"], result.get("error", "handler_failed"))
        log_job_event(job["id"], job.get("job_type"), "info", "worker_dispatched_job", {"worker_name": worker_name, "result": result})
        return {"ok": True, "job": job, "result": result, "worker_name": worker_name}
    except Exception as error:
        fail_job(job["id"], str(error))
        return {"ok": False, "job": job, "error": str(error), "worker_name": worker_name}
    finally:
        heartbeat_worker(worker_name, current_job_id=None, status="online")


def run_worker_loop(worker_name="worker-1", worker_type="default", queues=None, interval=2, max_jobs=None):
    global _STOP
    register_worker(worker_name, worker_type)
    processed = 0
    while not _STOP:
        result = run_worker_once(worker_name, worker_type, queues=queues)
        if not result.get("idle"):
            processed += 1
        if max_jobs and processed >= int(max_jobs):
            break
        time.sleep(float(interval or 2))
    mark_worker_offline(worker_name)
    return {"ok": True, "processed": processed}


def get_worker_status(worker_name):
    worker = _WORKERS.get(worker_name)
    return deepcopy(worker) if worker else None


def get_all_worker_statuses():
    return [deepcopy(w) for w in _WORKERS.values()]
