from __future__ import annotations

import concurrent.futures as cf
import threading
import time
import uuid
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.redis_service import (
    acquire_reel_cache_lock,
    delete_reel_cache,
    get_reel_cache_backend_status,
    get_reel_cache_json,
    set_reel_cache_json,
)


def main() -> int:
    status = get_reel_cache_backend_status()
    if status["backend"] != "redis_local" or not status["shared"]:
        print("SKIP local shared Redis unavailable")
        return 0

    key = f"reels:stampede:{uuid.uuid4().hex}"
    lock_key = f"{key}:lock"
    delete_reel_cache(key)
    delete_reel_cache(lock_key)

    invocations = 0
    inv_lock = threading.Lock()

    def loader():
        nonlocal invocations
        with inv_lock:
            invocations += 1
        time.sleep(0.15)
        return {"ok": True, "key": key}

    def worker():
        existing = get_reel_cache_json(key).get("value")
        if existing is not None:
            return existing
        lock = acquire_reel_cache_lock(lock_key, ttl=2)
        if lock.get("success"):
            try:
                payload = loader()
                set_reel_cache_json(key, payload, ttl=30, require_shared=True)
                return payload
            finally:
                from services.redis_service import release_reel_cache_lock
                release_reel_cache_lock(lock_key, lock.get("token"))
        deadline = time.time() + 2
        while time.time() < deadline:
            cached = get_reel_cache_json(key).get("value")
            if cached is not None:
                return cached
            time.sleep(0.02)
        return loader()

    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(lambda _: worker(), range(10)))

    assert len(results) == 10
    assert all(r == {"ok": True, "key": key} for r in results)
    assert invocations == 1, invocations
    delete_reel_cache(key)
    delete_reel_cache(lock_key)
    print("PASS callers=10 successful_results=10 loader_invocations=1 shared_backend=redis_local lock_backend=redis_local lock_shared=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
