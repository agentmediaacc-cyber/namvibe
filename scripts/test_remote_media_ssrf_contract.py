#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import socket
import sys
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import services.remote_media_service as remote_media_service


def _fake_getaddrinfo(public_ip: str):
    def inner(hostname, *args, **kwargs):
        ip = public_ip
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    return inner


def main() -> int:
    original_getaddrinfo = socket.getaddrinfo
    original_build_opener = remote_media_service._build_opener
    original_build_ctx = remote_media_service.build_verified_ssl_context
    try:
        socket.getaddrinfo = _fake_getaddrinfo("93.184.216.34")  # type: ignore[assignment]
        ok = remote_media_service.validate_remote_url("https://example.com/reel.mp4")
        assert ok["ok"], ok

        socket.getaddrinfo = _fake_getaddrinfo("2001:4860:4860::8888")  # type: ignore[assignment]
        ok = remote_media_service.validate_remote_url("https://example.com/reel.mp4")
        assert ok["ok"], ok

        for bad_url, expected in [
            ("http://127.0.0.1/video.mp4", "loopback_ipv4"),
            ("http://localhost/video.mp4", "localhost_hostname"),
            ("http://10.0.0.5/video.mp4", "private_ipv4"),
            ("http://[::1]/video.mp4", "loopback_ipv6"),
            ("http://[fe80::1]/video.mp4", "link_local_ipv6"),
        ]:
            result = remote_media_service.validate_remote_url(bad_url)
            assert not result["ok"], result
            assert expected in result["reason"], result

        class _FakeOpener:
            def __init__(self, exc):
                self.exc = exc

            def open(self, req, timeout=None):
                raise self.exc

        socket.getaddrinfo = _fake_getaddrinfo("93.184.216.34")  # type: ignore[assignment]
        remote_media_service.build_verified_ssl_context = lambda: (object(), "system")  # type: ignore[assignment]
        unsafe_redirect = HTTPError(
            "https://example.com/reel.mp4",
            302,
            "Found",
            {"Location": "http://localhost/internal.mp4"},
            BytesIO(),
        )
        remote_media_service._build_opener = lambda context: _FakeOpener(unsafe_redirect)  # type: ignore[assignment]
        redirect_result = remote_media_service.fetch_remote_headers("https://example.com/reel.mp4")
        assert not redirect_result["ok"], redirect_result
        assert redirect_result["reason"] == "redirect_to_unsafe_host", redirect_result

        rebinding_redirect = HTTPError(
            "https://example.com/reel.mp4",
            302,
            "Found",
            {"Location": "https://10.0.0.2/internal.mp4"},
            BytesIO(),
        )
        remote_media_service._build_opener = lambda context: _FakeOpener(rebinding_redirect)  # type: ignore[assignment]
        redirect_result = remote_media_service.fetch_remote_headers("https://example.com/reel.mp4")
        assert not redirect_result["ok"], redirect_result
        assert redirect_result["reason"] == "redirect_to_unsafe_host", redirect_result
    finally:
        socket.getaddrinfo = original_getaddrinfo  # type: ignore[assignment]
        remote_media_service._build_opener = original_build_opener  # type: ignore[assignment]
        remote_media_service.build_verified_ssl_context = original_build_ctx  # type: ignore[assignment]

    print("TEST_OK remote media ssrf contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
