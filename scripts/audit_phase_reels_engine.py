#!/usr/bin/env python3
"""Phase 4 Reels Engine Audit — 30+ checks"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import importlib

checks_passed = 0
checks_failed = 0

def check(desc, ok):
    global checks_passed, checks_failed
    if ok:
        checks_passed += 1
        print(f"  PASS  {desc}")
    else:
        checks_failed += 1
        print(f"  FAIL  {desc}")

def check_module(mod_name, symbols):
    try:
        mod = importlib.import_module(mod_name)
        for sym in symbols:
            check(f"{mod_name} has {sym}", hasattr(mod, sym))
        return mod
    except Exception as e:
        check(f"import {mod_name}", False)
        print(f"    ERROR: {e}")
        return None

print("=" * 60)
print("Phase 4 Reels Engine Audit")
print("=" * 60)

# 1. services/reels_engine.py
eng = check_module("services.reels_engine", [
    "get_reels_feed", "get_reel_detail", "get_next_reels",
    "track_reel_watch", "like_reel_v2", "unlike_reel",
    "save_reel", "unsave_reel", "share_reel_v2",
    "note_reel_comment", "get_reel_comments_summary",
    "get_creator_reel_stats", "rank_reels_for_viewer",
])

# 2. api_routes/reels_routes.py
routes = check_module("api_routes.reels_routes", [
    "reels_bp",
])

# Check route registrations by inspecting the module source
if routes:
    import inspect
    src = inspect.getsource(routes)
    expected_routes = [
        "api_reel_detail", "api_next_reels", "api_watch_v2",
        "api_like_v2", "api_save_v2", "api_share_v2",
        "api_creator_stats", "api_comments_summary",
        "api_feed_v2", "api_track_activity",
    ]
    for func_name in expected_routes:
        check(f"route handler {func_name} defined", func_name in src)

# 3. Static files
import os.path as osp
static_dir = osp.join(osp.dirname(__file__), "..", "static")
js_files = [("js", "namvibe_reels_engine.js"), ("css", "namvibe_reels_engine.css")]
for folder, fname in js_files:
    fpath = osp.join(static_dir, folder, fname)
    check(f"static/{folder}/{fname} exists", osp.isfile(fpath))

# 4. Migration script
mig_path = osp.join(osp.dirname(__file__), "migrations", "create_reels_engine_tables.sql")
check(f"migration script exists", osp.isfile(mig_path))

# 5. Template references
base_path = osp.join(osp.dirname(__file__), "..", "templates", "base.html")
if osp.isfile(base_path):
    with open(base_path) as f:
        content = f.read()
    check("base.html links namvibe_reels_engine.css", "namvibe_reels_engine.css" in content)

reels_tmpl = osp.join(osp.dirname(__file__), "..", "templates", "reels.html")
if osp.isfile(reels_tmpl):
    with open(reels_tmpl) as f:
        content = f.read()
    check("reels.html links namvibe_reels_engine.css", "namvibe_reels_engine.css" in content)
    check("reels.html links namvibe_reels_engine.js", "namvibe_reels_engine.js" in content)

# 6. Function signatures / contract checks
if eng:
    import inspect
    for fn_name in ["get_reels_feed", "get_reel_detail", "track_reel_watch",
                     "get_creator_reel_stats", "rank_reels_for_viewer", "get_next_reels"]:
        fn = getattr(eng, fn_name, None)
        if fn and callable(fn):
            sig = str(inspect.signature(fn))
            check(f"{fn_name} signature: {sig}", True)
        else:
            check(f"{fn_name} is callable", False)

# 7. Check ranking constants
if eng:
    check("has _REEL_RANKING_SIGNALS", hasattr(eng, "_REEL_RANKING_SIGNALS"))
    if hasattr(eng, "_REEL_RANKING_SIGNALS"):
        weights = eng._REEL_RANKING_SIGNALS
        total = sum(weights.values())
        check(f"ranking weights sum to 1.0", abs(total - 1.0) < 0.01)

# 8. SQL query safety — check for SQL injection vectors
if eng:
    import re
    src_file = osp.join(osp.dirname(__file__), "..", "services", "reels_engine.py")
    if osp.isfile(src_file):
        with open(src_file) as f:
            src = f.read()
        # Check all write_query/fast_query calls use %s params
        danger = re.findall(r"(fast_query|write_query)\(\s*[\"']([^\"']*)[\"']\s*%", src)
        check(f"no unsafe string-format SQL queries", len(danger) == 0)

print()
print(f"Results: {checks_passed} passed, {checks_failed} failed")
if checks_failed:
    sys.exit(1)
