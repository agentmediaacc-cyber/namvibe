#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")

import app as app_module


def _route_set(flask_app):
    return {rule.rule for rule in flask_app.url_map.iter_rules()}


def main():
    with patch.object(app_module, "prime_neon_runtime", side_effect=AssertionError("prime_neon_runtime should not run synchronously")), \
         patch.object(app_module, "warm_homepage_cache", side_effect=AssertionError("warm_homepage_cache should not run synchronously")), \
         patch.object(app_module, "prime_live_rooms_public_cache", side_effect=AssertionError("prime_live_rooms_public_cache should not run synchronously")):
        started = time.perf_counter()
        flask_app = app_module.create_app()
        elapsed_ms = (time.perf_counter() - started) * 1000

    assert flask_app is not None
    assert hasattr(flask_app, "url_map")
    assert elapsed_ms < 1500, f"create_app too slow: {elapsed_ms:.1f}ms"
    routes = _route_set(flask_app)
    for rule in ("/healthz", "/reels/", "/reels/api/reels/feed"):
        assert rule in routes, f"missing route {rule}"
    print(f"TEST_OK app startup nonblocking elapsed_ms={elapsed_ms:.1f}")


if __name__ == "__main__":
    main()
