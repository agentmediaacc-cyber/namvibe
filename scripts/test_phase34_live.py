#!/usr/bin/env python3
"""Phase 34 — Live Streaming Feature Test"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1

# 1. Routes exist
try:
    from api_routes.live_routes import live_bp
    check("live_routes blueprint exists", True)
except Exception as e:
    check("live_routes blueprint exists", False, str(e))

try:
    from api_routes.live_media_routes import live_media_bp
    check("live_media_routes blueprint exists", True)
except Exception as e:
    check("live_media_routes blueprint exists", False, str(e))

# 2. Services exist
try:
    from services.live_service import (
        create_live_room, get_live_rooms, get_room, join_room,
        add_comment, send_gift, request_cohost, update_cohost_status,
        end_live, room_activity, get_live_room_analytics,
        add_moderator, mute_user_live, remove_user_live,
        pin_comment, get_pinned_comment,
    )
    check("live_service: create_live_room", callable(create_live_room))
    check("live_service: get_live_rooms", callable(get_live_rooms))
    check("live_service: get_room", callable(get_room))
    check("live_service: join_room", callable(join_room))
    check("live_service: add_comment", callable(add_comment))
    check("live_service: send_gift", callable(send_gift))
    check("live_service: request_cohost", callable(request_cohost))
    check("live_service: end_live", callable(end_live))
    check("live_service: room_activity", callable(room_activity))
    check("live_service: add_moderator", callable(add_moderator))
except Exception as e:
    check("live_service imports", False, str(e))

try:
    from services.live_feature_service import (
        start_live, list_live_rooms, join_live, comment_live,
        end_live as f_end, request_guest, update_guest_request,
        create_poll, vote_poll, create_battle, moderation_action,
        save_replay, create_clip, add_shopping_item,
        upsert_leaderboard, save_stream_settings,
    )
    check("live_feature_service: start_live", callable(start_live))
    check("live_feature_service: list_live_rooms", callable(list_live_rooms))
    check("live_feature_service: join_live", callable(join_live))
    check("live_feature_service: comment_live", callable(comment_live))
    check("live_feature_service: create_poll", callable(create_poll))
    check("live_feature_service: create_battle", callable(create_battle))
    check("live_feature_service: moderation_action", callable(moderation_action))
    check("live_feature_service: save_replay", callable(save_replay))
    check("live_feature_service: create_clip", callable(create_clip))
    check("live_feature_service: save_stream_settings", callable(save_stream_settings))
except Exception as e:
    check("live_feature_service imports", False, str(e))

try:
    from services.live_media_service import (
        update_live_room_media, attach_mp3_to_live,
        set_youtube_embed, toggle_comments_gifts,
    )
    check("live_media_service: update_live_room_media", callable(update_live_room_media))
    check("live_media_service: set_youtube_embed", callable(set_youtube_embed))
except Exception as e:
    check("live_media_service imports", False, str(e))

# 3. Templates exist
templates = [
    "templates/live/channels.html",
    "templates/live/studio.html",
    "templates/live/watch.html",
    "templates/live/room.html",
    "templates/live/home.html",
    "templates/live/media_controls.html",
    "templates/live/locked.html",
]
for t in templates:
    check(f"Template {t} exists", os.path.exists(os.path.join(BASE, t)))

# 4. DB tables in SQL
import re
sql_files = []
for root, dirs, files in os.walk(os.path.join(BASE, "sql")):
    for f in files:
        if f.endswith(".sql"):
            sql_files.append(os.path.join(root, f))

all_sql = ""
for sf in sql_files:
    with open(sf) as fh:
        all_sql += fh.read()

live_tables = [
    "chain_live_rooms", "chain_live_viewers", "chain_live_comments",
    "chain_live_gifts", "chain_live_guest_requests", "chain_live_polls",
    "chain_live_battles", "chain_live_moderation_actions",
    "chain_live_replays", "chain_live_clips", "chain_live_shopping_items",
    "chain_live_leaderboard", "chain_live_stream_settings",
    "chain_live_moderators", "chain_live_pinned_comments",
    "chain_gift_catalog",
]
for tbl in live_tables:
    if tbl in all_sql:
        check(f"DB table {tbl} defined in SQL", True)
    else:
        check(f"DB table {tbl} defined in SQL", False, "NOT FOUND")

# 5. Socket events
try:
    socket_content = open(os.path.join(BASE, "services", "socket_events.py")).read()
    live_socket_events = [
        ("join_live_room", "handle_join_live"),
        ("leave_live_room", "handle_leave_live"),
        ("live_chat_message", "handle_live_chat"),
        ("live_gift", "handle_live_gift"),
    ]
    for event, handler in live_socket_events:
        check(f"Socket event {event} -> {handler}", handler in socket_content, f"handler {handler} not found")
except Exception as e:
    check("socket_events.py readable", False, str(e))

# 6. UI controls
try:
    studio_html = open(os.path.join(BASE, "templates", "live", "studio.html")).read()
    watch_html = open(os.path.join(BASE, "templates", "live", "watch.html")).read()

    ui_controls = [
        ("Go Live button", "Go Live", studio_html),
        ("Camera preview", "camera", studio_html),
        ("Stream title", "title", studio_html),
        ("Chat in watch", "chat", watch_html),
        ("Gift grid", "gift", watch_html),
        ("Viewer list", "viewer", watch_html),
        ("Leaderboard", "leaderboard", watch_html),
    ]
    for name, pattern, content in ui_controls:
        check(f"UI: {name} found in template", pattern.lower() in content.lower(), f"pattern '{pattern}' not found")
except Exception as e:
    check("Live template files readable", False, str(e))

print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
