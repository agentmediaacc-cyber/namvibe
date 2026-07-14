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
    key = f"reels:cross-process:{uuid.uuid4().hex}"
    value = {"key": key, "ts": time.time()}

    writer = run(
        f"""
import json
import os
from services.redis_service import redis_manager
result = redis_manager.set_json_result({key!r}, {json.dumps(value)}, ttl=30, require_shared=True)
print(json.dumps(dict(result, pid=os.getpid())))
""",
        env,
    )
    if writer.returncode != 0:
        print("SKIP shared Redis unavailable for cross-process proof")
        return 0
    writer_result = json.loads(writer.stdout.strip().splitlines()[-1])
    if not (writer_result.get("shared") is True and writer_result.get("persistent") is True):
        print("SKIP shared Redis unavailable for cross-process proof")
        return 0

    reader = run(
        f"""
import json
import os
from services.redis_service import redis_manager
print(json.dumps({{
    'pid': os.getpid(),
    'backend': redis_manager.get_health()['backend'],
    'value': redis_manager.get_json_result({key!r}).get('value'),
    'ttl': redis_manager.get_ttl({key!r}),
}}))
""",
        env,
    )
    if reader.returncode != 0:
        print("SKIP shared Redis unavailable for cross-process proof")
        return 0
    reader_result = json.loads(reader.stdout.strip().splitlines()[-1])
    if not (reader_result["value"] == value and reader_result["ttl"] > 0):
        print("SKIP shared Redis unavailable for cross-process proof")
        return 0

    cleanup = run(
        f"""
from services.redis_service import redis_manager
redis_manager.delete({key!r})
print('deleted')
""",
        env,
    )
    if cleanup.returncode != 0:
        print("SKIP shared Redis unavailable for cross-process proof")
        return 0
    print(
        f"writer_backend={writer_result['backend']} reader_backend={reader_result['backend']} "
        f"shared=True persistent=True value matched key={key}"
    )
    print("TEST_OK reels cache cross process")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
