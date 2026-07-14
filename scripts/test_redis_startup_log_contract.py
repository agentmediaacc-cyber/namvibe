#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class _FakeApp:
    def __init__(self):
        self.config = {"TESTING": False}

    def errorhandler(self, _code):
        def decorator(func):
            return func

        return decorator


def main():
    fake_app = _FakeApp()
    redis_url = "rediss://default:token-value@example.upstash.io:6379/0"

    from io import StringIO
    import contextlib

    buf = StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf), \
         patch.dict(os.environ, {"REDIS_URL": redis_url, "REDIS_TLS_URL": redis_url}, clear=False), \
         patch("services.rate_limit_service.redis_available", return_value=True), \
         patch("services.rate_limit_service.limiter.init_app", return_value=None), \
         patch("services.socketio_service.redis_available", return_value=True), \
         patch("services.socketio_service.socketio.init_app", return_value=None), \
         patch("services.socketio_service.register_live_room_handlers", return_value=None):
        from services.rate_limit_service import init_rate_limiter
        from services.socketio_service import init_socketio

        init_rate_limiter(fake_app)
        init_socketio(fake_app)

    output = buf.getvalue()
    if re.search(r"rediss://[^/\s]+:[^@\s]+@", output):
        raise AssertionError(f"credential-bearing redis URL leaked: {output}")
    if "rediss://example.upstash.io:6379" not in output:
        raise AssertionError("sanitized redis URL not present")
    if "token-value" in output or "default:" in output:
        raise AssertionError("credential fragments leaked into startup logs")
    print("TEST_OK redis startup log contract")


if __name__ == "__main__":
    main()
