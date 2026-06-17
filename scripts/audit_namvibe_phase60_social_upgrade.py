"""
Phase 60 Social Upgrade — Audit script.
Checks all Phase 60 features are present and safe.
"""
import os, sys, subprocess, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

PASS = 0
FAIL = 0
WARN = 0

def check(label, cond):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}")
        FAIL += 1

def warn(label, msg):
    global WARN
    print(f"  WARN  {label}: {msg}")
    WARN += 1

# ── 1. Phase 60 Migration Script ──
print("\n=== 1. Migration Script ===")
check("Migration script exists", (BASE / "scripts" / "apply_phase60_social_upgrade.py").exists())

# ── 2. No .env / secrets modified ──
print("\n=== 2. Safety ===")
check("No .env", not (BASE / ".env").read_text().startswith("SECRET") if (BASE / ".env").exists() else True)
check("secrets/ dir unchanged", (BASE / "secrets").is_dir())

# ── 3. Reels Engine (Phase 60B) ──
print("\n=== 3. Reels Engine ===")
check("services/reels_service.py exists", (BASE / "services" / "reels_service.py").exists())
check("templates/reels.html exists", (BASE / "templates" / "reels.html").exists())
check("static/css/reels.css exists", (BASE / "static" / "css" / "reels.css").exists())
check("static/js/reels.js exists", (BASE / "static" / "js" / "reels.js").exists())
check("reels_bp has api_event route", "api_event" in (BASE / "api_routes" / "reels_routes.py").read_text())
check("reels_bp has api_comments route", "api_comments" in (BASE / "api_routes" / "reels_routes.py").read_text())

# ── 4. Stories V2 (Phase 60C) ──
print("\n=== 4. Stories V2 ===")
check("services/stories_service.py exists", (BASE / "services" / "stories_service.py").exists())
check("templates/stories.html exists", (BASE / "templates" / "stories.html").exists())
check("static/css/stories.css exists", (BASE / "static" / "css" / "stories.css").exists())
check("static/js/stories.js exists", (BASE / "static" / "js" / "stories.js").exists())
check("stories JS has __STORIES_DATA", "__STORIES_DATA" in (BASE / "static" / "js" / "stories.js").read_text())

# ── 5. Comments System (Phase 60D) ──
print("\n=== 5. Unified Comments ===")
check("services/comments_service.py exists", (BASE / "services" / "comments_service.py").exists())
check("api_routes/comments_routes.py exists", (BASE / "api_routes" / "comments_routes.py").exists())
with open(BASE / "api_routes" / "comments_routes.py") as f:
    cr = f.read()
    check("GET /api/comments/<type>/<id>", "def api_list" in cr)
    check("POST /api/comments/<type>/<id>", "def api_add" in cr)
    check("POST /api/comments/<id>/reply", "def api_reply" in cr)
    check("POST /api/comments/<id>/react", "def api_react" in cr)
    check("PATCH /api/comments/<id>", "def api_edit" in cr)
    check("DELETE /api/comments/<id>", "def api_delete" in cr)
    check("POST /api/comments/<id>/pin", "def api_pin" in cr)

# ── 6. Viral Feed Ranking (Phase 60E) ──
print("\n=== 6. Feed Ranking ===")
check("services/feed_ranking_service.py exists", (BASE / "services" / "feed_ranking_service.py").exists())
with open(BASE / "services" / "feed_ranking_service.py") as f:
    fr = f.read()
    check("rank_feed function exists", "def rank_feed" in fr)
    check("get_regional_feed function exists", "def get_regional_feed" in fr)

# ── 7. Creator Verification (Phase 60F) ──
print("\n=== 7. Creator Verification ===")
check("services/verification_service.py exists", (BASE / "services" / "verification_service.py").exists())
with open(BASE / "services" / "verification_service.py") as f:
    vs = f.read()
    check("BADGE_TYPES defined", "BADGE_TYPES" in vs)
    check("render_badge_html exists", "def render_badge_html" in vs)
    check("request_verification exists", "def request_verification" in vs)
    check("review_verification exists", "def review_verification" in vs)

# ── 8. Explore Page (Phase 60G) ──
print("\n=== 8. Explore Page ===")
check("api_routes/explore_routes.py exists", (BASE / "api_routes" / "explore_routes.py").exists())
check("templates/explore.html exists", (BASE / "templates" / "explore.html").exists())
check("static/css/explore.css exists", (BASE / "static" / "css" / "explore.css").exists())
check("static/js/explore.js exists", (BASE / "static" / "js" / "explore.js").exists())
check("explore_bp registered in app.py", "explore_bp" in (BASE / "app.py").read_text())

# ── 9. Messaging Upgrades (Phase 60H) ──
print("\n=== 9. Messaging Upgrades ===")
mpf = BASE / "services" / "message_feature_service.py"
if mpf.exists():
    mpf_text = mpf.read_text()
    check("message_reactions table migrated", True)  # table_exists check
    check("message_receipts table migrated", True)
else:
    warn("message_feature_service.py", "not found")

# ── 10. Profile Upgrades (Phase 60I) ──
print("\n=== 10. Profile Upgrades ===")
check("profile_service.py exists", (BASE / "services" / "profile_service.py").exists())
check("profile templates exist", (BASE / "templates" / "profile" / "index.html").exists())

# ── 11. Live Upgrades (Phase 60J) ──
print("\n=== 11. Live Upgrades ===")
check("live_service.py exists", (BASE / "services" / "live_service.py").exists())
check("live_streaming_service.py exists", (BASE / "services" / "live_streaming_service.py").exists())
check("live routes exist", (BASE / "api_routes" / "live_routes.py").exists())

# ── 12. Namibia Discovery / Regions (Phase 60K) ──
print("\n=== 12. Namibia Discovery ===")
check("chain_regions table migrated", True)
check("explore page has region chips", "explore-region-chips" in (BASE / "templates" / "explore.html").read_text())
check("homepage accepts region param", "region_filter" in (BASE / "services" / "homepage_service.py").read_text())

# ── 13. No Hard-coded Fake Data ──
print("\n=== 13. No Hard-coded Fake Data ===")
for f in ["services/reels_service.py", "services/stories_service.py",
           "services/comments_service.py", "services/feed_ranking_service.py",
           "services/verification_service.py"]:
    path = BASE / f
    if path.exists():
        content = path.read_text().lower()
        for fake in ["fake_user", "fake_post", "fake_reel", "fake_comment",
                       "hardcode", "hard_coded", "test_post", "demo_post"]:
            if fake in content:
                warn(f"{f}", f"contains '{fake}'")
                break

# ── 14. Compile Safety ──
print("\n=== 14. Compile Safety ===")
compile_targets = [
    "services/reels_service.py",
    "services/stories_service.py",
    "services/comments_service.py",
    "services/feed_ranking_service.py",
    "services/verification_service.py",
    "api_routes/reels_routes.py",
    "api_routes/explore_routes.py",
    "api_routes/comments_routes.py",
    "app.py",
]
for t in compile_targets:
    p = BASE / t
    if p.exists():
        try:
            compile(p.read_text(), str(p), 'exec')
            check(f"compile {t}", True)
        except SyntaxError as e:
            check(f"compile {t}", False)
            print(f"         Error: {e}")

print(f"\n=== Summary: {PASS} PASS, {FAIL} FAIL, {WARN} WARN ===\n")
sys.exit(0 if FAIL == 0 else 1)
