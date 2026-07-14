#!/usr/bin/env python3
"""Verify anonymous homepage cold-shell requests avoid the expensive homepage build path."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")

from app import app


def main():
    with patch("app._app_test_mode", return_value=False), \
         patch("app.get_full", return_value=None), \
         patch("app.get_current_profile", side_effect=AssertionError("homepage cold shell should not resolve profile")), \
         patch("api_routes.homepage_api._build_homepage_contract", side_effect=AssertionError("homepage cold shell should not build the homepage contract")):
        client = app.test_client()
        response = client.get("/")

    assert response.status_code == 200, response.status_code
    html = response.get_data(as_text=True)
    assert "NamVibe" in html
    assert "Loading latest NamVibe content" in html or "nvpro-feed" in html
    print("TEST_OK homepage cold shell avoids homepage contract")


if __name__ == "__main__":
    main()
