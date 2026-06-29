#!/usr/bin/env python3
"""Phase 6 — Live Streaming + Gifts Audit Script (41 checks)"""

import importlib.util
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0
ERRORS = []


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {label}")
    else:
        FAIL += 1
        msg = f"  ❌ {label}" + (f" — {detail}" if detail else "")
        ERRORS.append(msg)
        print(msg)


def check_import(label, module_path):
    try:
        spec = importlib.util.spec_from_file_location(label, module_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod, True
    except Exception:
        pass
    return None, False


print("\n═══ Phase 6 — Live Streaming + Gifts Audit ═══\n")

# 1. Migration script
print("── Migration Script ──")
mig_path = "scripts/migrations/create_live_engine_tables.sql"
check("Migration script exists", os.path.isfile(mig_path))
with open(mig_path) as f:
    sql = f.read()
check("Migration uses CREATE TABLE IF NOT EXISTS", "CREATE TABLE IF NOT EXISTS" in sql, mig_path)
check("Migration has chain_live_chat_messages", "chain_live_chat_messages" in sql)
check("Migration has chain_live_reactions", "chain_live_reactions" in sql)
check("Migration has chain_live_guest_requests", "chain_live_guest_requests" in sql)
check("Migration has chain_live_gifts", "chain_live_gifts" in sql)
check("Migration has chain_live_moderation_actions", "chain_live_moderation_actions" in sql)
check("Migration uses UUID PRIMARY KEY", "UUID PRIMARY KEY" in sql)
check("Migration has no DROP", "DROP " not in sql)
check("Migration has no DELETE", "DELETE" not in sql)
check("Migration has no TRUNCATE", "TRUNCATE" not in sql)
check("Migration has ALTER TABLE safety checks (DO $$)", "DO $$" in sql or "IF NOT EXISTS" in sql)

# 2. live_engine.py
print("\n── Live Engine Service ──")
eng_path = "services/live_engine.py"
check("live_engine.py exists", os.path.isfile(eng_path))
mod, ok = check_import("live_engine", eng_path)
if ok and mod:
    expected_funcs = [
        "create_live_room", "get_live_room", "get_live_rooms", "get_trending_live_rooms",
        "start_live_room", "end_live_room",
        "join_live_room", "leave_live_room", "get_live_viewers", "update_viewer_count",
        "request_guest_slot", "approve_guest_request", "reject_guest_request", "remove_guest",
        "add_cohost", "remove_cohost", "get_cohosts",
        "send_live_chat", "get_live_chat_messages", "delete_live_chat_message", "pin_live_chat_message",
        "send_live_reaction", "get_live_reactions",
        "send_live_gift", "get_live_gift_leaderboard", "get_live_gift_catalog",
        "moderate_live_user", "is_user_banned",
        "get_live_analytics", "get_creator_live_analytics",
    ]
    for func in expected_funcs:
        check(f"live_engine has {func}()", hasattr(mod, func), func)
    check("live_engine imports live_service", "from services.live_service import" in open(eng_path).read())
    check("live_engine imports socketio_service", "from services.socketio_service import" in open(eng_path).read())
    check("live_engine imports performance_monitor", "from services.performance_monitor import" in open(eng_path).read())
    check("live_engine imports relationship_gate", "from services.relationship_gate_service import" in open(eng_path).read())
    check("live_engine uses @_track_op decorator", "@_track_op" in open(eng_path).read())
    check("live_engine calls track_timing", "track_timing" in open(eng_path).read())
    check("live_engine has wallet fallback (_wallet_available)", hasattr(mod, "_wallet_available"))
    check("live_engine has wallet_disabled in _deduct_coins_wallet", '"wallet_disabled"' in open(eng_path).read())
else:
    check("live_engine imports cleanly", False, str(sys.exc_info()))

# 3. live_routes.py
print("\n── Live Routes ──")
routes_path = "api_routes/live_routes.py"
check("live_routes.py exists", os.path.isfile(routes_path))
routes_content = open(routes_path).read()
check("Routes import live_engine", "from services.live_engine import" in routes_content)
phase6_routes = [
    "/api/live/trending",
    "/api/live/<room_id>/viewers",
    "/api/live/<room_id>/reactions",
    "/api/live/<room_id>/chat",
    "/api/live/<room_id>/chat/<message_id>/delete",
    "/api/live/<room_id>/chat/<message_id>/pin",
    "/api/live/guest/<request_id>/approve",
    "/api/live/guest/<request_id>/reject",
    "/api/live/<room_id>/guest/<profile_id>/remove",
    "/api/live/<room_id>/gift/leaderboard",
    "/api/live/<room_id>/analytics",
    "/api/live/analytics/creator",
]
for route in phase6_routes:
    route_name = route.split("/")[-1].replace("<", "").replace(">", "").replace("_", " ")
    check(f"Routes has {route_name} endpoint", route in routes_content or route.replace("/api/live/", "").replace("/", "_") in routes_content)

# 4. CSS
print("\n── Live Engine CSS ──")
css_path = "static/css/namvibe_live_engine.css"
check("namvibe_live_engine.css exists", os.path.isfile(css_path))
css = open(css_path).read()
check("CSS has .live-grid", ".live-grid" in css)
check("CSS has .live-chat-message", ".live-chat-message" in css)
check("CSS has .live-gift-drawer", ".live-gift-drawer" in css)
check("CSS has .live-reaction-btn", ".live-reaction-btn" in css)
check("CSS has .live-moderation-menu", ".live-moderation-menu" in css)
check("CSS has floatUp animation", "@keyframes floatUp" in css)
check("CSS has shimmer animation", "@keyframes shimmer" in css)
check("CSS has media queries", "@media" in css)
check("CSS has mobile breakpoints", "@media (max-width: 768px)" in css)

# 5. JS
print("\n── Live Engine JS ──")
js_path = "static/js/namvibe_live_engine.js"
check("namvibe_live_engine.js exists", os.path.isfile(js_path))
js = open(js_path).read()
check("JS has LiveEngine global", "window.LiveEngine" in js)
check("JS has initRoom", "initRoom" in js)
check("JS has sendChat", "sendChat" in js)
check("JS has sendReaction", "sendReaction" in js)
check("JS has openGiftDrawer", "openGiftDrawer" in js)
check("JS has sendGift", "sendGift" in js)
check("JS has moderateUser", "moderateUser" in js)
check("JS has Socket.IO integration", "io(" in js or "socket.on" in js)
check("JS has fetchJSON helper", "fetchJSON" in js)
check("JS has postJSON helper", "postJSON" in js)
check("JS has reconnect logic", "reconnect" in js)
check("JS has toast system", "showToast" in js)
check("JS has floating reaction animation", "live-floating-reaction" in js)

# Summary
print(f"\n═══ Results: {PASS} passed, {FAIL} failed ═══\n")
for err in ERRORS:
    print(err)
print(f"\n{PASS}/{PASS + FAIL} checks passed")

if FAIL > 0:
    sys.exit(1)
