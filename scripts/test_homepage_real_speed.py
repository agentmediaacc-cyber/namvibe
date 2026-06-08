import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_DISABLE_RATE_LIMITS", "1")

from app import create_app
from services.homepage_cache_service import cache_status, invalidate_homepage_cache


def _ms(started):
    return (time.perf_counter() - started) * 1000


def main():
    invalidate_homepage_cache()
    with patch("app.prime_neon_runtime"), patch("app.prime_live_rooms_public_cache"), patch("app.init_scheduler"):
        app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    started = time.perf_counter()
    first = client.get("/")
    first_ms = _ms(started)
    print(f"homepage_first_ms={first_ms:.1f} status={first.status_code} header={first.headers.get('X-Response-Time-Ms')}")
    assert first.status_code == 200
    assert first_ms < 3000, f"first homepage load too slow: {first_ms:.1f}ms"

    started = time.perf_counter()
    second = client.get("/")
    second_ms = _ms(started)
    print(f"homepage_cached_ms={second_ms:.1f} status={second.status_code} header={second.headers.get('X-Response-Time-Ms')}")
    assert second.status_code == 200
    assert second_ms < 1000, f"cached homepage load too slow: {second_ms:.1f}ms"

    started = time.perf_counter()
    health = client.get("/healthz")
    health_ms = _ms(started)
    print(f"healthz_ms={health_ms:.1f} status={health.status_code}")
    assert health.status_code == 200

    print(f"cache_status={cache_status()}")
    print("homepage real speed benchmark passed")


if __name__ == "__main__":
    main()
