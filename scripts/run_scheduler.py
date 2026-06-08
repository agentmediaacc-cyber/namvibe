#!/usr/bin/env python
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.scheduler_service import run_due_tasks, seed_default_tasks


def main():
    parser = argparse.ArgumentParser(description="Run the CHAIN scheduled-task dispatcher.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=10)
    args = parser.parse_args()
    seed_default_tasks()
    if args.once:
        print(run_due_tasks())
        return
    while True:
        print(run_due_tasks())
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
