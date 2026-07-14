from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.redis_service import redis_manager


def main() -> int:
    health = redis_manager.get_health()
    backend = health.get("backend")
    assert backend in {"redis_remote", "redis_local", "memory_degraded", "none"}
    assert "persistent" in health
    assert "shared" in health

    key = f"reels:backend-selection:{uuid.uuid4().hex}"
    result = redis_manager.set_json_result(key, {"ok": True, "ts": time.time()}, ttl=30, require_shared=True)
    assert result["backend"] in {"redis_remote", "redis_local", "memory_degraded", "none"}
    assert "success" in result
    assert "shared" in result
    assert "persistent" in result
    if result["shared"]:
        assert result["persistent"] is True
        assert result["backend"] in {"redis_remote", "redis_local"}
        assert redis_manager.get_json_result(key).get("value") is not None
        assert redis_manager.get_ttl(key) > 0
    else:
        assert result["backend"] == "memory_degraded"
    redis_manager.delete(key)
    print("TEST_OK redis backend selection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
