#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SECRET_MARKERS = ("SUPER_SECRET_REDIS_TOKEN_123", "SUPER_SECRET_DB_PASSWORD_456")


class _FakeApp:
    def __init__(self):
        self.config = {"TESTING": False}

    def errorhandler(self, _code):
        def decorator(func):
            return func

        return decorator


def main():
    fake_app = _FakeApp()
    redis_url = "rediss://default:SUPER_SECRET_REDIS_TOKEN_123@example.upstash.io:6379/0"

    buf = io.StringIO()
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
    for marker in SECRET_MARKERS:
        if marker in output:
            raise AssertionError(f"secret marker leaked in startup logs: {marker}")
    if "rediss://example.upstash.io:6379" not in output:
        raise AssertionError("sanitized redis endpoint not found in startup logs")
    print("TEST_OK startup logs no secrets")


if __name__ == "__main__":
    main()
