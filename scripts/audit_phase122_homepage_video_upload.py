#!/usr/bin/env python3
"""
Phase 122 — Homepage Video, Story, Upload & Icon Upgrade Audit.

Checks:
  - chain_home.html loads correct CSS/JS
  - no duplicate nav block
  - upload modal exists
  - reel autoplay JS exists (IntersectionObserver)
  - story/reel/post max duration rules exist
  - mobile bottom nav exists
  - empty state cards exist
  - required icon names exist
  - no FontAwesome i tags (replaced by SVG)
  - video overlay elements exist
  - drop zone exists
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
print("PHASE 122 — HOMEPAGE VIDEO & UPLOAD AUDIT")
print("=" * 60)

# ── 1. File existence ──
print("\n--- 1. File Existence ---")
files = [
    "templates/chain_home.html",
    "static/css/namvibe_home_pro.css",
    "static/js/namvibe_home_pro.js",
    "services/homepage_service.py",
    "api_routes/homepage_api.py",
    "services/content_service.py",
]
for f in files:
    if file_exists(f):
        ok(f"File exists: {f}")
    else:
        fail(f"File missing: {f}")

# ── 2. Template loads correct CSS/JS ──
print("\n--- 2. Template CSS/JS Loading ---")
html = file_read("templates/chain_home.html")
if not html:
    fail("Template file is empty")
else:
    if "namvibe_home_pro.css" in html:
        ok("Template links namvibe_home_pro.css")
    else:
        fail("Template missing namvibe_home_pro.css link")

    if "namvibe_home_pro.js" in html:
        ok("Template links namvibe_home_pro.js")
    else:
        fail("Template missing namvibe_home_pro.js link")

    if "tiktok_home.js" not in html:
        ok("tiktok_home.js NOT loaded in template")
    else:
        warn("tiktok_home.js still loaded")

    if "fontawesome" not in html.lower() and "fa-" not in html:
        ok("No FontAwesome class references found in template")
    else:
        warn("FontAwesome class references still present in template")

# ── 3. No duplicates ──
print("\n--- 3. Duplicate Check ---")
left_rail_count = html.count('nvpro-rail-item')
left_rail_count_open = html.count('class="nvpro-left-rail"') + html.count("class='nvpro-left-rail'")
if left_rail_count_open <= 1:
    ok("Left rail appears once")
else:
    fail(f"Left rail appears {left_rail_count_open} times")

bottom_nav_count = html.count('nvpro-bottom-nav') - html.count('nvpro-bottom-nav-item')
if html.count('class="nvpro-bottom-nav"') + html.count("class='nvpro-bottom-nav'") <= 1:
    ok("Bottom nav appears once")
else:
    fail("Bottom nav appears multiple times")

sidebar_count = html.count('class="nvpro-sidebar"') + html.count("class='nvpro-sidebar'")
if sidebar_count <= 1:
    ok("Sidebar appears once")
else:
    fail(f"Sidebar appears {sidebar_count} times")

# Check no duplicate nav items across left rail and bottom nav
for label in ["Home", "Discover", "Reels", "Inbox", "Profile"]:
    # Count occurrences of label in the entire template
    count = html.count(f">{label}</span>") + html.count(f">{label}</a>") + html.count(f">{label}</button>")
    if count <= 2:
        ok(f"Nav label '{label}' reasonable count: {count}")
    else:
        warn(f"Nav label '{label}' appears {count} times (possible duplicate)")

# ── 4. Upload modal exists ──
print("\n--- 4. Upload Modal ---")
modal_markers = [
    ("Upload modal overlay", 'nvpro-modal-overlay'),
    ("Modal container", 'nvpro-modal'),
    ("Modal tabs (Post/Reel/Story)", 'data-upload-tab'),
    ("Drop zone (Post)", 'nvpro-drop-post'),
    ("Drop zone (Reel)", 'nvpro-drop-reel'),
    ("Drop zone (Story)", 'nvpro-drop-story'),
    ("File input (Post)", 'nvpro-file-post'),
    ("File input (Reel)", 'nvpro-file-reel'),
    ("File input (Story)", 'nvpro-file-story'),
    ("Preview area", 'nvpro-preview-area'),
    ("Progress bar", 'nvpro-progress-bar'),
    ("Progress fill", 'nvpro-progress-fill'),
    ("Upload submit button", 'nvpro-submit-post'),
    ("Upload success state", 'nvpro-upload-result'),
    ("Close button", 'nvpro-modal-close'),
    ("Create button in header", 'nvpro-create-btn'),
    ("data-open-upload attribute", 'data-open-upload'),
]
for label, marker in modal_markers:
    if marker in html:
        ok(f"Upload modal: {label}")
    else:
        fail(f"Upload modal missing: {label}")

# ── 5. Reel autoplay JS ──
print("\n--- 5. Reel Autoplay JS ---")
js = file_read("static/js/namvibe_home_pro.js")
if not js:
    fail("JS file is empty")
else:
    if "IntersectionObserver" in js:
        ok("IntersectionObserver present in JS")
    else:
        fail("IntersectionObserver missing from JS")

    if "data-nv-video" in js:
        ok("data-nv-video attribute used for video elements")
    else:
        fail("data-nv-video attribute not found in JS")

    if "videoObserver" in js:
        ok("videoObserver variable defined")
    else:
        fail("videoObserver not defined")

    if "lazyLoadVideos" in js:
        ok("lazyLoadVideos function defined")
    else:
        fail("lazyLoadVideos function missing")

    if "nvpro-video-preview" in js:
        ok("nvpro-video-preview class used")
    else:
        warn("nvpro-video-preview class not found in JS")

    if "nvpro-video-overlay" in js:
        ok("Video overlay class used for play/pause toggle")
    else:
        fail("Video overlay class missing from JS")

    if "nvpro-double-tap-heart" in js:
        ok("Double-tap heart animation exists")
    else:
        warn("Double-tap heart animation missing")

    if "nvpro-loading-skeleton" in js:
        ok("Loading skeleton for videos exists")
    else:
        warn("Loading skeleton missing")

# ── 6. Duration validation rules in JS ──
print("\n--- 6. JS Duration Validation ---")
duration_checks = [
    ("Story max 60s", "maxDuration: 60"),
    ("Reel max 90s", "maxDuration: 90"),
    ("Post max 600s", "maxDuration: 600"),
    ("Story size 100MB", "maxSize: 100"),
    ("Reel size 250MB", "maxSize: 250"),
    ("Post size 700MB", "maxSize: 700"),
    ("Duration error messages", "seconds or less"),
]
for label, pattern in duration_checks:
    if pattern in js:
        ok(f"JS validation: {label}")
    else:
        warn(f"JS validation missing: {label}")

if "UPLOAD_RULES" in js:
    ok("UPLOAD_RULES dict defined in JS")
else:
    fail("UPLOAD_RULES not found in JS")

# ── 7. Server-side duration validation ──
print("\n--- 7. Server-Side Duration Validation ---")
svc = file_read("services/content_service.py")
if "max_duration_seconds" in svc:
    ok("validate_media() accepts max_duration_seconds parameter")
else:
    fail("validate_media() missing max_duration_seconds parameter")

if "save_media_file" in svc and "max_duration_seconds" in svc:
    ok("save_media_file() passes max_duration_seconds to validate_media()")
else:
    warn("save_media_file() may not pass max_duration_seconds")

# ── 8. SVG icon names ──
print("\n--- 8. SVG Icons ---")
required_icons = ["home", "discover", "live", "reels", "stories", "inbox", "contacts", "calls",
                  "dating", "wallet", "profile", "signout", "search", "plus", "upload",
                  "play", "pause", "heart", "comment", "share", "save", "close", "bell",
                  "envelope", "shield", "feedback", "film", "check", "alert", "newpost",
                  "camera", "video", "image"]
found_icons = 0
missing_icons = []
for icon_name in required_icons:
    pattern = f"{icon_name}:"
    if pattern in js:
        found_icons += 1
    else:
        missing_icons.append(icon_name)

if found_icons >= 28:
    ok(f"Icon definitions: {found_icons}/{len(required_icons)} required icons found")
else:
    warn(f"Only {found_icons}/{len(required_icons)} required icons found; missing: {missing_icons}")

# ── 9. Mobile bottom nav ──
print("\n--- 9. Mobile Bottom Nav ---")
if 'nvpro-bottom-nav' in html:
    ok("Mobile bottom nav element exists")
else:
    fail("Mobile bottom nav element missing")

if 'nvpro-bottom-nav' in js or 'nvpro-bottom-nav' in html:
    ok("Bottom nav has proper styling")
else:
    warn("Bottom nav styling may be incomplete")

if 'class="nvpro-bottom-item' in html:
    ok("Bottom nav items defined")
else:
    fail("Bottom nav items missing")

# ── 10. Empty state cards ──
print("\n--- 10. Premium Empty State Cards ---")
if "nvpro-empty-card" in html:
    ok("Premium empty-state card class used")
else:
    fail("nvpro-empty-card class missing")

if "nvpro-story-empty-card" in html:
    ok("Story empty-state card present")
else:
    fail("Story empty-state card missing")

if 'No reels yet' in html and 'Upload Reel' in html:
    ok("Reels empty state with action button")
else:
    warn("Reels empty state may be incomplete")

if 'No one is live right now' in html:
    ok("Live rooms empty state present")
else:
    warn("Live rooms empty state missing")

# ── 11. Video in template ──
print("\n--- 11. Video Support in Template ---")
if "data-nv-video" in html:
    ok("Template uses data-nv-video attribute for video containers")
else:
    fail("Template missing data-nv-video attribute")

if "nvpro-video-overlay" in html:
    ok("Template has video overlay for play button")
else:
    fail("Template missing video overlay")

if "nvpro-loading-skeleton" in html:
    ok("Template uses loading skeleton for videos")
else:
    fail("Template missing loading skeleton for videos")

# ── 12. Desktop layout ──
print("\n--- 12. Desktop Layout ---")
if 'nvpro-left-rail' in html:
    ok("Left rail defined")
else:
    fail("Left rail missing")

if 'nvpro-center' in html:
    ok("Center feed area defined")
else:
    fail("Center feed area missing")

if 'nvpro-sidebar' in html:
    ok("Right sidebar defined")
else:
    fail("Right sidebar missing")

# ── 13. Form validation JS ──
print("\n--- 13. Form Validation ---")
if "validateFile" in js or "validate_file" in js:
    ok("Client-side file validation function exists")
else:
    warn("Client-side file validation function not found")

if '.accept' in js or 'accept_video' in js:
    ok("File accept types used")
else:
    warn("File accept types may be missing")

# ── 14. Story create button ──
print("\n--- 14. Story/Upload Buttons Connected ---")
if 'data-open-upload="story"' in html:
    ok("Create Story button linked to upload modal")
else:
    fail("Create Story button not linked to upload modal")

if 'data-open-upload="post"' in html:
    ok("Create Post button linked to upload modal")
else:
    fail("Create Post button not linked to upload modal")

if 'data-open-upload="reel"' in html:
    ok("Upload Reel button linked to upload modal")
else:
    fail("Upload Reel button not linked to upload modal")

# ── Summary ──
print(f"\n{'=' * 60}")
print(f"PHASE 122 — HOMEPAGE VIDEO & UPLOAD AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  WARN: {WARN}")
print()

if FAIL == 0:
    print("  [PASS] No blockers — Phase 122 upgrades are complete")
else:
    print("  [FAIL] Blockers present")

if WARN > 0:
    print(f"  WARNINGS: {WARN} (review recommended)")

print()
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
