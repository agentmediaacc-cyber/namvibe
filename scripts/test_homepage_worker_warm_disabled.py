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


def main():
    import app as app_module

    calls = []

    def _mark(name):
        def _inner(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"{name} should not run automatically")
        return _inner

    with patch.object(app_module, "warm_homepage_cache", side_effect=_mark("warm_homepage_cache")), \
         patch.object(app_module, "prime_neon_runtime", side_effect=_mark("prime_neon_runtime")), \
         patch.object(app_module, "schedule_delayed_homepage_prewarm", side_effect=_mark("schedule_delayed_homepage_prewarm")):
        flask_app = app_module.create_app()
        assert flask_app is not None
        assert hasattr(flask_app, "url_map")
        for path in ("/healthz", "/reels/", "/reels/api/reels/feed?limit=5"):
            with flask_app.test_client() as client:
                resp = client.get(path)
                assert resp.status_code in (200, 302, 308), (path, resp.status_code)

    assert not calls, calls
    print("TEST_OK homepage worker warm disabled")


if __name__ == "__main__":
    main()
