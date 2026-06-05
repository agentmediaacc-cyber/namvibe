import uuid
import json
from datetime import datetime, timedelta, timezone
from services.neon_service import fast_query, transaction_query, write_query

VALID_QUEUES = {"critical", "realtime", "media", "notifications", "analytics", "maintenance", "default"}
RETRY_DELAYS = [60, 300, 900, 3600]

def enqueue_job(job_type, payload, run_after=None, queue_name="default", max_attempts=3, idempotency_key=None):
    """Enqueues a background job."""
    job_id = str(uuid.uuid4())
    sql = """
        INSERT INTO chain_background_jobs (id, job_type, payload, queue_name, max_attempts, run_after, status, created_at, idempotency_key)
        VALUES (%s, %s, %s, %s, %s, %s, 'queued', now(), %s)
        RETURNING id
    """
    if run_after is None:
        run_after = datetime.now(timezone.utc)
    queue_name = queue_name if queue_name in VALID_QUEUES else "default"
    return write_query(sql, (job_id, job_type, json.dumps(payload), queue_name, max(int(max_attempts or 3), 1), run_after, idempotency_key))

def claim_next_job(worker_id, queue_names=None):
    """Claims the next available job for a worker."""
    queue_names = [name for name in (queue_names or ["default"]) if name in VALID_QUEUES]
    def _callback(cursor):
        cursor.execute(
            """
            SELECT id
            FROM chain_background_jobs
            WHERE status IN ('queued', 'failed')
              AND attempts < max_attempts
              AND run_after <= now()
              AND queue_name = ANY(%s)
            ORDER BY run_after ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """,
            (queue_names,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        job_id = row["id"] if isinstance(row, dict) else row[0]
        cursor.execute(
            """
            UPDATE chain_background_jobs
            SET status = 'running', locked_at = now(), locked_by = %s, attempts = attempts + 1, updated_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (worker_id, job_id),
        )
        return cursor.fetchone()
    return transaction_query(_callback, timeout_ms=1500)

def complete_job(job_id):
    """Marks a job as completed."""
    sql = "UPDATE chain_background_jobs SET status = 'completed', completed_at = now(), updated_at = now() WHERE id = %s"
    return write_query(sql, (job_id,))

def fail_job(job_id, error):
    """Marks a job as failed or dead-lettered."""
    rows = fast_query(
        "SELECT attempts, max_attempts, error_history FROM chain_background_jobs WHERE id = %s LIMIT 1",
        (job_id,),
        timeout_ms=400,
        default=[],
    )
    if not rows:
        return None
    row = rows[0]
    attempts = int(row.get("attempts") or 0)
    max_attempts = int(row.get("max_attempts") or 1)
    history = row.get("error_history") or []
    if isinstance(history, str):
        try:
            history = json.loads(history)
        except Exception:
            history = []
    history.append({"error": str(error)[:240], "at": datetime.now(timezone.utc).isoformat()})
    if attempts >= max_attempts:
        sql = """
            UPDATE chain_background_jobs
            SET status = 'dead_letter',
                dead_letter_at = now(),
                dead_lettered_at = now(),
                dead_letter_reason = %s,
                last_error = %s,
                error_history = %s,
                locked_at = NULL,
                locked_by = NULL,
                updated_at = now()
            WHERE id = %s
        """
        return write_query(sql, (str(error)[:240], str(error)[:240], json.dumps(history), job_id))
    delay_seconds = RETRY_DELAYS[min(max(attempts - 1, 0), len(RETRY_DELAYS) - 1)]
    run_after = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    sql = """
        UPDATE chain_background_jobs
        SET status = 'failed',
            last_error = %s,
            error_history = %s,
            run_after = %s,
            retry_after = %s,
            retry_backoff_seconds = %s,
            locked_at = NULL,
            locked_by = NULL,
            updated_at = now()
        WHERE id = %s
    """
    return write_query(sql, (str(error)[:240], json.dumps(history), run_after, run_after, delay_seconds, job_id))


def recover_stuck_jobs(lock_timeout_seconds=300):
    return write_query(
        """
        UPDATE chain_background_jobs
        SET status = 'failed',
            locked_at = NULL,
            locked_by = NULL,
            last_error = COALESCE(last_error, 'worker_lock_timeout'),
            updated_at = now()
        WHERE status = 'running'
          AND locked_at < now() - (%s || ' seconds')::interval
        """,
        (int(lock_timeout_seconds),),
    )


def dead_letter_job(job_id, reason):
    return write_query(
        """
        UPDATE chain_background_jobs
        SET status = 'dead_letter',
            dead_letter_at = now(),
            dead_lettered_at = now(),
            dead_letter_reason = %s,
            last_error = %s,
            locked_at = NULL,
            locked_by = NULL,
            updated_at = now()
        WHERE id = %s
        """,
        (str(reason)[:240], str(reason)[:240], job_id),
    )

def run_due_jobs(limit=10):
    return fast_query(
        """
        SELECT id, job_type, queue_name, status, attempts, max_attempts
        FROM chain_background_jobs
        WHERE status IN ('queued', 'failed') AND run_after <= now()
        ORDER BY run_after ASC
        LIMIT %s
        """,
        (limit,),
        timeout_ms=500,
        default=[],
    )
