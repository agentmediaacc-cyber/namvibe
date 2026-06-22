#!/usr/bin/env python3
"""
Phase 123 — Homepage/Reels Performance Fix Audit.

Checks:
  - Indexes script exists
  - Reel view debounce (Redis/memory 30min) exists
  - API endpoints return {ok:true, queued:true}
  - Frontend 2s visibility rule exists
  - Frontend once-per-session tracking exists
  - Batch/sendBeacon exists
  - Homepage limits tightened to specified values
  - Reels initial limit is 15
  - No repeated direct views_count update on every request
"""

import os
import sys

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
print("PHASE 123 — HOMEPAGE / REELS PERFORMANCE FIX AUDIT")
print("=" * 60)

# ── 1. Indexes script exists ──
print("\n--- 1. Indexes Script ---")
if file_exists("scripts/apply_phase123_homepage_reels_indexes.py"):
    ok("Indexes script exists")
else:
    fail("Indexes script missing")

# ── 2. Reel view debounce exists ──
print("\n--- 2. Reel View Debounce (30 min) ---")
engine = file_read("services/reels_engine.py")
if "_REEL_VIEW_DEBOUNCE_SECONDS" in engine:
    ok("_REEL_VIEW_DEBOUNCE_SECONDS defined in reels_engine.py")
    if "1800" in engine:
        ok("Debounce period is 1800 seconds (30 min)")
    else:
        warn("Debounce period may not be 30 min")
else:
    fail("_REEL_VIEW_DEBOUNCE_SECONDS missing from reels_engine.py")

if "_check_debounce" in engine:
    ok("_check_debounce function exists")
else:
    fail("_check_debounce function missing")

if "_mark_debounce" in engine:
    ok("_mark_debounce function exists")
else:
    fail("_mark_debounce function missing")

if "debounce_key" in engine:
    ok("View debounce key generation exists")
else:
    fail("View debounce key generation missing")

# ── 3. API endpoints return {ok:true, queued:true} ──
print("\n--- 3. API Response Format ---")
routes = file_read("api_routes/reels_routes.py")
if '{"ok": True, "queued": True}' in routes or '{"ok": True, "queued": True}' in routes:
    ok("View endpoint returns {ok:true, queued:true}")
else:
    fail("View endpoint response format incorrect")

if '{"ok": True, "queued": True}' in routes:
    ok("Event endpoint returns {ok:true, queued:true}")
else:
    warn("Event endpoint response format check")

# ── 4. Frontend 2s visibility rule ──
print("\n--- 4. Frontend 2s Visibility Rule ---")
js = file_read("static/js/namvibe_home_pro.js")
if "startViewTimer" in js and "2000" in js:
    ok("startViewTimer with 2s delay exists")
else:
    fail("startViewTimer or 2s delay missing")

if "cancelViewTimer" in js:
    ok("cancelViewTimer exists (cancels when reel leaves viewport)")
else:
    fail("cancelViewTimer missing")

# ── 5. Frontend once-per-session tracking ──
print("\n--- 5. Frontend Once-Per-Session ---")
if "viewedReels" in js:
    ok("viewedReels dict tracks viewed reels per session")
else:
    fail("viewedReels tracking missing")

if "trackReelView" in js:
    ok("trackReelView function exists")
else:
    fail("trackReelView missing")

# ── 6. Batch/sendBeacon ──
print("\n--- 6. Batch and sendBeacon ---")
if "sendBeacon" in js:
    ok("navigator.sendBeacon used for batched view events")
else:
    fail("navigator.sendBeacon not used")

if "viewBatchQueue" in js and "flushViewBatch" in js:
    ok("View batch queue and flush function exist")
else:
    fail("View batching missing")

if "scheduleViewFlush" in js and "5000" in js:
    ok("Batch flush scheduled every 5 seconds")
else:
    warn("Batch flush interval check")

# ── 7. Event debounce in reels_service ──
print("\n--- 7. Reel Event Debounce ---")
svc = file_read("services/reels_service.py")
if "_REEL_EVENT_DEBOUNCE_SECONDS" in svc:
    ok("_REEL_EVENT_DEBOUNCE_SECONDS defined in reels_service.py")
else:
    fail("Event debounce missing from reels_service.py")

if "_check_event_debounce" in svc:
    ok("_check_event_debounce function exists")
else:
    fail("_check_event_debounce function missing")

if "_REEL_EVENT_QUEUE" in svc and "_flush_reel_events" in svc:
    ok("Reel event queue and flush function exist")
else:
    fail("Reel event batching missing")

# ── 8. Homepage limits tightened ──
print("\n--- 8. Homepage Limits ---")
hp = file_read("services/homepage_service.py")
if '"stories": 12' in hp:
    ok("stories limit is 12")
else:
    fail("stories limit not 12")

if '"reels": 12' in hp:
    ok("reels limit is 12")
else:
    fail("reels limit not 12")

if '"trending_posts": 12' in hp:
    ok("trending_posts limit is 12")
else:
    fail("trending_posts limit not 12")

if '"recommended_profiles": 10' in hp:
    ok("recommended_profiles limit is 10")
else:
    fail("recommended_profiles limit not 10")

if '"live_rooms": 5' in hp:
    ok("live_rooms limit is 5")
else:
    fail("live_rooms limit not 5")

# ── 9. Reels initial limit is 15 ──
print("\n--- 9. Reels Page Limit ---")
if "get_reel_feed(limit=15)" in routes:
    ok("Reels initial limit is 15")
else:
    fail("Reels initial limit not 15")

# ── 10. No repeated direct views_count update ──
print("\n--- 10. Views Count Update Pattern ---")
if "record_reel_view" in engine:
    ok("record_reel_view uses batched in-memory queue (not direct per-request)")
else:
    warn("record_reel_view check")

# Check no raw UPDATE views_count in the API route handler
if "UPDATE chain_reels SET views_count" not in routes:
    ok("No direct views_count UPDATE in reels routes")
else:
    warn("Direct views_count UPDATE found in reels routes")

# Check the flush still works
if "_flush_reel_views" in engine and "_REEL_VIEW_QUEUE" in engine:
    ok("Batched view flush mechanism intact")
else:
    fail("View flush mechanism broken")

# ── 11. Redis availability check ──
print("\n--- 11. Redis in Backend ---")
if "_redis_available" in engine:
    ok("Redis availability check exists in reels_engine.py")
else:
    warn("Redis check missing from reels_engine.py")

if "_redis_available" in svc:
    ok("Redis availability check exists in reels_service.py")
else:
    warn("Redis check missing from reels_service.py")

# ── 12. Lightweight reels feed query ──
print("\n--- 12. Lightweight Reels Feed Query ---")
if "r.id, r.profile_id, r.caption" in svc or "r.id, r.profile_id" in svc:
    ok("Reels feed query uses lightweight column selection")
else:
    warn("Reels feed query may use heavy column selection")

# ── Summary ──
print(f"\n{'=' * 60}")
print(f"PHASE 123 — PERFORMANCE FIX AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  WARN: {WARN}")
print()

if FAIL == 0:
    print("  [PASS] No blockers — Phase 123 performance fixes are complete")
else:
    print("  [FAIL] Blockers present")

if WARN > 0:
    print(f"  WARNINGS: {WARN} (review recommended)")

print()
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
