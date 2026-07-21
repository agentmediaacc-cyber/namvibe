#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from urllib.request import urlopen, Request

BASE_URL = os.environ.get("NAMVIBE_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def main() -> int:
    req = Request(f"{BASE_URL}/reels/api/reels/feed?limit=5", headers={"Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    items = payload.get("items") or payload.get("reels") or []
    assert items, "No reels returned"
    playable = next((item for item in items if item.get("video_url")), None)
    assert playable is not None, items
    first_thumb = next((item for item in items if item.get("thumbnail_url")), None)
    if first_thumb is not None:
        assert first_thumb.get("video_url"), first_thumb
        if first_thumb.get("poster_url"):
            assert first_thumb.get("poster_url") == first_thumb.get("thumbnail_url"), first_thumb
        thumb = first_thumb.get("thumbnail_url")
        assert not str(thumb).startswith("/Users/"), thumb
        if str(thumb).startswith("/static/"):
            local_thumb = ROOT / str(thumb).lstrip("/")
            assert local_thumb.exists(), f"Missing local thumbnail file: {local_thumb}"
    else:
        assert any(not item.get("thumbnail_url") for item in items), items
    print("TEST_OK reels thumbnail contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
