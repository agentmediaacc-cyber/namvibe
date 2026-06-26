#!/usr/bin/env python3
"""Audit music player UI elements exist in detail templates."""

import re, sys

issues = []

# Check post detail music UI
with open("templates/posts/detail.html") as f:
    pd = f.read()
    checks = ["pd-music", "pd-music-play", "data-music-url", "data-music-start", "pd-music-mute"]
    for c in checks:
        if c not in pd:
            issues.append(f"posts/detail.html: missing '{c}'")

# Check reel detail music UI
with open("templates/reels/detail.html") as f:
    rd = f.read()
    checks = ["rd-music", "rd-music-play", "data-music-url"]
    for c in checks:
        if c not in rd:
            issues.append(f"reels/detail.html: missing '{c}'")

# Check JS has Audio playback
with open("templates/posts/detail.html") as f:
    pd = f.read()
    if "new Audio(url)" not in pd:
        issues.append("posts/detail.html: missing Audio playback code")
    if "activeMusicAudio" not in pd:
        issues.append("posts/detail.html: missing single-audio manager")

with open("templates/reels/detail.html") as f:
    rd = f.read()
    if "new Audio(url)" not in rd:
        issues.append("reels/detail.html: missing Audio playback code")

# Camera creator has music upload in form data
with open("static/js/namvibe_camera_creator.js") as f:
    cjs = f.read()
    if "music_url" not in cjs:
        issues.append("cam_creator.js: missing music_url in upload FormData")
    if "music_file" not in cjs:
        issues.append("cam_creator.js: missing music_file in upload FormData")

if issues:
    for i in issues:
        print(f"MUSIC UI: {i}")
    sys.exit(1)
else:
    print("PART A UI OK: Music player UI is properly wired in all detail views")