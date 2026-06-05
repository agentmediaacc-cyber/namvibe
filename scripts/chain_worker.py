import argparse
import json
import os
import time
import traceback

from services.job_engine import claim_next_job, complete_job, fail_job, recover_stuck_jobs
from services.presence_engine import sync_presence_to_neon

WORKER_ID = f"worker-{os.getpid()}"
DEFAULT_QUEUES = ["critical", "realtime", "media", "notifications", "analytics", "maintenance", "default"]


def _job_payload(job):
    payload = job.get("payload")
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception:
            return payload
    return payload


def process_job(job):
    job_type = job["job_type"]
    payload = _job_payload(job)
    print(f"[{WORKER_ID}] Processing job {job['id']} of type {job_type}")

    if job_type in {"cleanup_typing", "cleanup_typing_state"}:
        return True, None

    if job_type in {"cleanup_expired_status", "cleanup_expired_status_posts"}:
        return True, None

    if job_type == "recalculate_profile_counts":
        return True, None

    if job_type in {"process_reel", "services.media_pipeline.process_reel_metadata_job"}:
        from services.media_pipeline import process_reel_job, process_reel_metadata_job
        reel_id = payload["args"][0] if isinstance(payload, dict) and payload.get("args") else payload
        if job_type == "process_reel":
            process_reel_job(reel_id)
        else:
            process_reel_metadata_job(reel_id)
        return True, None

    if job_type in {"process_reel_thumbnail", "services.media_pipeline.process_reel_thumbnail_job"}:
        from services.media_pipeline import process_reel_thumbnail_job
        reel_id = payload["args"][0] if isinstance(payload, dict) and payload.get("args") else payload
        process_reel_thumbnail_job(reel_id)
        return True, None

    if job_type in {"send_digest_notifications", "send_notification_digest"}:
        return True, None

    if job_type == "sync_presence_to_neon":
        profile_id = payload["args"][0] if isinstance(payload, dict) and payload.get("args") else payload
        sync_presence_to_neon(profile_id)
        return True, None

    if job_type == "rebuild_trending_feed":
        from services.feed_engine import trending_feed
        trending_feed(limit=20)
        return True, None

    return False, "Unknown job type"


def run_worker(once=False, queues=None):
    queues = queues or DEFAULT_QUEUES
    print(f"[{WORKER_ID}] CHAIN Background Worker started")
    idle_loops = 0
    while True:
        try:
            recover_stuck_jobs()
            job = claim_next_job(WORKER_ID, queue_names=queues)
            if job:
                idle_loops = 0
                success, error = process_job(job)
                if success:
                    complete_job(job["id"])
                    print(f"[{WORKER_ID}] Job {job['id']} completed")
                else:
                    fail_job(job["id"], error)
                    print(f"[{WORKER_ID}] Job {job['id']} failed: {error}")
                if once:
                    return 0
            else:
                if once:
                    return 0
                idle_loops += 1
                time.sleep(min(5, 1 + idle_loops))
        except Exception as error:
            print(f"[{WORKER_ID}] Worker error: {error}")
            traceback.print_exc()
            if once:
                return 1
            time.sleep(10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--queues", nargs="*", default=DEFAULT_QUEUES)
    args = parser.parse_args()
    raise SystemExit(run_worker(once=args.once, queues=args.queues))


if __name__ == "__main__":
    main()
