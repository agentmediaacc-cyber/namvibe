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
from services.homepage_cache_service import homepage_cache_info, invalidate_homepage_cache
from services.homepage_warmup_service import warm_homepage_cache


def elapsed_ms(started):
    return (time.perf_counter() - started) * 1000


def main():
    invalidate_homepage_cache()
    with patch("app.prime_neon_runtime"), patch("app.prime_live_rooms_public_cache"), patch("app.init_scheduler"):
        app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    with app.app_context():
        warm_result = warm_homepage_cache()
    print(f"warmup={warm_result}")

    started = time.perf_counter()
    first = client.get("/")
    first_ms = elapsed_ms(started)
    print(f"homepage_first_ms={first_ms:.1f} header={first.headers.get('X-Response-Time-Ms')} status={first.status_code}")
    assert first.status_code == 200
    assert first_ms < 3000, f"first request too slow: {first_ms:.1f}ms"

    started = time.perf_counter()
    second = client.get("/")
    second_ms = elapsed_ms(started)
    print(f"homepage_second_ms={second_ms:.1f} header={second.headers.get('X-Response-Time-Ms')} status={second.status_code}")
    assert second.status_code == 200
    assert second_ms < 500, f"second request too slow: {second_ms:.1f}ms"

    cache = client.get("/system/api/cache-status")
    print(f"cache_status={cache.get_json()}")
    assert cache.status_code == 200
    assert cache.get_json().get("homepage_cached") is True

    print("homepage warmup benchmark passed")


if __name__ == "__main__":
    main()
