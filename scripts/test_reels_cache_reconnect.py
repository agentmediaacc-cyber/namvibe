from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.redis_service import redis_manager, _RECONNECT_BACKOFF


def main() -> int:
    original_url = redis_manager.url
    original_allow = redis_manager.allow_local_fallback
    try:
        redis_manager.url = "rediss://invalid.invalid:6379/0"
        redis_manager.client = None
        redis_manager.client_backend = None
        redis_manager.allow_local_fallback = False
        redis_manager.reset_pubsub()
        first = redis_manager.get_health()
        assert first["backend"] in {"memory_degraded", "none"}
        assert first["shared"] is False

        redis_manager.url = "rediss://invalid.invalid:6379/0"
        redis_manager.client = None
        redis_manager.client_backend = None
        redis_manager.allow_local_fallback = True
        _RECONNECT_BACKOFF["retry_after"] = 0.0
        redis_manager.breaker.open_until = 0.0
        redis_manager.breaker.failures = 0
        redis_manager.health_cache["expires_at"] = 0.0
        redis_manager.health_cache["payload"] = None
        redis_manager.reset_pubsub()
        second = redis_manager.get_health()
        assert second["backend"] == "redis_local"
        assert second["shared"] is True
        assert second["persistent"] is True
        key = "reels:reconnect:test"
        write = redis_manager.set_json_result(key, {"ok": True}, ttl=10, require_shared=True)
        assert write["shared"] is True
        assert redis_manager.get_json_result(key).get("value") == {"ok": True}
        redis_manager.delete(key)
        print("PASS redis_remote unavailable -> redis_local selected -> shared backend restored -> write/read passed")
        return 0
    finally:
        redis_manager.url = original_url
        redis_manager.allow_local_fallback = original_allow
        redis_manager.client = None
        redis_manager.client_backend = None
        redis_manager.reset_pubsub()


if __name__ == "__main__":
    raise SystemExit(main())
