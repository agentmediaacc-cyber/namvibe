#!/usr/bin/env python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.job_queue_service import get_queue_stats
from services.redis_hardening_service import get_redis_health
from services.scheduler_service import get_scheduler_status
from services.worker_service import get_all_worker_statuses


def main():
    stats = get_queue_stats()
    print("Queue stats:", stats.get("stats"))
    print("Workers online:", len([w for w in get_all_worker_statuses() if w.get("status") == "online"]))
    print("Redis status:", get_redis_health())
    print("Scheduled tasks:", len(get_scheduler_status().get("tasks", [])))
    print("DB fallback status:", stats.get("db_fallback"))


if __name__ == "__main__":
    main()
