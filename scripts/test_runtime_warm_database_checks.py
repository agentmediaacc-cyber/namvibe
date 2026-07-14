#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SCRIPT_PATH = Path(ROOT) / "scripts" / "warm_production_runtime.py"
SPEC = importlib.util.spec_from_file_location("warm_production_runtime", SCRIPT_PATH)
warm_script = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(warm_script)


class _FakeRedis:
    def get_health(self):
        return {"backend": "redis_remote", "shared": True, "persistent": True}

    def acquire_lock(self, key, ttl=10):
        return {"success": True, "backend": "redis_remote", "shared": True, "persistent": True, "token": "tok"}

    def release_lock(self, key, token):
        return {"success": True, "backend": "redis_remote", "shared": True, "persistent": True}


def main():
    fake_redis = _FakeRedis()

    with patch.object(warm_script, "redis_manager", fake_redis), \
         patch.object(warm_script, "warm_schema", return_value=True), \
         patch.object(warm_script, "warm_homepage_cache", return_value={"ok": True}), \
         patch.object(warm_script, "warm_reels", return_value={"items": []}), \
         patch.object(warm_script, "get_neon_health", side_effect=AssertionError("unexpected health probe")):
        rc = warm_script.main(["--homepage"])
    assert rc == 0, rc

    neon_calls = []
    with patch.object(warm_script, "redis_manager", fake_redis), \
         patch.object(warm_script, "warm_schema", return_value=True), \
         patch.object(warm_script, "warm_homepage_cache", return_value={"ok": True}), \
         patch.object(warm_script, "warm_reels", return_value={"items": []}), \
         patch.object(warm_script, "get_neon_health", side_effect=lambda: neon_calls.append("health") or {"status": "ok", "latency_ms": 1}):
        rc = warm_script.main(["--all", "--check-database"])
    assert rc == 0, rc
    assert neon_calls == ["health"], neon_calls
    print("TEST_OK runtime warm database checks")


if __name__ == "__main__":
    main()
