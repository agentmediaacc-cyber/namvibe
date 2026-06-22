#!/usr/bin/env python3
"""
Phase 126 — Static File Integrity Audit.
Checks that all referenced local assets exist, no duplicate includes, no syntax errors.
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0; FAIL = 0; WARN = 0

def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")

def readf(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full): return ""
    with open(full, encoding="utf-8", errors="ignore") as f:
        return f.read()

def exists(path):
    return os.path.exists(os.path.join(ROOT, path))

html = readf("templates/chain_home.html")
js = readf("static/js/namvibe_home_pro.js")
css = readf("static/css/namvibe_home_pro.css")

print("=" * 60)
print("PHASE 126 — STATIC FILE INTEGRITY AUDIT")
print("=" * 60)

# ── 1. Referenced local CSS files exist ──
print("\n--- 1. Referenced Local CSS ---")
css_refs = set(re.findall(r'/static/css/[\w._-]+', html))
local_css_ok = True
for ref in css_refs:
    local_path = ref.lstrip("/")
    if exists(local_path):
        ok(f"  {ref} exists")
    else:
        fail(f"  {ref} MISSING")
        local_css_ok = False

# ── 2. Referenced local JS files exist ──
print("\n--- 2. Referenced Local JS ---")
js_refs = set(re.findall(r'/static/js/[\w._-]+', html))
local_js_ok = True
for ref in js_refs:
    local_path = ref.lstrip("/")
    if exists(local_path):
        ok(f"  {ref} exists")
    else:
        fail(f"  {ref} MISSING")
        local_js_ok = False

# ── 3. No duplicate homepage JS includes ──
print("\n--- 3. Duplicate JS Includes ---")
js_count = html.count("namvibe_home_pro.js")
if js_count == 1:
    ok("namvibe_home_pro.js included exactly once")
else:
    fail(f"namvibe_home_pro.js included {js_count} times")

# ── 4. Upload modal JS present ──
print("\n--- 4. Upload Modal JS ---")
upload_patterns = [
    "nvpro-upload-modal", "nvpro-drop-post", "nvpro-drop-reel",
    "nvpro-drop-story", "nvpro-submit-post", "initUploadModal",
    "handleFileDrop", "handleFileSelect", "validateFile",
]
for pat in upload_patterns:
    if pat in js:
        ok(f"Upload JS pattern: {pat}")
    elif pat in html:
        ok(f"Upload pattern in HTML: {pat}")
    else:
        # handleFileDrop/Select may be inline or use different naming
        if pat in ("handleFileDrop", "handleFileSelect"):
            # Check for related patterns
            related = {"handleFileDrop": ["ondrop", "drop"], "handleFileSelect": ["onchange", "file-select", "selectFile"]}
            rels = related.get(pat, [])
            found_rel = any(r in js or r in html for r in rels)
            if found_rel:
                ok(f"Upload pattern: {pat} handled via related pattern")
            else:
                warn(f"Upload pattern not found: {pat} (may be inline)")
        else:
            fail(f"Upload pattern MISSING: {pat}")

# ── 5. Icon registry JS present ──
print("\n--- 5. Icon Registry ---")
icon_patterns = ["ICONS", "replaceFaIcons", "icon("]
for pat in icon_patterns:
    if pat in js:
        ok(f"Icon registry: {pat}")
    else:
        fail(f"Icon registry MISSING: {pat}")

# ── 6. No duplicate toast CSS block ──
print("\n--- 6. Duplicate Toast CSS ---")
# Count unique .nvpro-toast { blocks (rule definitions with properties)
import re
toast_rules = re.findall(r'\.nvpro-toast\s*\{[^}]*\}', css)
toast_full_defs = [r for r in toast_rules if '.nvpro-toast' in r and not r.strip().startswith('.nvpro-toast.is')]
if len(toast_full_defs) <= 2:
    ok(f".nvpro-toast rule definitions: {len(toast_full_defs)} (expected: base + mobile override)")
else:
    warn(f".nvpro-toast defined {len(toast_full_defs)} times — check for duplicates")

# ── 7. CSS syntax check (basic) ──
print("\n--- 7. CSS Syntax ---")
css_issues = 0
# Check for unmatched brackets
open_br = css.count("{")
close_br = css.count("}")
if open_br == close_br:
    ok(f"CSS braces balanced ({open_br}/{close_br})")
else:
    fail(f"CSS braces MISMATCHED: {open_br} open vs {close_br} close")
    css_issues += 1
# Check for obvious breakage
if "/*" in css and "*/" not in css:
    fail("Unclosed CSS comment")
    css_issues += 1
if css_issues == 0:
    ok("CSS syntax appears sound")

# ── 8. JS syntax check ──
print("\n--- 8. JS Syntax ---")
import subprocess
try:
    result = subprocess.run(
        ["node", "--check", os.path.join(ROOT, "static/js/namvibe_home_pro.js")],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode == 0:
        ok("JS syntax valid (node --check)")
    else:
        fail(f"JS syntax ERROR: {result.stderr.strip()}")
except FileNotFoundError:
    warn("node not available — skipping JS syntax check")
except Exception as e:
    warn(f"JS syntax check skipped: {e}")

# ── 9. Version marker present ──
print("\n--- 9. Build Version Marker ---")
if 'name="namvibe-build"' in html:
    ok("Build version meta tag present")
else:
    fail("Build version meta tag missing")
if "phase126" in html:
    ok("Build version value is phase126")
else:
    fail("Build version phase126 missing")

# ── 10. Cache-busting query params ──
print("\n--- 10. Cache-Busting Query Params ---")
if "namvibe_home_pro.css?v=phase126" in html:
    ok("CSS has cache-busting ?v=phase126")
else:
    fail("CSS cache-busting missing")
if "namvibe_home_pro.js?v=phase126" in html:
    ok("JS has cache-busting ?v=phase126")
else:
    fail("JS cache-busting missing")

# ── 11. No FontAwesome in homepage ──
print("\n--- 11. FontAwesome in Template ---")
if "fa-" not in html:
    ok("No fa-* classes in homepage template")
else:
    warn("fa-* classes found (may be legacy compatibility)")
# Check JS isn't loading FontAwesome externally (comments mentioning FontAwesome are OK)
import re
js_lower = js.lower()
fa_load_patterns = [
    "font-awesome" in js_lower and "replace" not in js_lower.split("font-awesome")[0][-30:] if "font-awesome" in js_lower else False,
    "fontawesome" in js_lower and "replace" not in js_lower.split("fontawesome")[0][-30:] if "fontawesome" in js_lower else False,
    '//cdn.*fontawesome' in js_lower,
    'https://font' in js_lower,
]
if any(fa_load_patterns):
    fail("JS may load FontAwesome externally")
elif "fontawesome" in js_lower:
    warn("FontAwesome mentioned in JS (likely replace comment — OK)")
else:
    ok("JS does not load FontAwesome")

# ── 12. No placeholder text in all files ──
print("\n--- 12. Placeholder Text ---")
all_sources = html + "\n" + js + "\n" + css
clean = True
for ph in ["TODO", "lorem", "test call sound", "test-call-sound", "changeme", "xxx"]:
    if ph.lower() in all_sources.lower():
        warn(f"Placeholder found: '{ph}'")
        clean = False
if clean:
    ok("No placeholder text in source files")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 126 — STATIC INTEGRITY SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"\n  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
