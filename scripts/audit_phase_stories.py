#!/usr/bin/env python3
"""Phase 5 Stories 2.0 Audit — 40+ checks"""

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
print("Phase 5 Stories 2.0 Audit")
print("=" * 60)

# 1. services/stories_engine.py
eng = check_module("services.stories_engine", [
    "get_story_feed", "get_grouped_stories", "get_story_detail",
    "get_stories_by_creator", "record_story_view_v2",
    "react_to_story_v2", "reply_to_story_v2",
    "record_story_analytics_event", "can_view_story_v2",
    "get_story_viewers", "get_story_analytics",
    "get_creator_story_stats", "create_story_v2", "delete_story_v2",
    "create_highlight", "get_highlights", "get_highlight_detail",
    "update_highlight", "delete_highlight", "reorder_highlights",
    "add_stories_to_highlight", "remove_story_from_highlight",
    "add_close_friend", "remove_close_friend", "get_close_friends",
    "hide_story_from", "unhide_story_from", "get_hidden_users",
])

# 2. api_routes/stories_v2_routes.py
routes = check_module("api_routes.stories_v2_routes", ["stories_bp"])

# Check route handlers
if routes:
    import inspect
    src = inspect.getsource(routes)
    expected_handlers = [
        "api_stories_feed_v2", "api_story_view_v2", "api_story_react_v2",
        "api_story_reply_v2", "api_story_analytics_event",
        "api_story_detail_v2", "api_story_analytics",
        "api_story_creator_stats", "api_story_delete_v2",
        "api_highlights_list", "api_highlight_detail",
        "api_highlight_create", "api_highlight_update",
        "api_highlight_delete", "api_highlights_reorder",
        "api_highlight_add_stories", "api_highlight_remove_story",
        "api_close_friends_list", "api_close_friend_add",
        "api_close_friend_remove",
        "api_hidden_users_list", "api_hide_from_user",
        "api_unhide_from_user", "api_story_create_v2",
    ]
    for func_name in expected_handlers:
        check(f"route handler {func_name} defined", func_name in src)

# 3. Static files
import os.path as osp
static_dir = osp.join(osp.dirname(__file__), "..", "static")
js_files = [("js", "namvibe_stories_engine.js"), ("css", "namvibe_stories_engine.css")]
for folder, fname in js_files:
    fpath = osp.join(static_dir, folder, fname)
    check(f"static/{folder}/{fname} exists", osp.isfile(fpath))

# 4. Migration script
mig_path = osp.join(osp.dirname(__file__), "migrations", "create_stories_engine_tables.sql")
check(f"migration script exists", osp.isfile(mig_path))

# 5. Template references
base_path = osp.join(osp.dirname(__file__), "..", "templates", "base.html")
if osp.isfile(base_path):
    with open(base_path) as f:
        content = f.read()
    check("base.html links namvibe_stories_engine.css", "namvibe_stories_engine.css" in content)

stories_tmpl = osp.join(osp.dirname(__file__), "..", "templates", "stories.html")
if osp.isfile(stories_tmpl):
    with open(stories_tmpl) as f:
        content = f.read()
    check("stories.html links namvibe_stories_engine.css", "namvibe_stories_engine.css" in content)
    check("stories.html links namvibe_stories_engine.js", "namvibe_stories_engine.js" in content)
    check("stories.html has nv-story-tray", "nv-story-tray" in content)
    check("stories.html has nv-story-viewer", "nv-story-viewer" in content)
    check("stories.html has nv-highlights-section", "nv-highlights-section" in content)
    check("stories.html sets __NV_PROFILE_ID", "__NV_PROFILE_ID" in content)

# 6. Function signatures
if eng:
    import inspect
    for fn_name in ["get_story_feed", "get_grouped_stories", "get_story_detail",
                     "can_view_story_v2", "get_story_analytics", "get_creator_story_stats",
                     "create_highlight", "get_highlights", "get_close_friends"]:
        fn = getattr(eng, fn_name, None)
        if fn and callable(fn):
            sig = str(inspect.signature(fn))
            check(f"{fn_name} signature: {sig}", True)
        else:
            check(f"{fn_name} is callable", False)

# 7. Existing services still importable
check_module("services.stories_service", [
    "get_stories_feed", "record_story_view", "react_to_story", "reply_to_story",
])
check_module("services.story_engagement_service", [
    "get_tray", "record_view", "set_reaction", "send_reply", "delete_story",
])

# 8. SQL query safety
if eng:
    src_file = osp.join(osp.dirname(__file__), "..", "services", "stories_engine.py")
    if osp.isfile(src_file):
        with open(src_file) as f:
            src = f.read()
        import re
        danger = re.findall(r"(fast_query|write_query)\(\s*[\"']([^\"']*)[\"']\s*%", src)
        check(f"no unsafe string-format SQL queries", len(danger) == 0)

# 9. No fake data
for folder in ["services", "api_routes"]:
    dir_path = osp.join(osp.dirname(__file__), "..", folder)
    for fname in os.listdir(dir_path):
        if fname.endswith(".py") and ("stories" in fname or "story" in fname):
            fpath = osp.join(dir_path, fname)
            with open(fpath) as f:
                content = f.read()
            for keyword in ["INSERT INTO.*VALUES.*test", "fake_", "'test@test.com'"]:
                if re.search(keyword, content, re.IGNORECASE):
                    check(f"{folder}/{fname}: no fake data", False)
                    break

print()
print(f"Results: {checks_passed} passed, {checks_failed} failed")
if checks_failed:
    sys.exit(1)
