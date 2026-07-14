#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.log_sanitizer import sanitize_connection_url, redact_connection_urls


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    cases = [
        (
            "rediss://default:super-secret@example.upstash.io:6379",
            "rediss://example.upstash.io:6379",
        ),
        (
            "redis://user:password@localhost:6379/0",
            "redis://localhost:6379/0",
        ),
        (
            "postgresql://dbuser:dbpass@example.neon.tech/neondb",
            "postgresql://example.neon.tech/neondb",
        ),
        (
            "rediss://user:token@[2001:db8::1]:6380/0?ssl=true#frag",
            "rediss://[2001:db8::1]:6380/0",
        ),
        (None, "<not-configured>"),
        ("", "<not-configured>"),
        ("not-a-url", "<configured>"),
    ]

    for value, expected in cases:
        result = sanitize_connection_url(value)
        _assert(result == expected, f"sanitize_connection_url({value!r}) -> {result!r}, expected {expected!r}")

    raw = "redis://user:password@localhost:6379/0?x=1"
    redacted = redact_connection_urls(raw)
    _assert("password" not in redacted, redacted)
    _assert("user" not in redacted or "redis://user:" not in redacted, redacted)
    _assert("?x=1" not in redacted, redacted)
    _assert("localhost:6379/0" in redacted, redacted)

    print("TEST_OK connection url log redaction")


if __name__ == "__main__":
    main()
