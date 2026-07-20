#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.browser_smoke_support import run_smoke

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--viewport",
        choices=["desktop", "tablet", "mobile", "small_mobile", "all"],
        default="all",
    )
    args = parser.parse_args()
    routes = ["/", "/profile/@namvibe", "/profile/@definitely-missing-profile", "/discover", "/reels/", "/notifications", "/messages", "/calls", "/socket.io/?EIO=4&transport=polling"]
    viewport_map = {
        "desktop": [("desktop", {"width": 1440, "height": 900})],
        "tablet": [("tablet", {"width": 768, "height": 1024, "is_mobile": True, "has_touch": True})],
        "mobile": [("mobile", {"width": 390, "height": 844, "is_mobile": True, "has_touch": True})],
        "small_mobile": [("small_mobile", {"width": 320, "height": 568, "is_mobile": True, "has_touch": True})],
        "all": None,
    }
    raise SystemExit(run_smoke(routes, viewports=viewport_map[args.viewport]))
