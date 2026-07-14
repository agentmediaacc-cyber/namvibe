#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import importlib.util
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


def main():
    call_order = []

    class FakeRedis:
        def __init__(self):
            self.lock_calls = 0

        def get_health(self):
            return {"backend": "redis_local", "shared": True, "persistent": True}

        def acquire_lock(self, key, ttl=10):
            self.lock_calls += 1
            return {"success": True, "backend": "redis_local", "shared": True, "persistent": True, "token": "tok"}

        def release_lock(self, key, token):
            return {"success": True, "backend": "redis_local", "shared": True, "persistent": True}

    fake_redis = FakeRedis()

    with patch.object(warm_script, "redis_manager", fake_redis), \
         patch.object(warm_script, "get_neon_health", return_value={"status": "ok", "latency_ms": 1}), \
         patch.object(warm_script, "homepage_cache_info", return_value={"homepage_cached": False, "cache_backend": {"backend": "redis_remote"}}), \
         patch.object(warm_script, "warm_homepage_cache", side_effect=lambda: call_order.append("homepage") or {"ok": True}), \
         patch.object(warm_script, "warm_reels", side_effect=lambda force_refresh=False: call_order.append("reels") or {"items": []}), \
         patch.object(warm_script, "warm_schema", side_effect=lambda: call_order.append("schema") or True):
        rc = warm_script.main(["--all"])

    assert rc == 0, rc
    assert call_order == ["schema", "homepage", "reels"], call_order

    call_order.clear()
    with patch.object(warm_script, "redis_manager", fake_redis), \
         patch.object(warm_script, "get_neon_health", return_value={"status": "ok", "latency_ms": 1}), \
         patch.object(warm_script, "homepage_cache_info", return_value={"homepage_cached": False, "cache_backend": {"backend": "redis_remote"}}), \
         patch.object(warm_script, "warm_homepage_cache", side_effect=lambda: call_order.append("homepage") or {"ok": True}), \
         patch.object(warm_script, "warm_reels", side_effect=lambda force_refresh=False: call_order.append("reels") or {"items": []}), \
         patch.object(warm_script, "warm_schema", side_effect=lambda: call_order.append("schema") or True):
        rc = warm_script.main(["--homepage", "--reels"])

    assert rc == 0, rc
    assert call_order == ["homepage", "reels"], call_order

    call_order.clear()
    with patch.object(warm_script, "redis_manager", fake_redis), \
         patch.object(warm_script, "get_neon_health", side_effect=AssertionError("should not be called")), \
         patch.object(warm_script, "homepage_cache_info", return_value={"homepage_cached": False, "cache_backend": {"backend": "redis_remote"}}), \
         patch.object(warm_script, "warm_homepage_cache", side_effect=lambda: call_order.append("homepage") or {"ok": True}), \
         patch.object(warm_script, "warm_reels", side_effect=lambda force_refresh=False: call_order.append("reels") or {"items": []}), \
         patch.object(warm_script, "warm_schema", side_effect=lambda: call_order.append("schema") or True):
        rc = warm_script.main(["--reels"])

    assert rc == 0, rc
    assert call_order == ["reels"], call_order
    print("TEST_OK runtime warm script")


if __name__ == "__main__":
    main()
