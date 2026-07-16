#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.remote_media_service import classify_media_source


def main() -> int:
    static_file = ROOT / "static" / "uploads" / "reels" / "source_classification_test.mp4"
    static_file.parent.mkdir(parents=True, exist_ok=True)
    static_file.write_bytes(b"fake")

    local = classify_media_source("/static/uploads/reels/source_classification_test.mp4", app_root=ROOT)
    assert local["source_kind"] == "local", local
    assert local["exists"] is True, local
    assert local["reason"] == "local_media_candidate", local
    assert local["normalized_url"] == "/static/uploads/reels/source_classification_test.mp4", local

    rel = classify_media_source("static/uploads/reels/source_classification_test.mp4", app_root=ROOT)
    assert rel["source_kind"] == "local", rel
    assert rel["normalized_url"] == "/static/uploads/reels/source_classification_test.mp4", rel

    missing = classify_media_source("/static/uploads/reels/missing_test.mp4", app_root=ROOT)
    assert missing["source_kind"] == "local", missing
    assert missing["reason"] == "missing_local_source", missing

    webm = classify_media_source("/static/uploads/reels/source_classification_test.mp4", app_root=ROOT)
    assert webm["source_kind"] == "local", webm

    traversal = classify_media_source("/static/../../../../etc/passwd", app_root=ROOT)
    assert traversal["safe"] is False, traversal
    assert traversal["reason"] == "path_traversal_rejected", traversal

    infra = classify_media_source("https://db.example.invalid/_static/namvibe-logo.svg", app_root=ROOT)
    assert infra["source_kind"] == "remote", infra
    assert infra["reason"] == "invalid_media_origin", infra

    remote = classify_media_source("https://example.com/reel.mp4", app_root=ROOT)
    assert remote["source_kind"] == "remote", remote
    assert remote["safe"] is True, remote

    unsupported = classify_media_source("file:///tmp/reel.mp4", app_root=ROOT)
    assert unsupported["reason"] == "unsupported_scheme", unsupported

    print("TEST_OK reel source classification contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
