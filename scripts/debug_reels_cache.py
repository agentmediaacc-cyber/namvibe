"""Direct diagnostic for reel cache write/read behavior."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from pprint import pprint

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.content_service import get_reels_content_version
from services.redis_service import redis_manager
from engines.cache_engine import cache_key


def main() -> int:
    require_shared = os.getenv("REQUIRE_SHARED_CACHE", "").strip().lower() in {"1", "true", "yes", "on"}
    version = get_reels_content_version("public")
    public_key = cache_key("reels", "public", "feed", f"v{version}", "limit:5", "first")
    diag_key = "reels:diagnostic:%s" % int(time.time())

    health = redis_manager.get_health()
    print(f"REDIS_URL_SCHEME={health['redis_url_scheme']}")
    print(f"REDIS_BACKEND={health.get('backend')}")
    print(f"REDIS_HOST={health.get('redis_host')}")
    print(f"REDIS_PORT={health.get('redis_port')}")
    print(f"REDIS_DB={health.get('redis_db')}")
    print(f"PUBLIC_KEY={public_key}")
    print(f"DIAG_KEY={diag_key}")
    print(f"VERSION={version}")

    payload = {
        "kind": "reels_cache_diagnostic",
        "ts": time.time(),
        "version": version,
        "public_key": public_key,
    }
    json.dumps(payload)

    write_ok = redis_manager.set_json(diag_key, payload, ttl=60)
    print(f"WRITE_RESULT={write_ok}")
    read_back = redis_manager.get_json(diag_key)
    client = redis_manager.get_client()
    direct = client.get("chain:" + diag_key) if client else None
    ttl = redis_manager.get_ttl(diag_key)

    print(f"HELPER_READ_OK={read_back == payload}")
    print(f"DIRECT_REDIS_READ_OK={direct is not None}")
    print(f"TTL={ttl}")
    print(f"SERIALIZATION={json.dumps(read_back, sort_keys=True) if read_back is not None else 'None'}")
    print(f"RAW_READ_TYPE={type(read_back).__name__}")

    try:
        redis_manager.delete(diag_key)
    except Exception:
        pass
    shared = bool(health.get("shared"))
    persistent = bool(health.get("persistent"))
    if require_shared and not (shared and persistent and health.get("backend") in {"redis_remote", "redis_local"}):
        return 1
    return 0 if write_ok and read_back == payload and direct is not None and ttl > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
