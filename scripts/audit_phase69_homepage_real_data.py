#!/usr/bin/env python3
"""Phase 69 audit: homepage real-data readiness — 47 checks."""

import os
import sys
import re
import importlib.util as imp

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed = 0
failed = 0

def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}" + (f"  -- {detail}" if detail else ""))

print("=" * 64)
print("Phase 69 Audit — Homepage Real-Data Readiness")
print("=" * 64)

# ── 1. _normalize_story includes media fields ──
src = open("services/homepage_service.py").read()
check("_normalize_story has media_url", '"_normalize_story"' in src or '"media_url"' in src.split("_normalize_story")[1].split("def ")[0] if "_normalize_story" in src else False, "_normalize_story not found")

# Check for media_url in _normalize_story
idx = src.find("def _normalize_story")
if idx >= 0:
    chunk = src[idx:idx+1200]
    check("_normalize_story includes media_url", '"media_url"' in chunk)
    check("_normalize_story includes video_url", '"video_url"' in chunk)
    check("_normalize_story includes thumbnail_url", '"thumbnail_url"' in chunk)
else:
    check("_normalize_story found", False, "function not defined")
    check("_normalize_story includes media_url", False)
    check("_normalize_story includes video_url", False)
    check("_normalize_story includes thumbnail_url", False)

# ── 2. _safe_current_profile has rich data ──
idx = src.find("def _safe_current_profile")
if idx >= 0:
    chunk = src[idx:idx+2500]
    check("_safe_current_profile includes followers_count", '"followers_count"' in chunk)
    check("_safe_current_profile includes following_count", '"following_count"' in chunk)
    check("_safe_current_profile includes post_count", '"post_count"' in chunk)
    check("_safe_current_profile includes wallet_balance", '"wallet_balance"' in chunk)
    check("_safe_current_profile includes unread_notifications", '"unread_notifications"' in chunk)
    check("_safe_current_profile includes is_verified", '"is_verified"' in chunk)
    check("_safe_current_profile includes is_online", '"is_online"' in chunk)
else:
    check("_safe_current_profile found", False, "function not defined")
    for label in ("followers_count", "following_count", "post_count", "wallet_balance", "unread_notifications", "is_verified", "is_online"):
        check(f"_safe_current_profile includes {label}", False)

# ── 3. Public helper functions exist ──
helpers = [
    "build_current_user_card",
    "fetch_homepage_stories",
    "fetch_homepage_reels",
    "fetch_homepage_posts",
    "fetch_trending_creators",
    "fetch_suggested_people",
    "fetch_trending_hashtags",
    "fetch_popular_towns",
]
for h in helpers:
    check(f"Public helper {h} exists", f"def {h}" in src)

# ── 4. No hardcoded test data in homepage_service.py ──
bad_patterns = ["Test User", "tester_", "Phase 8", "lorem ipsum", "fake_creator", "demo_user"]
for pat in bad_patterns:
    # Only flag patterns that are NOT in comments/strings
    matches = [line for line in src.split("\n") if pat.lower() in line.lower() and not line.strip().startswith("#")]
    check(f"No hardcoded '{pat}' in code", len(matches) == 0, f"found {len(matches)} matches" if matches else "")

# ── 5. Template check: no href="#" ──
tmpl = open("templates/chain_home.html").read()
bare_hash = re.findall(r'href\s*=\s*"#"', tmpl)
check("No href='#' in chain_home.html", len(bare_hash) == 0, f"found {len(bare_hash)} bare # links")

# ── 6. Template uses safe_link for all external links ──
check("Template uses safe_link for home", "safe_link('home'" in tmpl or "safe_link('home'" in tmpl)
check("Template uses safe_link for profile", "safe_link('profile'" in tmpl)
check("Template uses safe_link for wallet", "safe_link('wallet'" in tmpl)
check("Template uses safe_link for messages", "safe_link('messages'" in tmpl)
check("Template uses safe_link for notifications", "safe_link('notifications'" in tmpl)
check("Template uses safe_link for settings", "safe_link('settings'" in tmpl)
check("Template uses safe_link for create_story", "safe_link('create_story'" in tmpl)
check("Template uses safe_link for upload_reel", "safe_link('upload_reel'" in tmpl)

# ── 7. Template uses route_exists ──
check("Template uses route_exists for /status/create", "route_exists('/status/create')" in tmpl)
check("Template uses route_exists for /reels/upload", "route_exists('/reels/upload')" in tmpl)

# ── 8. Template current user card ──
check("Template has profile card section", "rail-profile-card" in tmpl)
check("Template uses current.avatar_url", "current.avatar_url" in tmpl)
check("Template has initials fallback", "gen-avatar" in tmpl)
check("Template shows current.full_name", "current.full_name" in tmpl)
check("Template shows current.username", "current.username" in tmpl)

# ── 9. Story strip checks ──
check("Template has story-strip", "story-strip" in tmpl)
check("Story uses /status/{{ story.id }}", "/status/{{ story.id }}" in tmpl)
check("Story has create button", "story-card--create" in tmpl)
check("Story has empty state", "story-empty" in tmpl)

# ── 10. Reels section ──
check("Template has reels-preview", "reels-preview" in tmpl)
check("Reel uses reel.video_url or reel.media_url", "reel.video_url" in tmpl and "reel.media_url" in tmpl)
check("Reel has avatar", "reel.avatar_url" in tmpl)
check("Reel has display_name", "reel.display_name" in tmpl)
check("Reel has likes_count", "reel.likes_count" in tmpl)
check("Reel has comments_count", "reel.comments_count" in tmpl)
check("Reel has view_count", "reel.view_count" in tmpl)
check("Reel has empty state", "reels-preview-empty" in tmpl)

# ── 11. Right sidebar ──
check("Template has recommended_profiles loop", "recommended_profiles[:5]" in tmpl)
check("Template has suggested_people loop", "suggested_people" in tmpl)
check("Template has trending_hashtags loop", "trending_hashtags" in tmpl)
check("Template has live_rooms section", "live_rooms" in tmpl)

# ── 12. Composer section ──
check("Template composer has Post button", "composer-action-chip" in tmpl)
check("Template composer has Reel button", "upload_reel" in tmpl)
check("Template composer has Story button", "create_story" in tmpl)
check("Template composer has Live button", "go_live" in tmpl)

# ── 13. Python compiles ──
try:
    import py_compile
    py_compile.compile("services/homepage_service.py", doraise=True)
    check("Python compile: homepage_service.py", True)
except py_compile.PyCompileError as e:
    check("Python compile: homepage_service.py", False, str(e))

# ── 14. Import helpers work ──
try:
    spec = imp.spec_from_file_location("hps", "services/homepage_service.py")
    mod = imp.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for h in helpers:
        check(f"Helper {h} is callable", callable(getattr(mod, h, None)))
except Exception as e:
    check("Import homepage_service", False, str(e))

print("-" * 64)
print(f"  {passed} passed, {failed} failed")
print("=" * 64)
sys.exit(0 if failed == 0 else 1)
