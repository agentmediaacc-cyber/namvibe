#!/usr/bin/env python3
"""Phase 178: Social Experience Engine — Friend activity, stories ordering, reel interspersion, live surfacing."""

import sys, os, time, json, subprocess, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

PASS, FAIL = "PASS", "FAIL"
_total = 0
_passed = 0
_failed = 0

def check(label, condition, detail=""):
    global _total, _passed, _failed
    _total += 1
    status = PASS if condition else FAIL
    if status == PASS:
        _passed += 1
    else:
        _failed += 1
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))

def section(name):
    print(f"\n{'='*60}\n{name}\n{'='*60}")

# ── Story sort key exists ──
section("1. _fetch_stories story sort key")
try:
    from services.homepage_service import _fetch_stories
    import inspect
    src = inspect.getsource(_fetch_stories)
    check("_story_sort_key defined", "_story_sort_key" in src)
    check("followed stories prioritized", "is_followed" in src)
    check("follows_check SQL present", "SELECT following_profile_id FROM chain_follows" in src)
except Exception as e:
    check("_fetch_stories inspectable", False, str(e))

# ── Reel interspersion in rank_homepage_sections ──
section("2. Reel interspersion in rank_homepage_sections")
try:
    from services.homepage_service import rank_homepage_sections
    src = inspect.getsource(rank_homepage_sections)
    check("reel interspersion logic present", "inline_reel" in src)
    check("every 4-6 interval", "% 5 ==" in src or "% 4 ==" in src or "% 6 ==" in src)
    check("reel_pool from payload reels", "payload.get(\"reels\")" in src or "reel_pool" in src)
except Exception as e:
    check("rank_homepage_sections inspectable", False, str(e))

# ── Friend activity in _empty_homepage_payload ──
section("3. Friend activity payload integration")
try:
    from services.homepage_service import _empty_homepage_payload as _ehp
    _ = _ehp()
    check("_empty_homepage_payload callable", True)
except Exception as e:
    check("_empty_homepage_payload", False, str(e))

try:
    from services.homepage_service import get_homepage_payload
    src = inspect.getsource(get_homepage_payload)
    check("get_homepage_payload includes friend_activity", "friend_activity" in src)
    check("get_homepage_payload fetches friend_activity", "_fetch_friend_activity" in src)
except Exception as e:
    check("get_homepage_payload", False, str(e))

# ── Friend activity in API endpoint ──
section("4. Friend activity in API endpoint")
try:
    from api_routes.homepage_api import _safe_degraded_homepage_payload, _minimal_feed_payload, _fast_homepage_feed_payload
    payload = _safe_degraded_homepage_payload()
    check("_safe_degraded_homepage_payload key", "friend_activity" in payload)
    payload_min = _minimal_feed_payload()
    check("_minimal_feed_payload key", "friend_activity" in payload_min)
    src = inspect.getsource(_fast_homepage_feed_payload)
    check("_fast_homepage_feed_payload fetches friend_activity", "_fetch_friend_activity" in src)
except Exception as e:
    check("API endpoint friend_activity", False, str(e))

# ── Template has friend_activity section ──
section("5. Template friend_activity rendering")
try:
    tpl = open("templates/chain_home.html", "rb").read().decode("utf-8")
    check("friend_activity section in template", "friend_activity" in tpl)
    check("Friend activity heading present", "Friend Activity" in tpl or "Friend activity" in tpl)
    check("p.get friend_activity fallback", "\"friend_activity\")" in tpl or "friend_activity or []" in tpl)
except Exception as e:
    check("template friend_activity", False, str(e))

# ── Route shell includes friend_activity ──
section("6. Route shell includes friend_activity")
try:
    app_src = open("app.py", "rb").read().decode("utf-8")
    check("friend_activity in shell dict", '"friend_activity": []' in app_src)
    check("build_fast_shell includes friend_activity", 'friend_activity' in app_src.split('def build_fast_shell')[1].split('\n        data[')[0] if 'def build_fast_shell' in app_src else '')
except Exception as e:
    check("route shell", False, str(e))

# ── Normalized friend activity messages ──
section("7. Friend activity normalization")
try:
    from services.homepage_service import _normalize_friend_activity
    row = {"event_type": "post_liked", "target_type": "post", "p_username": "alice", "p_display_name": "", "p_avatar_url": "", "target_id": "123", "created_at": "2026-07-01T12:00:00", "id": "1", "actor_profile_id": "42"}
    norm = _normalize_friend_activity(row)
    check("normalized returned dict", isinstance(norm, dict))
    if norm:
        check("normalized item has text", bool(norm.get("text")))
        check("normalized item has action_url", bool(norm.get("action_url")))
        check("like activity text", "liked" in norm.get("text", ""))
    else:
        check("normalized works", False, "empty result")
except Exception as e:
    check("_normalize_friend_activity", False, str(e))

# ── Import sanity ──
section("8. Import sanity")
try:
    from services.homepage_service import (
        _fetch_friend_activity, _normalize_friend_activity, _activity_action_url
    )
    check("_fetch_friend_activity importable", True)
    check("_normalize_friend_activity importable", True)
    check("_activity_action_url importable", True)
except Exception as e:
    check("imports", False, str(e))

# ── HTML+CSS does not break existing structure ──
section("9. Existing structure integrity")
try:
    from services.neon_service import CHAIN_STATIC_COLUMNS
    check("chain_activity_events in static columns", "chain_activity_events" in CHAIN_STATIC_COLUMNS)
except Exception as e:
    check("CHAIN_STATIC_COLUMNS", False, str(e))

try:
    tpl = open("templates/chain_home.html", "rb").read().decode("utf-8")
    check("nv-side-card still present", "nv-side-card" in tpl)
    check("Quick links still present", "Quick links" in tpl or "Quick Links" in tpl)
    check("nv-trend links preserved", "nv-trend" in tpl)
    check("nv-bottom nav unchanged", "nv-bottom" in tpl)
    check("nv-create-modal unchanged", "nv-create-modal" in tpl)
except Exception as e:
    check("template integrity", False, str(e))

# ── Summary ──
section(f"SUMMARY: {_passed}/{_total} passed, {_failed} failed")
sys.exit(0 if _failed == 0 else 1)
