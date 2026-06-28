#!/usr/bin/env python3
"""Verify camera creator files exist with minimum expected structure."""

import re, sys

checks = {
    "static/js/namvibe_camera_creator.js": [
        r"getUserMedia",
        r"MediaRecorder",
        r"nvcc-overlay",
        r"XMLHttpRequest|fetch",
        r"progress",
    ],
    "static/css/namvibe_camera_creator.css": [
        r"nvcc-overlay",
        r"nvcc-editor",
        r"nvcc-capture-btn",
    ],
    "templates/partials/camera_creator.html": [
        r"nvcc-overlay",
        r"camera",
        r"nvcc-capture-btn",
        r"nvcc-confirm-btn",
        r"nvcc-editor-tools",
    ],
}

issues = []
for fp, patterns in checks.items():
    try:
        with open(fp) as f:
            content = f.read()
    except FileNotFoundError:
        issues.append(f"MISSING: {fp}")
        continue
    for pat in patterns:
        if not re.search(pat, content):
            issues.append(f"{fp}: missing pattern {pat}")

if issues:
    for i in issues:
        print(f"ISSUE: {i}")
    sys.exit(1)
else:
    print("PART E/F/G OK: Camera creator files present with expected structure")