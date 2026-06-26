#!/usr/bin/env python3
"""Audit detail view offline caching."""

import re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

issues = []

# Check offline cache has detail support
with open("static/js/namvibe_offline_cache.js") as f:
    oc = f.read()
    if "saveDetail" not in oc:
        issues.append("offline_cache.js: missing saveDetail")
    if "loadDetail" not in oc:
        issues.append("offline_cache.js: missing loadDetail")

# Check post detail and reel detail pages serve correctly
# We can't test actual offline rendering here, but we can verify the templates don't error
try:
    from app import create_app
    app = create_app()
    with app.test_client() as c:
        # Verify post detail returns 200 or 404 (not 500)
        resp = c.get("/post/test-post-id")
        assert resp.status_code in (200, 404), f"post detail returned {resp.status_code}"
        # Verify reel detail returns 200 or 404 (not 500)
        resp = c.get("/reels/test-reel-id")
        assert resp.status_code in (200, 404), f"reel detail returned {resp.status_code}"
        print("PART F ROUTE OK: Detail routes respond without 500 errors")
except Exception as e:
    issues.append(f"Detail route test failed: {e}")

# Check that detail templates have offline-friendly messaging
with open("templates/posts/detail.html") as f:
    pd = f.read()
    if "Back" not in pd:
        issues.append("posts/detail.html: missing Back navigation for offline users")

with open("templates/reels/detail.html") as f:
    rd = f.read()
    if "Back" not in rd:
        issues.append("reels/detail.html: missing Back navigation for offline users")

if issues:
    for i in issues:
        print(f"DETAIL CACHE: {i}")
    sys.exit(1)
else:
    print("PART F OK: Detail views support offline-friendly rendering")