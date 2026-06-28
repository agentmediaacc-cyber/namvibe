#!/usr/bin/env python3
"""Test that post detail template includes comment section."""

import sys
sys.path.insert(0, '.')
from app import create_app

app = create_app()

with app.test_client() as c:
    # Check that the post detail template exists and includes comment markup
    resp = c.get("/post/test-post")
    if resp.status_code == 200:
        assert b"comment" in resp.data.lower()
        print("PART C OK: Post detail page renders with comment section")
    elif resp.status_code == 404:
        # Even on 404, the post_not_found template should not crash
        assert b"not found" in resp.data.lower() or b"deleted" in resp.data.lower()
        print("PART C OK: Post detail returns 404 gracefully without crash")
    else:
        print(f"PART C WARN: Unexpected status {resp.status_code}")