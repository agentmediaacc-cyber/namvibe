#!/usr/bin/env python3
"""Deterministic contract for social relationship cache invalidation."""

from pathlib import Path
import uuid
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import services.redis_service as redis_service
from services.relationship_cache_service import invalidate_profile_relationships


def check(name, condition):
    print(("PASS" if condition else "FAIL") + f": {name}")
    if not condition:
        raise AssertionError(name)


class FakeRedis:
    def __init__(self, keys):
        self.keys = list(keys)
        self.deleted = []

    def scan_iter(self, pattern):
        import fnmatch
        for key in list(self.keys):
            if fnmatch.fnmatch(key, pattern):
                yield key

    def delete(self, key):
        self.deleted.append(key)
        if key in self.keys:
            self.keys.remove(key)


def main():
    memory_backup = dict(redis_service._MEMORY_FALLBACK)
    set_backup = dict(redis_service._SET_FALLBACK)
    ttl_backup = dict(redis_service._TTL_FALLBACK)
    client_backup = redis_service.redis_manager.client

    try:
        redis_service._MEMORY_FALLBACK.clear()
        redis_service._SET_FALLBACK.clear()
        redis_service._TTL_FALLBACK.clear()

        target_id = str(uuid.uuid4())
        viewer_a = str(uuid.uuid4())
        viewer_b = str(uuid.uuid4())
        viewer_c = str(uuid.uuid4())
        other_target = str(uuid.uuid4())

        keys = {
            f"chain:cache:rel:state:{viewer_a}:{target_id}": {"relationship": "friend"},
            f"chain:cache:rel:state:{target_id}:{viewer_a}": {"relationship": "friend"},
            f"chain:cache:rel:state:{viewer_b}:{target_id}": {"relationship": "none"},
            f"chain:cache:rel:state:{viewer_c}:{other_target}": {"relationship": "none"},
        }
        redis_service._MEMORY_FALLBACK.update(keys)
        redis_service._SET_FALLBACK.update(keys)

        fake_client = FakeRedis(keys.keys())
        redis_service.redis_manager.client = fake_client

        invalidate_profile_relationships(target_id)

        check(
            "outgoing cache cleared",
            f"chain:cache:rel:state:{viewer_a}:{target_id}" not in redis_service._MEMORY_FALLBACK,
        )
        check(
            "incoming cache cleared",
            f"chain:cache:rel:state:{target_id}:{viewer_a}" not in redis_service._MEMORY_FALLBACK,
        )
        check(
            "other viewer cache cleared",
            f"chain:cache:rel:state:{viewer_b}:{target_id}" not in redis_service._MEMORY_FALLBACK,
        )
        check(
            "unrelated cache preserved",
            f"chain:cache:rel:state:{viewer_c}:{other_target}" in redis_service._MEMORY_FALLBACK,
        )
        check(
            "redis scan delete used exact matches",
            any(target_id in key for key in fake_client.deleted),
        )

        print("test_social_relationship_cache_contract_ok")
    finally:
        redis_service._MEMORY_FALLBACK.clear()
        redis_service._MEMORY_FALLBACK.update(memory_backup)
        redis_service._SET_FALLBACK.clear()
        redis_service._SET_FALLBACK.update(set_backup)
        redis_service._TTL_FALLBACK.clear()
        redis_service._TTL_FALLBACK.update(ttl_backup)
        redis_service.redis_manager.client = client_backup


if __name__ == "__main__":
    main()
