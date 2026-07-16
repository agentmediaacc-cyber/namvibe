#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import services.remote_media_service as remote_media_service


class _FakeDownload:
    def __init__(self, payload: bytes):
        self.payload = payload

    def download(self, object_path):
        return self.payload


class _FakeStorage:
    def __init__(self, payload: bytes):
        self.payload = payload

    def from_(self, bucket):
        return _FakeDownload(self.payload)


class _FakeAdmin:
    def __init__(self, payload: bytes):
        self.storage = _FakeStorage(payload)


def main() -> int:
    original_admin = remote_media_service.get_supabase_admin
    try:
        remote_media_service.get_supabase_admin = lambda: _FakeAdmin(b"\x00\x01video-bytes")  # type: ignore[assignment]
        tmp, meta = remote_media_service._download_supabase_storage(
            "https://example.supabase.co/storage/v1/object/public/reels/sample.mp4"
        )
        assert tmp is not None, meta
        assert meta["ok"], meta
        assert tmp.exists(), tmp
        assert tmp.read_bytes() == b"\x00\x01video-bytes"
        tmp.unlink(missing_ok=True)

        remote_media_service.get_supabase_admin = lambda: _FakeAdmin(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")  # type: ignore[assignment]
        tmp, meta = remote_media_service._download_supabase_storage(
            "https://example.supabase.co/storage/v1/object/public/reels/sample.svg"
        )
        assert tmp is None, (tmp, meta)
        assert meta["reason"] == "svg_not_video", meta
    finally:
        remote_media_service.get_supabase_admin = original_admin  # type: ignore[assignment]

    print("TEST_OK remote media supabase storage contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
