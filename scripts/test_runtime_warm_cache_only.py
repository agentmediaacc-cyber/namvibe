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


class _FakeClient:
    def __init__(self, value):
        self.value = value

    def get(self, key):
        return self.value


class _FakeRedis:
    def __init__(self, payload, ttl=299):
        self.payload = payload
        self.ttl = ttl
        self.client = _FakeClient(payload)

    def get_health(self):
        return {"backend": "redis_remote", "shared": True, "persistent": True}

    def acquire_lock(self, key, ttl=10):
        return {"success": True, "backend": "redis_remote", "shared": True, "persistent": True, "token": "tok"}

    def release_lock(self, key, token):
        return {"success": True, "backend": "redis_remote", "shared": True, "persistent": True}

    def get_json_result(self, key, default=None):
        return {"success": True, "backend": "redis_remote", "shared": True, "persistent": True, "value": self.payload, "error": None}

    def get_ttl(self, key):
        return self.ttl

    def get_client(self):
        return self.client

    def delete(self, key):
        return {"success": True, "backend": "redis_remote", "shared": True, "persistent": True}


def main():
    reels_payload = {"items": [{"id": "reel-1"}], "next_cursor": None, "has_more": False}
    fake_redis = _FakeRedis(reels_payload)

    with patch.object(warm_script, "redis_manager", fake_redis), \
         patch.object(warm_script, "get_reels_content_version", return_value=1), \
         patch.object(warm_script, "get_reel_feed", side_effect=AssertionError("unexpected reel loader")), \
         patch.object(warm_script, "homepage_cache_info", return_value={"homepage_cached": True, "cache_backend": {"backend": "redis_remote"}}), \
         patch.object(warm_script, "warm_homepage_cache", side_effect=AssertionError("unexpected homepage warm")):
        reels = warm_script.warm_reels(force_refresh=False)
        homepage = warm_script.warm_homepage(force_refresh=False)

    assert reels == reels_payload, reels
    assert homepage["homepage_cached"] is True, homepage
    print("TEST_OK runtime warm cache only")


if __name__ == "__main__":
    main()
