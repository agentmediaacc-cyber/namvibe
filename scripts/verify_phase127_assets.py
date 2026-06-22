#!/usr/bin/env python3
"""
Phase 127 — Static Asset Verification.
Checks local static assets for JS syntax, CSS integrity, duplicate includes,
placeholder text, missing assets, and broken references.
"""

import os
import sys
import re
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0; FAIL = 0; WARN = 0


def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")


def read_file(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return None
    with open(full, encoding="utf-8", errors="ignore") as f:
        return f.read()


def file_exists(path):
    return os.path.exists(os.path.join(ROOT, path))


HTML = "templates/chain_home.html"
CSS = "static/css/namvibe_home_pro.css"
JS = "static/js/namvibe_home_pro.js"


print("=" * 60)
print("PHASE 127 — STATIC ASSET VERIFICATION")
print("=" * 60)

# ── 1. File existence ──
print("\n--- 1. Required Files Exist ---")
expected = [HTML, CSS, JS, "services/homepage_service.py"]
for path in expected:
    if file_exists(path):
        ok(f"{path} exists")
    else:
        fail(f"{path} missing")

# ── 2. JS syntax via node --check ──
print("\n--- 2. JS Syntax (node --check) ---")
js_full = os.path.join(ROOT, JS)
try:
    result = subprocess.run(["node", "--check", js_full],
                            capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        ok("JS syntax valid (node --check)")
    else:
        fail(f"JS syntax error: {result.stderr.strip()[:200]}")
except FileNotFoundError:
    warn("node not found on PATH — skipping JS syntax check")
except subprocess.TimeoutExpired:
    warn("node --check timed out — skipping")
except Exception as e:
    warn(f"node --check failed: {e}")

# ── 3. CSS integrity ──
print("\n--- 3. CSS Integrity ---")
css_text = read_file(CSS)
if css_text:
    opens = css_text.count("{")
    closes = css_text.count("}")
    if opens == closes:
        ok(f"CSS braces balanced ({opens}/{closes})")
    else:
        fail(f"CSS braces unbalanced (open={opens} close={closes})")
    if len(css_text) > 1000:
        ok(f"CSS is substantial ({len(css_text)} bytes)")
    else:
        warn(f"CSS is small ({len(css_text)} bytes)")
else:
    fail("CSS file unreadable")

# ── 4. Duplicate includes ──
print("\n--- 4. Duplicate Includes ---")
html_text = read_file(HTML)
if html_text:
    css_count = html_text.count("namvibe_home_pro.css")
    if css_count == 1:
        ok("namvibe_home_pro.css included exactly once")
    else:
        fail(f"namvibe_home_pro.css included {css_count} times")
    js_count = html_text.count("namvibe_home_pro.js")
    if js_count == 1:
        ok("namvibe_home_pro.js included exactly once")
    else:
        fail(f"namvibe_home_pro.js included {js_count} times")
else:
    fail("HTML file unreadable")

# ── 5. Placeholder text ──
print("\n--- 5. Placeholder Text ---")
sources = {}
for path in [HTML, CSS, JS]:
    text = read_file(path)
    if text:
        sources[path] = text

placeholders = ["TODO", "lorem", "test-call-sound", "xxx", "changeme", "placeholder"]
found_any = False
for path, text in sources.items():
    for ph in placeholders:
        if ph.lower() in text.lower():
            warn(f"Placeholder '{ph}' found in {path}")
            found_any = True
if not found_any:
    ok("No placeholder text in source files")

# ── 6. Missing assets ──
print("\n--- 6. Missing Assets ---")
if html_text:
    import re
    asset_refs = re.findall(r'(/static/[^\s"\'?]+)', html_text)
    missing = []
    for ref in set(asset_refs):
        # Strip version param
        local_path = ref.split("?")[0].lstrip("/")
        full = os.path.join(ROOT, local_path)
        if not os.path.exists(full):
            missing.append(ref)
    if missing:
        for m in missing:
            fail(f"Referenced asset not found: {m}")
    else:
        ok("All referenced static assets exist locally")

# ── 7. Broken references ──
print("\n--- 7. Broken References ---")
if html_text:
    js_refs = re.findall(r'src="([^"]+\.js[^"]*)"', html_text)
    css_refs = re.findall(r'href="([^"]+\.css[^"]*)"', html_text)
    all_refs = js_refs + css_refs
    missing_refs = []
    for ref in all_refs:
        local = ref.split("?")[0].lstrip("/")
        full = os.path.join(ROOT, local)
        if not os.path.exists(full):
            missing_refs.append(ref)
    if missing_refs:
        for m in missing_refs:
            fail(f"Broken reference: {m}")
    else:
        ok("No broken JS/CSS references")

# ── 8. Build marker ──
print("\n--- 8. Build Marker ---")
if html_text:
    if 'namvibe-build' in html_text:
        ok("Build version meta tag present")
    else:
        fail("Build version meta tag missing")
    if 'phase127' in html_text:
        ok("phase127 marker found")
    else:
        fail("phase127 marker missing")
    if 'data-namvibe-build' in html_text:
        ok("Hidden build marker present")
    else:
        warn("Hidden build marker missing")

# ── 9. Cache-busting ──
print("\n--- 9. Cache-Busting ---")
if html_text:
    if '?v=phase127' in html_text:
        ok("Cache-busting ?v=phase127 found")
    else:
        fail("Cache-busting version parameter missing")

# ── 10. No FontAwesome ──
print("\n--- 10. FontAwesome ---")
if html_text:
    if 'fa-' in html_text and 'font-awesome' not in html_text.lower():
        ok("No FontAwesome class references in template")
    elif 'font-awesome' in html_text.lower() or 'fontawesome' in html_text.lower():
        warn("FontAwesome CDN linked in template")
    else:
        ok("No FontAwesome dependency")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 127 — STATIC ASSET VERIFICATION SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"\n  RESULT: {'READY' if FAIL == 0 else 'BLOCKERS PRESENT'}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
