#!/usr/bin/env python3
"""Audit PWA service worker and registration."""

import re, sys

issues = []

# Check service worker exists
for fp, checks in [
    ("static/js/namvibe_service_worker.js", ["CACHE_NAME", "install", "activate", "fetch", "STATIC_ASSETS"]),
    ("static/js/namvibe_pwa_register.js", ["serviceWorker", "register", "namvibe_service_worker"]),
    ("static/manifest.json", ["name", "short_name", "start_url", "display", "icons"]),
]:
    try:
        with open(fp) as f:
            content = f.read()
    except FileNotFoundError:
        issues.append(f"MISSING: {fp}")
        continue
    for c in checks:
        if c not in content:
            issues.append(f"{fp}: missing '{c}'")

# Check manifest.json is valid JSON
try:
    import json
    with open("static/manifest.json") as f:
        json.load(f)
except Exception as e:
    issues.append(f"manifest.json: invalid JSON - {e}")

# Check service worker doesn't cache API or auth pages
with open("static/js/namvibe_service_worker.js") as f:
    sw = f.read()
    if "api/" not in sw:
        issues.append("service_worker: should skip /api/ paths")
    if "auth/" not in sw:
        issues.append("service_worker: should skip /auth/ paths")
    if "caches.match(\"/\")" not in sw:
        issues.append("service_worker: missing offline fallback to cached root")
    if "network-first" not in sw.lower():
        issues.append("service_worker: missing network-first strategy for HTML")

# Check template registration
with open("templates/chain_home.html") as f:
    ch = f.read()
    if "namvibe_pwa_register.js" not in ch:
        issues.append("chain_home.html: missing PWA register script")

if issues:
    for i in issues:
        print(f"PWA FAIL: {i}")
    sys.exit(1)
else:
    print("PART D OK: PWA service worker and manifest are properly set up")