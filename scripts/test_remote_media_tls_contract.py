#!/usr/bin/env python3
from __future__ import annotations

import builtins
import os
import ssl
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import services.remote_media_service as remote_media_service


def _reset_env(keys):
    for key in keys:
        os.environ.pop(key, None)


def main() -> int:
    original_create = ssl.create_default_context
    original_import = builtins.__import__
    original_certifi = sys.modules.get("certifi", None)
    try:
        calls = []

        def capture_create_default_context(*args, **kwargs):
            calls.append(kwargs.get("cafile"))

            class DummyContext:
                pass

            return DummyContext()

        ssl.create_default_context = capture_create_default_context  # type: ignore[assignment]

        os.environ["SSL_CERT_FILE"] = "/tmp/fake-env-ca.pem"
        ctx, source = remote_media_service.build_verified_ssl_context()
        assert source == "environment", source
        assert calls[-1] == "/tmp/fake-env-ca.pem", calls
        assert ctx is not None

        _reset_env(["SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"])

        fake_certifi = types.SimpleNamespace(where=lambda: "/tmp/fake-certifi-ca.pem")
        sys.modules["certifi"] = fake_certifi
        ctx, source = remote_media_service.build_verified_ssl_context()
        assert source == "certifi", source
        assert calls[-1] == "/tmp/fake-certifi-ca.pem", calls
        assert ctx is not None

        sys.modules.pop("certifi", None)

        def import_without_certifi(name, *args, **kwargs):
            if name == "certifi":
                raise ImportError("certifi unavailable")
            return original_import(name, *args, **kwargs)

        builtins.__import__ = import_without_certifi  # type: ignore[assignment]
        ctx, source = remote_media_service.build_verified_ssl_context()
        assert source == "system", source
        assert calls[-1] is None, calls
        assert ctx is not None

        helper_source = Path("services/remote_media_service.py").read_text()
        assert "verify=False" not in helper_source
        assert "_create_unverified_context" not in helper_source
    finally:
        ssl.create_default_context = original_create  # type: ignore[assignment]
        builtins.__import__ = original_import  # type: ignore[assignment]
        _reset_env(["SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"])
        if original_certifi is not None:
            sys.modules["certifi"] = original_certifi
        else:
            sys.modules.pop("certifi", None)

    print("TEST_OK remote media tls contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
