from __future__ import annotations

import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    env = dict(__import__("os").environ)
    env["CHAIN_REDIS_ALLOW_LOCAL_FALLBACK"] = "1"
    env["REDIS_URL"] = "rediss://invalid.invalid:6379/0"
    code = """
import json, time, uuid
from services.redis_service import redis_manager
key = 'reels:bench:' + uuid.uuid4().hex
payload = {'ok': True, 'key': key}
t0=time.perf_counter(); r=redis_manager.set_json_result(key,payload,ttl=30,require_shared=True); w=(time.perf_counter()-t0)*1000
t1=time.perf_counter(); v=redis_manager.get_json_result(key).get('value'); r1=(time.perf_counter()-t1)*1000
reads=[]
for _ in range(20):
    s=time.perf_counter(); redis_manager.get_json_result(key); reads.append((time.perf_counter()-s)*1000)
print(json.dumps({'backend': r['backend'], 'write_ms': w, 'read_ms': r1, 'match': v==payload, 'reads': reads, 'ttl': redis_manager.get_ttl(key)}))
redis_manager.delete(key)
"""
    proc = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=env, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        return proc.returncode
    print(proc.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
