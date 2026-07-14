#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
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


class SharedLockRedis:
    def __init__(self):
        self._lock = threading.Lock()
        self._held = False
        self._issued = False

    def get_health(self):
        return {"backend": "redis_local", "shared": True, "persistent": True}

    def acquire_lock(self, key, ttl=10):
        with self._lock:
            if self._issued:
                return {"success": False, "backend": "redis_local", "shared": True, "persistent": True, "token": None}
            self._held = True
            self._issued = True
            return {"success": True, "backend": "redis_local", "shared": True, "persistent": True, "token": "tok"}

    def release_lock(self, key, token):
        with self._lock:
            self._held = False
        return {"success": True, "backend": "redis_local", "shared": True, "persistent": True}


def main():
    fake_redis = SharedLockRedis()
    counts = {"schema": 0, "homepage": 0, "reels": 0}

    def _schema():
        counts["schema"] += 1
        import time
        time.sleep(0.2)
        return True

    def _homepage():
        counts["homepage"] += 1
        import time
        time.sleep(0.2)
        return {"ok": True}

    def _reels():
        counts["reels"] += 1
        import time
        time.sleep(0.2)
        return {"items": []}

    def run_once():
        with patch.object(warm_script, "redis_manager", fake_redis), \
             patch.object(warm_script, "get_neon_health", return_value={"status": "ok", "latency_ms": 1}), \
             patch.object(warm_script, "warm_homepage_cache", side_effect=_homepage), \
             patch.object(warm_script, "warm_reels", side_effect=_reels), \
             patch.object(warm_script, "warm_schema", side_effect=_schema):
            return warm_script.main(["--all"])

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: run_once(), range(5)))

    assert all(rc in (0, 1) for rc in results), results
    assert counts == {"schema": 1, "homepage": 1, "reels": 1}, counts
    print("TEST_OK runtime warm singleflight")


if __name__ == "__main__":
    main()
