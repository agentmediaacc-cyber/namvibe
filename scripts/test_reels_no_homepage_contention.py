#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("CHAIN_REDIS_ALLOW_LOCAL_FALLBACK", "1")


def main():
    import app as app_module

    calls = []

    def _sleeping(name):
        def _inner(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"{name} should not run during reels request")
        return _inner

    with patch.object(app_module, "warm_homepage_cache", side_effect=_sleeping("warm_homepage_cache")), \
         patch.object(app_module, "prime_neon_runtime", side_effect=_sleeping("prime_neon_runtime")):
        flask_app = app_module.create_app()
        client = flask_app.test_client()
        resp = client.get("/reels/")
        assert resp.status_code in (200, 302, 308), resp.status_code
        resp2 = client.get("/reels/api/reels/feed?limit=5")
        assert resp2.status_code == 200, resp2.status_code

    assert not calls, calls
    print("TEST_OK reels no homepage contention")


if __name__ == "__main__":
    main()
