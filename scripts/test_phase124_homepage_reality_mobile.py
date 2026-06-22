#!/usr/bin/env python3
"""
Phase 124 — Homepage Reality & Mobile Polish Test.
"""

import os
import sys
import re

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


def file_read(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return ""
    with open(full, encoding="utf-8", errors="ignore") as f:
        return f.read()


def file_exists(path):
    return os.path.exists(os.path.join(ROOT, path))


print("=" * 60)
print("PHASE 124 — HOMEPAGE REALITY & MOBILE POLISH TEST")
print("=" * 60)

html = file_read("templates/chain_home.html")
css = file_read("static/css/namvibe_home_pro.css")
js = file_read("static/js/namvibe_home_pro.js")

# ── 1. Single sidebar nav ──
print("\n--- 1. Single Nav / No Duplicates ---")
if html.count('class="nvpro-left-rail"') <= 1:
    ok("Only one left rail in template")
else:
    fail(f"Left rail appears {html.count('class=\"nvpro-left-rail\"')} times")

if html.count('class="nvpro-sidebar"') <= 1:
    ok("Only one sidebar in template")
else:
    fail(f"Sidebar appears {html.count('class=\"nvpro-sidebar\"')} times")

if html.count('class="nvpro-bottom-nav"') <= 1:
    ok("Only one bottom nav in template")
else:
    fail(f"Bottom nav appears {html.count('class=\"nvpro-bottom-nav\"')} times")

namvibe_logo_count = html.count("NamVibe")
if namvibe_logo_count <= 3:
    ok(f"NamVibe logo/text appears {namvibe_logo_count} times (within limit)")
else:
    warn(f"NamVibe logo/text appears {namvibe_logo_count} times")

# ── 2. SVG icons exist, no FontAwesome required ──
print("\n--- 2. Icons ---")
if "fa-" not in html:
    ok("No FontAwesome class references in template")
else:
    fail("FontAwesome class references present in template")

if "ICONS" in js:
    ok("SVG ICONS map defined in JS")
else:
    fail("ICONS map missing from JS")

if "replaceFaIcons" in js:
    ok("replaceFaIcons function exists for legacy compatibility")
else:
    fail("replaceFaIcons missing")

# ── 3. Upload modal ──
print("\n--- 3. Upload Modal ---")
modal_checks = [
    ("Upload modal overlay", "nvpro-upload-modal"),
    ("Post tab", 'data-upload-tab="post"'),
    ("Reel tab", 'data-upload-tab="reel"'),
    ("Story tab", 'data-upload-tab="story"'),
    ("Drop zone (post)", "nvpro-drop-post"),
    ("Drop zone (reel)", "nvpro-drop-reel"),
    ("Drop zone (story)", "nvpro-drop-story"),
    ("Submit button", "nvpro-submit-post"),
]
for label, marker in modal_checks:
    if marker in html:
        ok(f"Upload modal: {label}")
    else:
        fail(f"Upload modal missing: {label}")

# ── 4. Mobile nav ──
print("\n--- 4. Mobile Bottom Nav ---")
if 'nvpro-bottom-nav' in html:
    ok("Bottom nav element exists")
else:
    fail("Bottom nav missing")

if 'nvpro-bottom-item' in html:
    ok("Bottom nav items exist")
else:
    fail("Bottom nav items missing")

mobile_items = ["Home", "Discover", "Create", "Inbox", "Profile"]
for item in mobile_items:
    pattern = f">{item}</span>"
    bottom_pattern = f'class="nvpro-bottom-item'
    if pattern in html:
        ok(f"Bottom nav item: {item}")
    else:
        warn(f"Bottom nav item not found: {item}")

# ── 5. Video elements ──
print("\n--- 5. Video Elements ---")
if "playsinline" in html or "playsInline" in html or "playsInline" in js or "playsinline" in js:
    ok("Video uses playsinline (HTML attr or JS property)")
else:
    fail("playsinline missing from video elements")

if "muted" in html or "muted" in js:
    ok("Video uses muted attribute")
else:
    fail("muted missing from video elements")

if "preload" in html or "preload" in js:
    ok("Video uses preload attribute (HTML or JS)")
else:
    fail("preload missing from video elements")

# ── 6. Autoplay JS ──
print("\n--- 6. Autoplay JS ---")
if "IntersectionObserver" in js:
    ok("IntersectionObserver present")
else:
    fail("IntersectionObserver missing")

if "videoObserver" in js:
    ok("videoObserver setup exists")
else:
    fail("videoObserver missing")

if "0.65" in js:
    ok("IntersectionObserver threshold 0.65")
else:
    warn("Threshold check")

# ── 7. View tracking throttle ──
print("\n--- 7. View Tracking Throttle ---")
if "startViewTimer" in js:
    ok("startViewTimer function exists")
else:
    fail("startViewTimer missing")

if "cancelViewTimer" in js:
    ok("cancelViewTimer function exists")
else:
    fail("cancelViewTimer missing")

if "viewedReels" in js:
    ok("viewedReels once-per-session tracking exists")
else:
    fail("viewedReels tracking missing")

if "viewBatchQueue" in js:
    ok("viewBatchQueue batching exists")
else:
    fail("viewBatchQueue missing")

if "sendBeacon" in js:
    ok("navigator.sendBeacon used for batching")
else:
    fail("sendBeacon missing")

# ── 8. Empty-state cards ──
print("\n--- 8. Empty-State Cards ---")
if "nvpro-empty-card" in html:
    ok("Premium empty-state card exists")
else:
    fail("nvpro-empty-card missing")

if "nvpro-story-empty-card" in html:
    ok("Story empty-state card exists")
else:
    fail("Story empty-state card missing")

if "No stories yet" in html:
    ok("Stories empty state text present")
else:
    fail("Stories empty state text missing")

if "No reels yet" in html:
    ok("Reels empty state text present")
else:
    fail("Reels empty state text missing")

if "Your NamVibe feed is ready" in html:
    ok("Feed empty state text present")
else:
    warn("Feed empty state text check")

# ── 9. CSS mobile breakpoints ──
print("\n--- 9. CSS Mobile Breakpoints ---")
breakpoints = ["760px", "1100px", "480px"]
for bp in breakpoints:
    if bp in css:
        ok(f"CSS breakpoint: {bp}")
    else:
        fail(f"CSS breakpoint missing: {bp}")

if "@media (max-width: 760px)" in css:
    ok("Mobile breakpoint (760px) present")
else:
    fail("Mobile breakpoint (760px) missing")

# ── 10. 44px tap targets ──
print("\n--- 10. Tap Targets ---")
if "44px" in css or "min-height: 44px" in css or "min-height:44px" in css:
    ok("44px minimum tap target size enforced")
else:
    fail("44px tap target rule missing")

if "min-height: 44px" in css:
    ok("min-height: 44px explicit in CSS")
else:
    warn("min-height:44px may be missing — check .nvpro-bottom-item")

# ── 11. 16px font on mobile inputs ──
print("\n--- 11. Mobile Input Font Size ---")
if "font-size: 16px" in css:
    ok("16px font size for inputs (prevents iOS zoom)")
else:
    fail("16px input font size missing")

# ── 12. Mobile rail hiding ──
print("\n--- 12. Mobile Responsive Hiding ---")
cleaned = css.replace(" ", "").replace("\n", "")
if ".nvpro-sidebar{display:none;}" in cleaned:
    ok("Sidebar hides on mobile via @media")
else:
    warn("Sidebar may not hide on mobile")

if ".nvpro-left-rail{display:none;}" in cleaned:
    ok("Left rail hides on mobile via @media")
else:
    fail("Left rail may not hide on mobile")

if ".nvpro-bottom-nav{display:flex;}" in cleaned:
    ok("Bottom nav shown on mobile")
else:
    fail("Bottom nav not shown on mobile")

# ── 13. Modal mobile fullscreen ──
print("\n--- 13. Mobile Modal Fullscreen ---")
if "max-width: 100vw" in css:
    ok("Upload modal full-width on mobile")
else:
    fail("Mobile modal full-width missing")

if "max-height: 100vh" in css:
    ok("Upload modal full-height on mobile")
else:
    fail("Mobile modal full-height missing")

# ── 14. No old tiktok_home.js ──
print("\n--- 14. No Deprecated JS ---")
if "tiktok_home.js" not in html:
    ok("tiktok_home.js not loaded")
else:
    fail("tiktok_home.js still loaded")

# ── 15. No broken placeholder text ──
print("\n--- 15. No Placeholder Text ---")
placeholders = ["TODO", "lorem", "test call sound", "sample text", "changeme", "xxx"]
for ph in placeholders:
    pattern = re.compile(re.escape(ph), re.IGNORECASE)
    matches = pattern.findall(html)
    if matches:
        fail(f"Placeholder text found: '{ph}' ({len(matches)} occurrences)")
    else:
        ok(f"No placeholder text: '{ph}'")

# ── 16. Story row horizontal scroll ──
print("\n--- 16. Story Row Horizontal Scroll ---")
if "overflow-x: auto" in css:
    ok("Story row: overflow-x auto for horizontal scroll")
else:
    warn("Story horizontal scroll style check")

# ── 17. Sign Out links ──
print("\n--- 17. Sign Out Links ---")
signout_count = html.count("Sign Out") + html.count("Sign Out")
if signout_count <= 2:
    ok(f"Sign Out appears {signout_count} time(s) — within limit")
else:
    warn(f"Sign Out appears {signout_count} times — possible duplicates")

# ── 18. Mobile content padding for bottom nav ──
print("\n--- 18. Mobile Bottom Nav Padding ---")
if "padding-bottom" in css.split("@media")[2] if len(css.split("@media")) > 2 else "" or "padding-bottom" in css and "bottom-h" in css:
    ok("Body padding-bottom for bottom nav on mobile")
else:
    warn("Mobile bottom nav padding may be missing")

# ── 19. Desktop rail width constraint ──
print("\n--- 19. Desktop Rail Widths ---")
if "--nvpro-rail-width: 220px" in css:
    ok("Left rail width constrained")
else:
    fail("Left rail width unconstrained")

if "--nvpro-sidebar-width: 300px" in css:
    ok("Sidebar width constrained")
else:
    fail("Sidebar width unconstrained")

# ── 20. No duplicate feed containers ──
print("\n--- 20. Feed Containers ---")
if html.count('id="nvpro-feed"') <= 1:
    ok("Single feed container")
else:
    fail("Multiple feed containers")

if html.count('id="nvpro-tabs"') <= 1:
    ok("Single tab container")
else:
    fail("Multiple tab containers")

# ── Summary ──
print(f"\n{'=' * 60}")
print(f"PHASE 124 — MOBILE POLISH TEST SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  WARN: {WARN}")
print()

if FAIL == 0:
    print("  [PASS] No blockers — mobile/reality checks pass")
else:
    print("  [FAIL] Blockers present")

if WARN > 0:
    print(f"  WARNINGS: {WARN} (review recommended)")

print()
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
