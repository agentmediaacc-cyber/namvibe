#!/usr/bin/env python3
"""Test offline cache module is properly wired."""

import re, sys

issues = []

# Check offline cache JS exists
with open("static/js/namvibe_offline_cache.js") as f:
    oc = f.read()
    checks = ["indexedDB", "saveFeed", "loadFeed", "saveDetail", "loadDetail", "saveDraft", "getDrafts"]
    for c in checks:
        if c not in oc:
            issues.append(f"offline_cache.js: missing '{c}'")

# Check it's loaded from chain_home.html
with open("templates/chain_home.html") as f:
    ch = f.read()
    if "namvibe_offline_cache.js" not in ch:
        issues.append("chain_home.html: missing offline_cache.js script")
    if "namvibe_pwa_register.js" not in ch:
        issues.append("chain_home.html: missing pwa_register.js script")

# Check namvibe_home_pro.js uses NamVibeCache
with open("static/js/namvibe_home_pro.js") as f:
    hp = f.read()
    if "NamVibeCache" not in hp:
        issues.append("home_pro.js: not using NamVibeCache")
    if "saveFeed" not in hp:
        issues.append("home_pro.js: not calling saveFeed")
    if "loadFeed" not in hp:
        issues.append("home_pro.js: not calling loadFeed")

# Check offline banner exists
with open("templates/chain_home.html") as f:
    ch = f.read()
    if "nvpro-offline-banner" not in ch:
        issues.append("chain_home.html: missing offline banner")
    if "is-offline" not in ch:
        issues.append("chain_home.html: missing is-offline class")

if issues:
    for i in issues:
        print(f"CACHE FAIL: {i}")
    sys.exit(1)
else:
    print("PART B OK: Offline cache module is properly integrated")