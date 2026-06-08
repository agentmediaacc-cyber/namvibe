#!/usr/bin/env python
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.worker_service import run_worker_loop, run_worker_once


def main():
    parser = argparse.ArgumentParser(description="Run a CHAIN background worker.")
    parser.add_argument("--worker-name", default="worker-1")
    parser.add_argument("--worker-type", default="default")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--queues", default="default,notifications,safety,wallet")
    parser.add_argument("--max-jobs", type=int, default=None)
    args = parser.parse_args()
    queues = [q.strip() for q in args.queues.split(",") if q.strip()]
    if args.once:
        print(run_worker_once(args.worker_name, args.worker_type, queues=queues))
    else:
        print(run_worker_loop(args.worker_name, args.worker_type, queues=queues, interval=args.interval, max_jobs=args.max_jobs))


if __name__ == "__main__":
    main()
