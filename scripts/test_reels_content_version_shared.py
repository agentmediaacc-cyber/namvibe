from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(code: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["REDIS_URL"] = "rediss://invalid.invalid:6379/0"
    env["CHAIN_REDIS_ALLOW_LOCAL_FALLBACK"] = "1"
    return subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=env, text=True, capture_output=True, check=False)


def main() -> int:
    writer = run(
        """
import json
from services.content_service import get_reels_content_version, bump_reels_content_version
from services.redis_service import redis_manager
before = get_reels_content_version('public')
after = bump_reels_content_version('public')
print(json.dumps({'backend': redis_manager.get_health()['backend'], 'before': before, 'after': after}))
"""
    )
    if writer.returncode != 0:
        print(writer.stdout)
        print(writer.stderr)
        return writer.returncode
    writer_data = json.loads(writer.stdout.strip().splitlines()[-1])
    if writer_data["backend"] != "redis_local":
        print("SKIP shared local Redis unavailable")
        return 0

    reader = run(
        """
import json
from services.content_service import get_reels_content_version
from services.redis_service import redis_manager
print(json.dumps({'backend': redis_manager.get_health()['backend'], 'version': get_reels_content_version('public')}))
"""
    )
    if reader.returncode != 0:
        print(reader.stdout)
        print(reader.stderr)
        return reader.returncode
    reader_data = json.loads(reader.stdout.strip().splitlines()[-1])
    assert reader_data["backend"] == "redis_local"
    assert reader_data["version"] == writer_data["after"]
    print(f"PASS version_before={writer_data['before']} version_after={writer_data['after']} reader_version={reader_data['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
