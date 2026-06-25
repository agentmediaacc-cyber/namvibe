#!/usr/bin/env python3
"""Audit: No old homepage placeholders, hardcoded content, or demo text."""
import os, sys, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = 0, 0
def test(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} - {detail}")

BLOCKED_PHRASES = [
    "Special homepage",
    "Your NamVibe feed is ready",
    "TODO",
    "FIXME",
    "coming soon",
    "under construction",
]

EXCLUDE_IF_HTML_ATTR = ["placeholder"]
DEMO_SAMPLE = ["demo", "sample"]

print("="*60)
print("PHASE 161c - PLACEHOLDER / HARDCODE AUDIT")
print("="*60)

def is_html_placeholder(line):
    stripped = line.strip()
    return bool(re.search(r'[\"\']?\s*placeholder\s*=\s*[\"\']', stripped, re.IGNORECASE))

def has_phrase(content, phrase, exclude_attr=False):
    for line in content.split('\n'):
        l = line.lower()
        if phrase.lower() not in l:
            continue
        if exclude_attr and is_html_placeholder(line):
            continue
        if phrase.lower() == 'demo' or phrase.lower() == 'sample':
            if 'demo' in l.lower() and 'placeholder' not in l.lower():
                return True
            if 'sample' in l.lower() and 'placeholder' not in l.lower():
                return True
            continue
        return True
    return False

all_files = []
for root, dirs, files in os.walk(BASE):
    for f in files:
        if f.endswith(('.html', '.js', '.css', '.py')):
            path = os.path.join(root, f)
            if 'node_modules' in path or '.git' in path or 'venv' in path:
                continue
            all_files.append(path)

checked = 0
for fpath in all_files:
    with open(fpath, errors='ignore') as f:
        content = f.read()
    for phrase in BLOCKED_PHRASES:
        if phrase.lower() in content.lower():
            test(f"{os.path.basename(fpath)}: {phrase}", False, fpath)
    for phrase in DEMO_SAMPLE:
        if has_phrase(content, phrase):
            # Only flag if it's not in the context of demo/sample empty state text
            lines = content.split('\n')
            for line in lines:
                if phrase.lower() in line.lower() and not is_html_placeholder(line):
                    test(f"{os.path.basename(fpath)}: {phrase}", False, fpath)
                    break
    checked += 1

print(f"\nChecked {checked} files")
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
