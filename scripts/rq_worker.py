import sys
import os
from rq import Worker, Queue, Connection
from services.queue_service import get_queue
from services.redis_service import get_redis

def main():
    r = get_redis()
    if not r:
        print("[rq_worker] Redis unavailable, exiting.")
        sys.exit(1)

    with Connection(r):
        queue_names = sys.argv[1:] or ['critical', 'realtime', 'media', 'notifications', 'analytics', 'maintenance', 'default']
        queues = [get_queue(name) for name in queue_names]
        queues = [queue for queue in queues if queue is not None]
        worker = Worker(queues)
        print(f"[rq_worker] Worker started listening on: {queue_names}")
        worker.work()

if __name__ == '__main__':
    # Add project root to path
    sys.path.append(os.getcwd())
    main()
