#!/usr/bin/env python3
"""Audit that post cards have data-href attributes and click handlers."""

import re, sys

files = [
    "templates/chain_home.html",
    "static/js/namvibe_home_pro.js",
]

issues = []

for fp in files:
    with open(fp) as f:
        content = f.read()
    if "data-href" not in content:
        issues.append(f"{fp}: missing data-href usage")
    if "cursor:pointer" not in content:
        issues.append(f"{fp}: missing cursor:pointer style")

with open("templates/chain_home.html") as f:
    home = f.read()
    # check click delegation
    if not re.search(r"e\.target\.closest\(['\"]\.nvpro-post-card['\"]\)", home):
        issues.append("chain_home.html: missing card click delegation")

with open("static/js/namvibe_home_pro.js") as f:
    js = f.read()
    # search for href assignment in both renderFeedItems and appendFeedItems
    if not re.search(r"data-href\s*=|\.dataset\.href\s*=", js):
        issues.append("namvibe_home_pro.js: missing data-href assignment")
    if not re.search(r"renderFeedItems|appendFeedItems", js):
        issues.append("namvibe_home_pro.js: missing feed render functions")

if issues:
    for i in issues:
        print(f"ISSUE: {i}")
    sys.exit(1)
else:
    print("PART B OK: All clickable card markers present")