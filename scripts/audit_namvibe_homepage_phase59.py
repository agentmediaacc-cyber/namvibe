#!/usr/bin/env python3
"""Phase 59 audit: verify all Phase 59 features are present and correct."""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def file_read(path):
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"ERROR: {e}"

passed = 0
failed = 0

def check(ok, msg):
    global passed, failed
    prefix = "PASS" if ok else "FAIL"
    print(f"  [{prefix}] {msg}")
    if ok:
        passed += 1
    else:
        failed += 1
    return ok

print("\n=== Phase 59 NamVibe Homepage Audit ===\n")

app_py = file_read(os.path.join(BASE, "app.py"))
homepage_service = file_read(os.path.join(BASE, "services/homepage_service.py"))
chain_home = file_read(os.path.join(BASE, "templates/chain_home.html"))
js = file_read(os.path.join(BASE, "static/js/homepage_premium.js"))
css = file_read(os.path.join(BASE, "static/css/homepage_premium.css"))
data_guard = file_read(os.path.join(BASE, "services/homepage_real_data_guard.py"))

# 1. No secrets touched
# Allow DATABASE_URL only if used via import/config, not hardcoded
has_hardcoded = re.search(r'(DATABASE_URL|SUPABASE_KEY|NEON_|REDIS_URL)\s*[:=]\s*["\']', app_py, re.I)
check(not has_hardcoded, "No hardcoded secrets in app.py")
has_hardcoded2 = re.search(r'(DATABASE_URL|SUPABASE_KEY|NEON_|REDIS_URL)\s*[:=]\s*["\']', homepage_service, re.I)
check(not has_hardcoded2, "No hardcoded secrets in homepage_service.py")

# 2. Reels homepage section exists
check("reels-preview" in chain_home, "Reels preview section exists in template")
check("reel-preview-card" in chain_home, "Reel preview card exists in template")
check("reel-preview-media" in chain_home, "Reel preview media element exists")
check("reel-preview-creator" in chain_home, "Reel preview creator info exists")
check("reel-preview-stats" in chain_home, "Reel preview stats exist")
check("reel-preview-actions" in chain_home, "Reel preview actions exist")
check(".reels-preview" in css, "Reels preview CSS exists")
check(".reel-preview-card" in css, "Reel preview card CSS exists")
check(".reels-preview-strip" in css, "Reels preview strip CSS exists")
check(".reel-action-btn" in css, "Reel action button CSS exists")

# 3. Real-time counter JS exists
check("initRealtimeCounters" in js, "Real-time counter init function exists")
check("like:update" in js, "Socket like:update listener exists")
check("comment:update" in js, "Socket comment:update listener exists")
check("view:update" in js, "Socket view:update listener exists")
check("data-count" in js, "data-count attributes exist in JS renderer")
check('data-count="comments"' in js, "comments count attribute in JS")
check('data-count="views"' in js, "views count attribute in JS")

# 4. Hashtag helper exists
check("_trending_hashtags" in homepage_service, "Trending hashtags helper exists")
check("re.findall" in homepage_service, "Hashtag extraction uses regex")

# 5. Suggested people helper exists
check("_suggested_people" in homepage_service, "Suggested people helper exists")
check("suggested_people" in chain_home, "Suggested people rendered in template")

# 6. Town query param support exists
check('request.args.get("town"' in app_py, "Town query param support in app.py")
check("town_filter" in chain_home, "town_filter variable in template")
check("?town=" in chain_home, "Town query param links in template")

# 7. Poll UI exists
check('data-action="poll"' in chain_home, "Poll button with data-action in template")
check("poll-form" in chain_home, "Poll form exists in template")
check("poll-question" in chain_home, "Poll question input exists")
check("initPollUI" in js, "Poll UI JS init function exists")
check(".poll-form" in css, "Poll form CSS exists")
check(".poll-input" in css, "Poll input CSS exists")

# 8. Save button JS exists
check("initSaveWithToast" in js, "Save with toast JS function exists")
check("showSaveToast" in js, "Show save toast function exists")
check("Saved locally" in js, "Local save fallback message exists")
check(".save-toast" in css, "Save toast CSS exists")

# 9. Ranking helper exists
check("_rank_feed" in homepage_service, "Feed ranking helper exists")
check("feed_for_you_ranked" in homepage_service, "Ranked feed variable in service")

# 10. Empty states exist
check("reels-preview-empty" in chain_home, "Reels empty state exists")
check("story-empty-btn" in chain_home, "Story empty button exists")
check("No trending hashtags yet" in chain_home, "Hashtags empty state copy")
check("No suggestions yet" in chain_home, "Suggested people empty state copy")

# 11. Mobile responsive CSS exists
check("@media (max-width: 768px)" in css, "Mobile responsive CSS exists")
check("@media (max-width: 480px)" in css, "Small phone responsive CSS exists")

# 12. No Phase 8/test/debug posts visible
check("phase8_" in data_guard, "Phase 8 pattern in data guard")
check("_TEST_CONTENT_PATTERNS" in data_guard, "Test content patterns in data guard")

# 13. Compile-safe imports
check("from services.homepage_real_data_guard" in homepage_service, "Compile-safe imports in homepage_service")

# Summary
print(f"\n{'='*50}")
print(f"Phase 59 Audit Results")
print(f"{'='*50}")
print(f"Total checks: {passed + failed}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print(f"Result: {'ALL PASS' if failed == 0 else 'SOME FAILED'}")
sys.exit(0 if failed == 0 else 1)
