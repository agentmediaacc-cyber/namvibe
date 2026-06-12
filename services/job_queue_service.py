import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from services.redis_hardening_service import safe_redis_lpush, get_redis_health

_JOBS = {}
_LOGS = []


def _now():
    return datetime.now(timezone.utc)


def _iso(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def _parse_time(value):
    if value is None:
        return _now()
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return _now()


def _testing():
    return (
        os.getenv("FLASK_TESTING") == "1"
        or os.getenv("CHAIN_FAST_LOCAL") == "1"
        or os.getenv("CHAIN_TEST_FAKE_DB") == "1"
    )


def _db_available():
    if _testing():
        return False
    try:
        from services.neon_service import get_pool_status
        return bool(get_pool_status().get("configured"))
    except Exception:
        return False


def _row_to_job(row):
    if not row:
        return None
    job = dict(row)
    payload = job.get("payload")
    if isinstance(payload, str):
        try:
            job["payload"] = json.loads(payload)
        except Exception:
            job["payload"] = {}
    job.setdefault("payload", {})
    for key in ("run_after", "started_at", "finished_at", "locked_at", "created_at", "updated_at"):
        job[key] = _iso(job.get(key))
    return job


def _memory_job(job_id):
    job = _JOBS.get(str(job_id))
    return deepcopy(job) if job else None


def active_unique_job_exists(unique_key, job_type=None):
    if not unique_key:
        return False
    for job in _JOBS.values():
        if job.get("payload", {}).get("_unique_key") != unique_key:
            continue
        if job_type and job.get("job_type") != job_type:
            continue
        if job.get("status") in {"queued", "running"}:
            return True
    if not _db_available():
        return False
    try:
        from services.neon_service import fast_query
        if job_type:
            rows = fast_query(
                """SELECT id
                   FROM chain_background_jobs
                   WHERE payload->>'_unique_key' = %s
                     AND job_type = %s
                     AND status IN ('queued', 'running')
                   LIMIT 1""",
                (unique_key, job_type),
                timeout_ms=500,
                default=[],
            )
        else:
            rows = fast_query(
                """SELECT id
                   FROM chain_background_jobs
                   WHERE payload->>'_unique_key' = %s
                     AND status IN ('queued', 'running')
                   LIMIT 1""",
                (unique_key,),
                timeout_ms=500,
                default=[],
            )
        return bool(rows)
    except Exception:
        return False


def enqueue_job(job_type, payload=None, priority=5, run_after=None, max_attempts=3, queue="default"):
    payload = payload or {}
    run_at = _parse_time(run_after)
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "job_type": str(job_type),
        "status": "queued",
        "priority": int(priority or 5),
        "payload": dict(payload),
        "attempts": 0,
        "max_attempts": int(max_attempts or 3),
        "locked_by": None,
        "locked_at": None,
        "run_after": _iso(run_at),
        "started_at": None,
        "finished_at": None,
        "error_message": None,
        "created_at": _iso(_now()),
        "updated_at": _iso(_now()),
        "queue": queue,
        "backend": "memory",
    }
    if _db_available():
        try:
            from services.neon_service import fast_query, write_query
            if payload.get("_unique_key"):
                row = write_query(
                    """INSERT INTO chain_background_jobs
                       (id, job_type, status, priority, payload, max_attempts, run_after)
                       SELECT %s,%s,'queued',%s,%s::jsonb,%s,%s
                       WHERE NOT EXISTS (
                           SELECT 1
                           FROM chain_background_jobs
                           WHERE payload->>'_unique_key' = %s
                             AND status IN ('queued', 'running')
                       )
                       ON CONFLICT DO NOTHING
                       RETURNING *""",
                    (
                        job_id,
                        job_type,
                        int(priority or 5),
                        json.dumps(payload),
                        int(max_attempts or 3),
                        run_at,
                        payload.get("_unique_key"),
                    ),
                )
            else:
                row = write_query(
                    """INSERT INTO chain_background_jobs
                       (id, job_type, status, priority, payload, max_attempts, run_after)
                       VALUES (%s,%s,'queued',%s,%s::jsonb,%s,%s)
                       ON CONFLICT DO NOTHING
                       RETURNING *""",
                    (job_id, job_type, int(priority or 5), json.dumps(payload), int(max_attempts or 3), run_at),
                )
            if row:
                job = _row_to_job(row[0] if isinstance(row, list) else row)
                job["backend"] = "database"
            elif payload.get("_unique_key"):
                job["duplicate"] = True
        except Exception as error:
            job["error_message"] = str(error)
    final_job_id = str(job.get("id") or job_id)
    _JOBS[final_job_id] = deepcopy(job)
    if not job.get("duplicate"):
        safe_redis_lpush(f"chain:jobs:{queue}", final_job_id)
        log_job_event(final_job_id, job_type, "info", "job_queued", {"queue": queue})
    return {"ok": True, "job": deepcopy(job), "job_id": final_job_id, "duplicate": bool(job.get("duplicate"))}


def enqueue_unique_job(job_type, payload=None, unique_key=None, priority=5, run_after=None, max_attempts=3, queue="default"):
    payload = payload or {}
    unique_key = unique_key or json.dumps({"job_type": job_type, "payload": payload}, sort_keys=True)
    for job in _JOBS.values():
        if job.get("payload", {}).get("_unique_key") == unique_key and job.get("status") in {"queued", "running"}:
            return {"ok": True, "job": deepcopy(job), "job_id": job["id"], "duplicate": True}
    payload = dict(payload)
    payload["_unique_key"] = unique_key
    result = enqueue_job(job_type, payload, priority=priority, run_after=run_after, max_attempts=max_attempts, queue=queue)
    result["duplicate"] = bool(result.get("duplicate"))
    return result


