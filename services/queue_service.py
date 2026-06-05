import os
from rq import Queue
from services.redis_service import get_redis, queue_key

def get_queue(name='default'):
    """Returns an RQ Queue instance if Redis is available, else None."""
    r = get_redis()
    if r:
        return Queue(queue_key(name), connection=r)
    return None

def enqueue_job(function_path, *args, queue_name='default', **kwargs):
    """Enqueues a job to RQ if available, otherwise fallbacks to Neon background jobs."""
    q = get_queue(queue_name)
    if q:
        try:
            return q.enqueue(function_path, *args, **kwargs)
        except Exception as e:
            print(f"[queue_service] RQ enqueue failed: {e}")
    
    # Fallback to Neon (Simplified)
    from services.job_engine import enqueue_job as enqueue_neon_job
    return enqueue_neon_job(function_path, {"args": args, "kwargs": kwargs})

def queue_health():
    """Returns the health status of the Redis queue."""
    r = get_redis()
    if not r:
        return {"status": "unavailable", "reason": "Redis client not initialized"}
    try:
        from rq.registry import StartedJobRegistry
        q = Queue(queue_key("default"), connection=r)
        return {
            "status": "ok",
            "queue": queue_key("default"),
            "queued_jobs": len(q),
            "started_jobs": len(StartedJobRegistry(connection=r))
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
