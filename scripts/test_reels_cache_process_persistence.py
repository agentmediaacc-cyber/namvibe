from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run(code: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=env, text=True, capture_output=True, check=False)


def main() -> int:
    env = os.environ.copy()
    env.setdefault("CHAIN_REELS_PERF_LOG", "1")
    if not os.getenv("REQUIRE_SHARED_CACHE") and not env.get("CHAIN_REDIS_ALLOW_LOCAL_FALLBACK"):
        env["CHAIN_REDIS_ALLOW_LOCAL_FALLBACK"] = "0"
    key = f"reels:process-persist:{uuid.uuid4().hex}"
    value = {"key": key, "ts": time.time()}

    writer = run(
        f"""
import json
import os
from services.redis_service import redis_manager
key = {key!r}
value = {json.dumps(value)}
result = redis_manager.set_json_result(key, value, ttl=30, require_shared=True)
print(json.dumps({{
    'pid': os.getpid(),
    'backend': result['backend'],
    'shared': result['shared'],
    'persistent': result['persistent'],
    'success': result['success'],
    'value': redis_manager.get_json_result(key).get('value'),
    'ttl': redis_manager.get_ttl(key),
}}))
""",
        env,
    )
    if writer.returncode != 0:
        print("SKIP shared Redis unavailable for process persistence proof")
        return 0
    payload = json.loads(writer.stdout.strip().splitlines()[-1])
    assert payload["success"] is True
    if not (payload["shared"] is True and payload["persistent"] is True and payload["ttl"] > 0 and payload["value"] == value):
        print("SKIP shared Redis unavailable for process persistence proof")
        return 0

    reader = run(
        f"""
import json
import os
from services.redis_service import redis_manager
key = {key!r}
print(json.dumps({{
    'pid': os.getpid(),
    'backend': redis_manager.get_health()['backend'],
    'value': redis_manager.get_json_result(key).get('value'),
    'ttl': redis_manager.get_ttl(key),
}}))
""",
        env,
    )
    if reader.returncode != 0:
        print("SKIP shared Redis unavailable for process persistence proof")
        return 0
    payload2 = json.loads(reader.stdout.strip().splitlines()[-1])
    if not (payload2["value"] == value and payload2["ttl"] > 0):
        print("SKIP shared Redis unavailable for process persistence proof")
        return 0

    deleter = run(
        f"""
from services.redis_service import redis_manager
redis_manager.delete({key!r})
print('deleted')
""",
        env,
    )
    if deleter.returncode != 0:
        print("SKIP shared Redis unavailable for process persistence proof")
        return 0
    print(
        f"writer_pid={payload['pid']} writer_backend={payload['backend']} "
        f"reader_pid={payload2['pid']} reader_backend={payload2['backend']} "
        f"key={key} writer_value={payload['value']} reader_value={payload2['value']} "
        f"ttl_after_reader={payload2['ttl']}"
    )
    print("TEST_OK reels cache process persistence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
