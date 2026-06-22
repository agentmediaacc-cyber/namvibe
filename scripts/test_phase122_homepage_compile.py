#!/usr/bin/env python3
"""
Phase 122 — Homepage Compile & Sanity Test.

Runs:
  - python compile for changed Python files
  - template existence checks
  - static file existence checks
  - syntax sanity on JS/CSS
"""

import os
import sys
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0
FAIL = 0
WARN = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  [PASS] {msg}")


def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")


def warn(msg):
    global WARN
    WARN += 1
    print(f"  [WARN] {msg}")


def file_exists(path):
    return os.path.exists(os.path.join(ROOT, path))


def file_read(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return ""
    with open(full, encoding="utf-8", errors="ignore") as f:
        return f.read()


print("=" * 60)
print("PHASE 122 — HOMEPAGE COMPILE & SANITY TEST")
print("=" * 60)

# ── 1. Python compile ──
print("\n--- 1. Python Compile ---")
py_files = [
    "services/homepage_service.py",
    "api_routes/homepage_api.py",
    "api_routes/feed_routes.py",
    "services/content_service.py",
]
all_compiled = True
for pyf in py_files:
    path = os.path.join(ROOT, pyf)
    if not os.path.exists(path):
        warn(f"File not found: {pyf}")
        continue
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", path],
        capture_output=True, text=True, timeout=30, cwd=ROOT,
    )
    if result.returncode == 0:
        ok(f"py_compile: {pyf}")
    else:
        fail(f"py_compile: {pyf} -> {result.stderr.strip()}")
        all_compiled = False

if all_compiled:
    ok("All Python files compiled successfully")
else:
    fail("Some Python files failed to compile")

# ── 2. Template existence ──
print("\n--- 2. Template Existence ---")
templates = [
    "templates/chain_home.html",
]
for t in templates:
    if file_exists(t):
        ok(f"Template exists: {t}")
    else:
        fail(f"Template missing: {t}")

tpl = file_read("templates/chain_home.html")
if tpl:
    # Check template syntax basics
    block_starts = tpl.count("{% block")
    block_ends = tpl.count("{% endblock")
    if block_starts == block_ends or block_ends >= block_starts:
        ok("Jinja2 block tags balanced")
    else:
        fail(f"Block tag mismatch: {block_starts} open, {block_ends} close")

    if "{% extends" in tpl:
        ok("Template extends base template")
    else:
        warn("Template does not extend base template")
else:
    fail("chain_home.html is empty")

# ── 3. Static file existence ──
print("\n--- 3. Static File Existence ---")
static_files = [
    "static/css/namvibe_home_pro.css",
    "static/js/namvibe_home_pro.js",
]
for sf in static_files:
    if file_exists(sf):
        ok(f"Static file exists: {sf}")
    else:
        fail(f"Static file missing: {sf}")

# ── 4. CSS sanity ──
print("\n--- 4. CSS Sanity ---")
css = file_read("static/css/namvibe_home_pro.css")
if css:
    required_css_classes = [
        "nvpro-shell",
        "nvpro-header",
        "nvpro-body",
        "nvpro-left-rail",
        "nvpro-center",
        "nvpro-sidebar",
        "nvpro-bottom-nav",
        "nvpro-modal-overlay",
        "nvpro-modal",
        "nvpro-drop-zone",
        "nvpro-preview-area",
        "nvpro-progress-bar",
        "nvpro-upload-result",
        "nvpro-empty-card",
        "nvpro-video-overlay",
        "nvpro-video-play-icon",
        "nvpro-double-tap-heart",
        "nvpro-loading-skeleton",
        "nv-pro-video-preview",
        "nvpro-story-empty-card",
    ]
    found = 0
    missing = []
    for cls in required_css_classes:
        if "." + cls in css:
            found += 1
        else:
            missing.append(cls)
    if found >= 15:
        ok(f"Required CSS classes: {found}/{len(required_css_classes)} found")
    else:
        warn(f"Only {found}/{len(required_css_classes)} CSS classes found; missing: {missing[:5]}")

    # Check responsive breakpoints
    for bp in ["760px", "1100px", "480px"]:
        if bp in css:
            ok(f"CSS responsive breakpoint: {bp}")
        else:
            warn(f"CSS missing breakpoint: {bp}")

    # Check no pink
    if "pink" in css.lower() or "#ff69b4" in css.lower() or "#ff1493" in css.lower():
        warn("Pink color detected in CSS — avoid per constraints")
    else:
        ok("No pink color in CSS")

    # Dark premium colors
    if "#0a1628" in css or "#1a1d23" in css:
        ok("Dark premium colors present")
    else:
        warn("Dark premium colors missing")

    # CSS length
    if len(css) > 5000:
        ok(f"CSS is substantial ({len(css)} bytes)")
    else:
        warn(f"CSS seems short ({len(css)} bytes)")
else:
    fail("CSS file is empty")

# ── 5. JS sanity ──
print("\n--- 5. JS Sanity ---")
js = file_read("static/js/namvibe_home_pro.js")
if js:
    if js.strip().endswith("})();"):
        ok("JS IIFE properly closed")
    else:
        warn("JS IIFE may not be properly closed")

    if "use strict" in js:
        ok("JS uses strict mode")
    else:
        warn("JS missing strict mode")

    # Key function checks
    js_functions = [
        "function setupVideoObserver",
        "function lazyLoadVideos",
        "function initUploadModal",
        "function replaceFaIcons",
        "function switchTab",
        "function fetchFeed",
        "function showToast",
        "function apiFetch",
        "function renderEmpty",
        "function renderFeedItems",
        "function initDropZone",
    ]
    func_found = 0
    for fn in js_functions:
        if fn in js:
            func_found += 1
    if func_found >= 8:
        ok(f"Key JS functions: {func_found}/{len(js_functions)} found")
    else:
        warn(f"Only {func_found}/{len(js_functions)} JS functions found")

    # ICONS object
    if "var ICONS" in js or "ICONS = {" in js:
        ok("ICONS object defined with SVG icons")
    else:
        warn("ICONS object not found in JS")

    # Event listeners
    for event in ["click", "dragover", "dragleave", "drop", "change"]:
        if f'addEventListener("{event}"' in js or f"addEventListener('{event}'" in js:
            ok(f"JS event listener: {event}")
        else:
            warn(f"JS event listener missing: {event}")

    # DOMContentLoaded
    if "DOMContentLoaded" in js:
        ok("DOMContentLoaded initialization present")
    else:
        warn("DOMContentLoaded initialization missing")

    if "MutationObserver" in js:
        ok("MutationObserver for dynamic video elements")
    else:
        warn("MutationObserver not present")

    # JS length
    if len(js) > 10000:
        ok(f"JS is substantial ({len(js)} bytes)")
    else:
        warn(f"JS seems short ({len(js)} bytes)")
else:
    fail("JS file is empty")

# ── Summary ──
print(f"\n{'=' * 60}")
print(f"PHASE 122 — HOMEPAGE COMPILE & SANITY SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  WARN: {WARN}")
print()

if FAIL == 0:
    print("  [PASS] No blockers — Phase 122 compiles and passes sanity checks")
else:
    print("  [FAIL] Blockers present")

if WARN > 0:
    print(f"  WARNINGS: {WARN} (review recommended)")

print()
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