def get_next_job(queues=None):
    queues = set(queues or [])
    now = _now()
    candidates = []
    for job in _JOBS.values():
        if job.get("status") != "queued":
            continue
        if queues and job.get("queue", "default") not in queues and job.get("job_type") not in queues:
            continue
        if _parse_time(job.get("run_after")) <= now:
            candidates.append(job)
    candidates.sort(key=lambda j: (int(j.get("priority", 5)), _parse_time(j.get("run_after")), _parse_time(j.get("created_at"))))
    return deepcopy(candidates[0]) if candidates else None


def lock_job(job_id, worker_name="worker"):
    job = _JOBS.get(str(job_id))
    if not job or job.get("status") != "queued":
        return {"ok": False, "error": "job_not_available"}
    job["status"] = "running"
    job["locked_by"] = worker_name
    job["locked_at"] = _iso(_now())
    job["started_at"] = _iso(_now())
    job["attempts"] = int(job.get("attempts") or 0) + 1
    job["updated_at"] = _iso(_now())
    log_job_event(job_id, job.get("job_type"), "info", "job_locked", {"worker_name": worker_name})
    return {"ok": True, "job": deepcopy(job)}


def complete_job(job_id, result=None):
    job = _JOBS.get(str(job_id))
    if not job:
        return {"ok": False, "error": "job_not_found"}
    job["status"] = "completed"
    job["finished_at"] = _iso(_now())
    job["updated_at"] = _iso(_now())
    job["payload"] = {**(job.get("payload") or {}), "_result": result or {}}
    log_job_event(job_id, job.get("job_type"), "info", "job_completed", {"result": result or {}})
    return {"ok": True, "job": deepcopy(job)}


def fail_job(job_id, error_message, retry=True):
    job = _JOBS.get(str(job_id))
    if not job:
        return {"ok": False, "error": "job_not_found"}
    job["error_message"] = str(error_message)
    if retry and int(job.get("attempts") or 0) < int(job.get("max_attempts") or 3):
        return retry_job(job_id, error_message=error_message)
    job["status"] = "failed"
    job["finished_at"] = _iso(_now())
    job["updated_at"] = _iso(_now())
    log_job_event(job_id, job.get("job_type"), "error", "job_failed", {"error": str(error_message)})
    return {"ok": True, "job": deepcopy(job)}


def retry_job(job_id, error_message=None):
    job = _JOBS.get(str(job_id))
    if not job:
        return {"ok": False, "error": "job_not_found"}
    attempts = int(job.get("attempts") or 0)
    if attempts >= int(job.get("max_attempts") or 3):
        job["status"] = "failed"
        return {"ok": False, "error": "max_attempts_reached", "job": deepcopy(job)}
    delay = min(300, 2 ** max(attempts, 0))
    job["status"] = "queued"
    job["locked_by"] = None
    job["locked_at"] = None
    job["run_after"] = _iso(_now() + timedelta(seconds=delay))
    job["error_message"] = str(error_message) if error_message else job.get("error_message")
    job["updated_at"] = _iso(_now())
    log_job_event(job_id, job.get("job_type"), "warning", "job_retry_scheduled", {"delay_seconds": delay})
    return {"ok": True, "job": deepcopy(job)}


def cancel_job(job_id):
    job = _JOBS.get(str(job_id))
    if not job:
        return {"ok": False, "error": "job_not_found"}
    if job.get("status") in {"completed", "cancelled"}:
        return {"ok": True, "job": deepcopy(job)}
    job["status"] = "cancelled"
    job["finished_at"] = _iso(_now())
    job["updated_at"] = _iso(_now())
    log_job_event(job_id, job.get("job_type"), "warning", "job_cancelled", {})
    return {"ok": True, "job": deepcopy(job)}


def get_job(job_id):
    return _memory_job(job_id)


def get_jobs(status=None, job_type=None, limit=100):
    rows = list(_JOBS.values())
    if status:
        rows = [j for j in rows if j.get("status") == status]
    if job_type:
        rows = [j for j in rows if j.get("job_type") == job_type]
    rows.sort(key=lambda j: _parse_time(j.get("created_at")), reverse=True)
    return deepcopy(rows[: int(limit or 100)])


def log_job_event(job_id, job_type, level="info", message="", metadata=None):
    event = {
        "id": str(uuid.uuid4()),
        "job_id": str(job_id) if job_id else None,
        "job_type": str(job_type),
        "level": level or "info",
        "message": message or "",
        "metadata": metadata or {},
        "created_at": _iso(_now()),
    }
    _LOGS.append(event)
    return {"ok": True, "log": deepcopy(event)}


def get_queue_stats():
    stats = {"queued": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0, "total": 0}
    by_type = {}
    for job in _JOBS.values():
        status = job.get("status", "queued")
        stats[status] = stats.get(status, 0) + 1
        stats["total"] += 1
        by_type[job.get("job_type")] = by_type.get(job.get("job_type"), 0) + 1
    return {"ok": True, "stats": stats, "by_type": by_type, "redis": get_redis_health(), "db_fallback": not _db_available()}


def cleanup_old_jobs(days=7):
    cutoff = _now() - timedelta(days=int(days or 7))
    removed = []
    for job_id, job in list(_JOBS.items()):
        if job.get("status") in {"completed", "failed", "cancelled"} and _parse_time(job.get("finished_at") or job.get("updated_at")) < cutoff:
            removed.append(job_id)
            _JOBS.pop(job_id, None)
    return {"ok": True, "removed": len(removed)}
