#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, create_app


def _assert_route(flask_app, rule):
    rules = {r.rule for r in flask_app.url_map.iter_rules()}
    assert rule in rules, f"missing route {rule}"


def main():
    assert app is not None
    assert create_app() is not None
    assert hasattr(app, "url_map")
    assert hasattr(create_app(), "url_map")

    _assert_route(app, "/healthz")
    _assert_route(app, "/reels/")
    _assert_route(app, "/reels/api/reels/feed")
    print("TEST_OK app factory contract")


if __name__ == "__main__":
    main()
