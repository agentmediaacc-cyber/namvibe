import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

env = os.environ.copy()
env.update({
    "PYTHONPATH": ".",
    "FLASK_ENV": "production",
    "ENV": "production",
    "CHAIN_FAST_LOCAL": "1",
    "CHAIN_DISABLE_PERFORMANCE_LOGS": "1",
    "CHAIN_DISABLE_IP_REPUTATION": "1",
})

_disable_scheduler = os.environ.get("CHAIN_DISABLE_SCHEDULER") == "1"
_disable_workers = os.environ.get("CHAIN_DISABLE_WORKERS") == "1"
_disable_call_worker = os.environ.get("CHAIN_DISABLE_CALL_WORKER") == "1"

commands = [
    ("app", [sys.executable, "app.py"]),
]
if not _disable_scheduler:
    commands.append(("scheduler", [sys.executable, "scripts/run_scheduler.py", "--interval", "10"]))
if not _disable_workers:
    commands.append(("worker", [sys.executable, "scripts/run_worker.py", "--worker-name", "worker-1", "--worker-type", "default", "--interval", "2", "--queues", "default,notifications,safety,wallet"]))
if not _disable_call_worker:
    commands.append(("call-worker", [sys.executable, "scripts/run_worker.py", "--worker-name", "call-worker-1", "--worker-type", "calls", "--interval", "2", "--queues", "default,notifications"]))

processes = []

def stop_all(*_):
    print("\nStopping CHAIN dev stack...")
    for name, p in processes:
        if p.poll() is None:
            print(f"Stopping {name}...")
            p.terminate()
    time.sleep(2)
    for name, p in processes:
        if p.poll() is None:
            p.kill()
    sys.exit(0)

signal.signal(signal.SIGINT, stop_all)
signal.signal(signal.SIGTERM, stop_all)

if _disable_scheduler:
    print("[dev_run_all] SCHEDULER DISABLED (CHAIN_DISABLE_SCHEDULER=1)")
if _disable_workers:
    print("[dev_run_all] WORKERS DISABLED (CHAIN_DISABLE_WORKERS=1)")
if _disable_call_worker:
    print("[dev_run_all] CALL WORKER DISABLED (CHAIN_DISABLE_CALL_WORKER=1)")

print("Starting CHAIN dev stack...")
for name, cmd in commands:
    print("Starting", name, "=>", " ".join(cmd))
    p = subprocess.Popen(cmd, cwd=ROOT, env=env)
    processes.append((name, p))
    time.sleep(1)

print("\nCHAIN stack running.")
print("Open: http://127.0.0.1:5000")
print("Press CTRL+C to stop everything.\n")

while True:
    for name, p in processes:
        if p.poll() is not None:
            print(f"{name} stopped with code {p.returncode}")
            stop_all()
    time.sleep(3)
