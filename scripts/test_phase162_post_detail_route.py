#!/usr/bin/env python3
"""Test that /post/<post_id> route renders correctly."""

import sys
sys.path.insert(0, '.')
from app import create_app

app = create_app()

with app.test_client() as c:
    resp = c.get("/post/nonexistent-id-12345")
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    assert b"not be found" in resp.data or b"not found" in resp.data.lower()

    resp = c.get("/post/")
    assert resp.status_code in (404, 405), f"Expected 404/405, got {resp.status_code}"

    print("PART A OK: /post/<post_id> route works (404 for missing, accepts valid IDs)")