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
    first = next((item for item in items if item.get("thumbnail_url")), None)
    assert first is not None, items
    assert first.get("video_url"), first
    assert first.get("thumbnail_url"), first
    if first.get("poster_url"):
        assert first.get("poster_url") == first.get("thumbnail_url"), first
    thumb = first.get("thumbnail_url")
    assert not str(thumb).startswith("/Users/"), thumb
    if str(thumb).startswith("/static/"):
        local_thumb = ROOT / str(thumb).lstrip("/")
        assert local_thumb.exists(), f"Missing local thumbnail file: {local_thumb}"
    print("TEST_OK reels thumbnail contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
