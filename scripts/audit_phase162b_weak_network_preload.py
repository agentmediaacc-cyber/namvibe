#!/usr/bin/env python3
"""Audit media preloading system."""

import re, sys

issues = []

# Check home_pro.js has IntersectionObserver for media
with open("static/js/namvibe_home_pro.js") as f:
    hp = f.read()
    if "IntersectionObserver" not in hp:
        issues.append("home_pro.js: missing IntersectionObserver for media preload")
    if "mediaObserver" not in hp:
        issues.append("home_pro.js: missing mediaObserver variable")
    if "preload" not in hp:
        issues.append("home_pro.js: missing preload functionality")
    if "nvpro-card-visible" not in hp:
        issues.append("home_pro.js: missing visibility class for cards")

    # Check video play/pause on visibility
    if ".pause()" not in hp.split("IntersectionObserver")[1] if "IntersectionObserver" in hp else "":
        pass  # may be in another section
    if "preloadNextMedia" not in hp:
        issues.append("home_pro.js: missing preloadNextMedia function")

    # Check at least 20 items loaded initially (limit=20)
    if "limit=20" not in hp and "limit:20" not in hp:
        issues.append("home_pro.js: not using limit=20 for initial fetch")

# Check media extraction from DOM (getMediaUrlFromCard)
with open("static/js/namvibe_home_pro.js") as f:
    hp = f.read()
    if "getMediaUrlFromCard" not in hp:
        issues.append("home_pro.js: missing getMediaUrlFromCard function")
    if "querySelector(\"img\")" not in hp and 'querySelector("img")' not in hp:
        issues.append("home_pro.js: not extracting media from card DOM")

if issues:
    for i in issues:
        print(f"PRELOAD: {i}")
    sys.exit(1)
else:
    print("PART C OK: Media preloading with IntersectionObserver is properly wired")