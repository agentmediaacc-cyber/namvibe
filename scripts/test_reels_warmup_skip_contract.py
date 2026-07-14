#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import threading
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")


def _get_hooks(flask_app):
    hooks = flask_app.before_request_funcs.get(None, []) or []
    by_name = {getattr(fn, "__name__", ""): fn for fn in hooks}
    assert "_first_request_warm" in by_name, "missing first-request warm hook"
    assert "prime_neon_on_first_request" in by_name, "missing neon prime hook"
    return by_name["_first_request_warm"], by_name["prime_neon_on_first_request"]


def main():
    import services.neon_service as neon_service
    from app import create_app

    counter = {"count": 0}

    def _prime():
        counter["count"] += 1

    with patch.object(neon_service, "prime_neon_runtime", side_effect=_prime), patch.object(threading.Thread, "start", lambda self: None):
        flask_app = create_app()
        first_request_warm, neon_prime = _get_hooks(flask_app)
        baseline = counter["count"]
        assert baseline == 0, counter

        with flask_app.test_request_context("/reels/"):
            assert first_request_warm() is None
            assert neon_prime() is None
        assert counter["count"] == baseline, counter

        with flask_app.test_request_context("/reels/api/reels/feed?limit=5"):
            assert first_request_warm() is None
            assert neon_prime() is None
        assert counter["count"] == baseline, counter

        with flask_app.test_request_context("/reels/00000000-0000-0000-0000-000000000000"):
            assert first_request_warm() is None
            assert neon_prime() is None
        assert counter["count"] == baseline, counter

        with flask_app.test_request_context("/healthz"):
            assert first_request_warm() is None
            assert neon_prime() is None
        assert counter["count"] == baseline, counter

    print("TEST_OK reels warmup skip contract")


if __name__ == "__main__":
    main()
