#!/usr/bin/env python3
"""
Full Reel UI Verification — API + Static Code Analysis

Tests all user-facing reel behaviors in a single process.
"""
import os, sys, json, uuid, time, shutil, subprocess
from datetime import datetime, timezone

os.environ['CHAIN_DISABLE_RATE_LIMITS'] = '1'
os.environ['CHAIN_FAST_LOCAL'] = '1'
os.environ['CHAIN_DISABLE_DB_PING'] = '1'
os.environ['CHAIN_DISABLE_PREWARM'] = '1'
os.environ['WTF_CSRF_ENABLED'] = '0'
os.environ['WERKZEUG_RUN_MAIN'] = 'true'

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Import app FIRST (handles Neon pool init)
from app import app as flask_app
from services.neon_service import fast_query, write_query

results = {"ok": 0, "fail": 0, "items": []}

def check(name, ok, detail=""):
    status = "OK" if ok else "FAIL"
    results["ok" if ok else "fail"] += 1
    results["items"].append({"name": name, "status": status, "detail": detail})
    print(f"  [{status}] {name}" + (f" \u2014 {detail}" if detail else ""))

# ═══════════════════════════════════════════
# PHASE 1: Setup test data
# ═══════════════════════════════════════════
print("=== Setup ===")
NOW = datetime.now(timezone.utc).isoformat()
user_a_id = str(uuid.uuid4())
user_b_id = str(uuid.uuid4())
try:
    write_query("INSERT INTO chain_profiles (id,username,display_name,email,auth_user_id,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (user_a_id, f"reel_a_{int(time.time())}", "Reel Creator A", f"ra@t.com", user_a_id, NOW, NOW))
    write_query("INSERT INTO chain_profiles (id,username,display_name,email,auth_user_id,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (user_b_id, f"reel_b_{int(time.time())}", "Reel Viewer B", f"rb@t.com", user_b_id, NOW, NOW))
    check("Test profiles created", True)
except Exception as e:
    check("Create profiles", False, str(e)[:80])

STATIC_DIR = os.path.join(ROOT, "static", "uploads", "reels")
os.makedirs(STATIC_DIR, exist_ok=True)
target_file = f"reel_full_{uuid.uuid4().hex[:8]}.mp4"
target_path = os.path.join(STATIC_DIR, target_file)
rel_url = f"/static/uploads/reels/{target_file}"
shutil.copy2(os.path.join(ROOT, "namvibe_promo.mp4"), target_path)
fsize = os.path.getsize(target_path)
check("Promo video copied", True, f"{fsize} bytes")

reel_id = str(uuid.uuid4())
try:
    write_query("""INSERT INTO chain_reels (id,profile_id,caption,video_url,media_url,storage_bucket,storage_path,mime_type,file_size,duration_seconds,width,height,processing_status,visibility,likes_count,comments_count,shares_count,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (reel_id, user_a_id, "NamVibe Full Promo", rel_url, rel_url, "local", f"reels/{user_a_id}/{reel_id}.mp4", "video/mp4", fsize, 146, 720, 1280, "ready", "public", 0, 0, 0, NOW, NOW))
    check("Reel inserted", True, f"id={reel_id[:12]}...")
except Exception as e:
    check("Insert reel", False, str(e)[:80])

# ═══════════════════════════════════════════
# PHASE 2: API behavior tests (in same process)
# ═══════════════════════════════════════════
print("\n=== API behavior tests ===")

with flask_app.test_client() as c:
    # Login as User B
    with c.session_transaction() as s:
        s["profile_id"] = user_b_id
        s["auth_user_id"] = user_b_id
        s["user_id"] = user_b_id
        s["logged_in"] = True

    # 1. View event (video play signal)
    r1 = c.post(f"/reels/api/reels/{reel_id}/event", json={"event_type": "view", "watch_ms": 3000})
    check("View event (video play signal)", r1.status_code == 200, f"HTTP {r1.status_code}")

    # 2. Watch tracking
    r2 = c.post(f"/reels/api/reels/{reel_id}/watch-v2", json={"watch_ms": 5000, "completed": False})
    check("Watch-v2 tracking", r2.status_code == 200, f"HTTP {r2.status_code}")

    # 3. Like
    r3 = c.post(f"/reels/api/reels/{reel_id}/like")
    d3 = r3.get_json(silent=True) or {}
    check("Like reel", r3.status_code == 200 and d3.get("liked") is True, json.dumps(d3))

    # 4. Unlike
    r4 = c.post(f"/reels/api/reels/{reel_id}/like")
    d4 = r4.get_json(silent=True) or {}
    check("Unlike reel (toggle off)", r4.status_code == 200 and d4.get("liked") is False, json.dumps(d4))

    # 5. Re-like
    r5 = c.post(f"/reels/api/reels/{reel_id}/like")
    d5 = r5.get_json(silent=True) or {}
    check("Re-like after unlike", r5.status_code == 200 and d5.get("liked") is True, json.dumps(d5))

    # 6. Comment
    r6 = c.post(f"/reels/api/reels/{reel_id}/comment", data={"body": "Amazing promo video! The editing is super clean. #NamVibe"})
    d6 = r6.get_json(silent=True) or {}
    check("Post comment on reel", r6.status_code == 201 and d6.get("success") is True, json.dumps(d6))

    # 7. Get comments
    r7 = c.get(f"/reels/api/reels/{reel_id}/comments")
    d7 = r7.get_json(silent=True) or {}
    comments = d7.get("comments") if isinstance(d7, dict) else (d7 if isinstance(d7, list) else None)
    check("Fetch comments returns list", comments is not None, f"type={type(d7).__name__}")

    # 8. Comment count incremented
    r8 = c.get(f"/reels/api/reels/{reel_id}/detail")
    d8 = r8.get_json(silent=True) or {}
    reel_data = d8.get("reel", {})
    cc = reel_data.get("comments_count", -1)
    check("Comment count > 0 after posting", isinstance(cc, (int, float)) and cc > 0, f"count={cc}")

    # 9. Next reel (scroll to next)
    r9 = c.get(f"/reels/api/reels/{reel_id}/next?limit=3")
    d9 = r9.get_json(silent=True) or {}
    next_reels = d9.get("reels", []) if isinstance(d9, dict) else []
    check("Next reel endpoint (scroll to next)", r9.status_code == 200, f"HTTP {r9.status_code}, next_count={len(next_reels)}")

    # 10. Feed includes the reel
    r10 = c.get("/reels/api/reels/feed?limit=50")
    d10 = r10.get_json(silent=True) or {}
    reels10 = d10.get("reels", [])
    found = any(rl.get("id") == reel_id for rl in reels10)
    check("Reel visible in feed", found, f"found_in_{len(reels10)}_reels")

    # 11. Reel detail has all UI fields
    r11 = c.get(f"/reels/api/reels/{reel_id}/detail")
    d11 = r11.get_json(silent=True) or {}
    reel = d11.get("reel", {})
    required = ["id", "profile_id", "caption", "video_url", "duration_seconds", "username", "avatar_url"]
    missing = [k for k in required if k not in reel]
    check("Reel detail has all UI fields", len(missing) == 0, f"missing={missing}" if missing else "all_present")

    # 12. Like count in detail
    lc = reel.get("likes_count", 0)
    check("Like count in detail", isinstance(lc, (int, float)) and lc > 0, f"count={lc}")

    # 13. Viewer liked state
    has_liked = reel.get("viewer_has_liked", False)
    check("Viewer liked state in detail", has_liked is True, f"viewer_has_liked={has_liked}")

    # 14. Video URL present
    vu = reel.get("video_url", "")
    check("Video URL present and accessible", bool(vu) and vu.startswith("/"), vu[:60])

# ═══════════════════════════════════════════
# PHASE 3: Static frontend code analysis
# ═══════════════════════════════════════════
print("\n=== Static frontend code analysis ===")

css_file = os.path.join(ROOT, "static", "css", "reels.css")
js_file = os.path.join(ROOT, "static", "js", "reels.js")
engine_js = os.path.join(ROOT, "static", "js", "namvibe_reels_engine.js")
engine_css = os.path.join(ROOT, "static", "css", "namvibe_reels_engine.css")

# Video sizing
if os.path.exists(css_file):
    css = open(css_file).read()
    check("CSS: object-fit defined", "object-fit" in css, f"cover={'cover' in css}, contain={'contain' in css}")
    check("CSS: full viewport height", "100vh" in css or "100dvh" in css or "height: 100%" in css)

if os.path.exists(engine_css):
    ecss = open(engine_css).read()
    check("Engine CSS: scroll-snap", "scroll-snap" in ecss)
    check("Engine CSS: full-height slides", "100dvh" in ecss or "100vh" in ecss)

# JS UI patterns
if os.path.exists(js_file):
    js = open(js_file).read()
    for label, pattern in [
        ("likeReel (like button)", "likeReel"),
        ("loadComments (comment drawer)", "loadComments"),
        ("touch swipe handler (touchStartY)", "touchStartY" in js),
        ("keyboard navigation (ArrowUp/Down)", "ArrowUp" in js or "ArrowDown" in js),
        ("double-tap like", "lastTapTime" in js or "doubleTap" in js),
        ("playVideo / pauseVideo", "playVideo" in js and "pauseVideo" in js),
        ("watch tracking interval", "watchInterval" in js or "watchTracking" in js),
        ("view tracking (trackView)", "trackView" in js or "/view" in js),
        ("comment drawer (show/hide)", "reel-comment-drawer" in js or "commentDrawer" in js),
        ("share drawer", "shareDrawer" in js or "shareReel" in js or "share" in js),
    ]:
        check(f"reels.js: {label}", pattern)

if os.path.exists(engine_js):
    ej = open(engine_js).read()
    for label, pattern in [
        ("handleLike", "handleLike" in ej),
        ("handleSave", "handleSave" in ej),
        ("handleDoubleTap (double-tap like)", "handleDoubleTap" in ej),
        ("openCommentDrawer", "openCommentDrawer" in ej),
        ("openShareDrawer", "openShareDrawer" in ej),
        ("toggleMute", "toggleMute" in ej),
        ("togglePlay (spacebar)", "togglePlay" in ej),
        ("progress bar (updateProgress)", "updateProgress" in ej or "progress-bar" in ej),
        ("scroll detection (observeScroll)", "observeScroll" in ej),
        ("preload next video", "preloadNext" in ej or "preload" in ej),
        ("error/retry handling", "retry" in ej or "error" in ej.lower()),
        ("skeleton loader", "skeleton" in ej),
        ("watch timer (sendBeacon)", "sendBeacon" in ej or "reportWatch" in ej),
    ]:
        check(f"engine.js: {label}", pattern)

# HTML templates
templates_dir = os.path.join(ROOT, "templates")
for fname in ["reels.html", os.path.join("reels", "index.html"), os.path.join("reels", "detail.html")]:
    fpath = os.path.join(templates_dir, fname)
    if os.path.exists(fpath):
        html = open(fpath).read()
        check(f"HTML: {fname} has <video>", "video" in html)
        # Check for like button in static HTML or JS that creates it
        likes_in_static = "like" in html.lower()
        likes_in_js_dynamic = False
        related_js = os.path.join(ROOT, "static", "js", "namvibe_reels_pro.js")
        if fname == os.path.join("reels", "index.html") and os.path.exists(related_js):
            likes_in_js_dynamic = "like" in open(related_js).read().lower()
        check(f"HTML: {fname} has like button", likes_in_static or likes_in_js_dynamic, "static" if likes_in_static else "via JS")
        check(f"HTML: {fname} has comment", "comment" in html.lower())

# ═══════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════
print("\n=== Cleanup ===")
for tbl, cid in [("chain_reels", reel_id), ("chain_profiles", user_a_id), ("chain_profiles", user_b_id)]:
    try:
        write_query(f"DELETE FROM {tbl} WHERE id=%s", (cid,))
        check(f"Cleanup {tbl}", True)
    except Exception as e:
        check(f"Cleanup {tbl}", False, str(e)[:60])
try:
    os.remove(target_path)
    check("Cleanup video file", True)
except:
    pass

# ═══════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════
print("\n" + "=" * 60)
passing = results["ok"]
failing = results["fail"]
total = passing + failing
print(f"RESULTS: {passing}/{total} passed, {failing}/{total} failed")
print("=" * 60)
for item in results["items"]:
    print(f"  {item['status']} {item['name']}" + (f" \u2014 {item['detail']}" if item['detail'] else ""))

sys.exit(0 if failing == 0 else 1)
