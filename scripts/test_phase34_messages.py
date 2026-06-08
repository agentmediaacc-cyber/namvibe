#!/usr/bin/env python3
"""Phase 34 — Messaging Feature Test"""

import os
import sys
import importlib
import inspect

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
    from api_routes.message_routes import message_bp
    check("message_routes blueprint exists", True)
except Exception as e:
    check("message_routes blueprint exists", False, str(e))

try:
    from api_routes.message_production_routes import message_production_bp
    check("message_production_routes blueprint exists", True)
except Exception as e:
    check("message_production_routes blueprint exists", False, str(e))

try:
    from api_routes.message_upgrade_routes import message_upgrade_bp
    check("message_upgrade_routes blueprint exists", True)
except Exception as e:
    check("message_upgrade_routes blueprint exists", False, str(e))

# 2. Services exist
try:
    from services.message_feature_service import (
        send_text_message, get_thread_messages, add_reaction,
        edit_message, delete_message, star_message, pin_message,
        forward_messages, unread_count, mark_delivered, mark_seen,
        save_draft, schedule_message, save_shared_item, list_shared_items,
        save_voice_note, save_attachment, save_wallpaper, search_messages
    )
    check("message_feature_service: send_text_message", callable(send_text_message))
    check("message_feature_service: get_thread_messages", callable(get_thread_messages))
    check("message_feature_service: add_reaction", callable(add_reaction))
    check("message_feature_service: edit_message", callable(edit_message))
    check("message_feature_service: delete_message", callable(delete_message))
    check("message_feature_service: star_message", callable(star_message))
    check("message_feature_service: pin_message", callable(pin_message))
    check("message_feature_service: forward_messages", callable(forward_messages))
    check("message_feature_service: unread_count", callable(unread_count))
    check("message_feature_service: mark_delivered", callable(mark_delivered))
    check("message_feature_service: mark_seen", callable(mark_seen))
    check("message_feature_service: save_draft", callable(save_draft))
    check("message_feature_service: save_shared_item", callable(save_shared_item))
    check("message_feature_service: save_voice_note", callable(save_voice_note))
    check("message_feature_service: save_attachment", callable(save_attachment))
    check("message_feature_service: search_messages", callable(search_messages))
except Exception as e:
    check("message_feature_service imports", False, str(e))

try:
    from services.messaging_engine import (
        list_threads, get_thread, get_or_create_direct_thread,
        send_message, set_typing, search_messages as engine_search,
        get_stickers
    )
    check("messaging_engine: list_threads", callable(list_threads))
    check("messaging_engine: get_thread", callable(get_thread))
    check("messaging_engine: send_message", callable(send_message))
    check("messaging_engine: set_typing", callable(set_typing))
except Exception as e:
    check("messaging_engine imports", False, str(e))

try:
    from services.message_delivery_service import (
        ensure_message_tables, get_thread_messages as delivery_get,
        send_message as delivery_send, unread_count as delivery_unread
    )
    check("message_delivery_service: send_message", callable(delivery_send))
    check("message_delivery_service: unread_count", callable(delivery_unread))
except Exception as e:
    check("message_delivery_service imports", False, str(e))

# 3. Templates exist
templates = [
    "templates/messages/index.html",
    "templates/messages/thread.html",
]
for t in templates:
    check(f"Template {t} exists", os.path.exists(os.path.join(BASE, t)))

# 4. DB tables documented in SQL or defined via CREATE TABLE IF NOT EXISTS
import re
sql_content = ""
for root, dirs, files in os.walk(os.path.join(BASE, "sql")):
    for f in files:
        if f.endswith(".sql"):
            sql_content += open(os.path.join(root, f)).read()
# Also check .py files for inline CREATE TABLE IF NOT EXISTS
py_content = ""
for root, dirs, files in os.walk(os.path.join(BASE, "services")):
    for f in files:
        if f.endswith(".py"):
            py_content += open(os.path.join(root, f)).read()
all_db_defs = sql_content + py_content

message_tables = [
    "chain_message_threads", "chain_thread_members", "chain_messages",
    "chain_message_reactions", "chain_message_stars", "chain_message_edits",
    "chain_message_deletions", "chain_message_forwards", "chain_message_attachments",
    "chain_message_voice_notes", "chain_message_pins", "chain_message_drafts",
    "chain_message_scheduled", "chain_message_wallpapers", "chain_message_shared_items",
    "chain_message_autodownload_settings", "chain_message_encryption_status",
    "chain_voice_note_drafts", "chain_voice_note_playback_state",
    "chain_message_reads", "chain_message_delivery_events",
]
for tbl in message_tables:
    check(f"DB table {tbl} defined in SQL/PY", tbl in all_db_defs)

# 5. Socket events exist
try:
    socket_content = open(os.path.join(BASE, "services", "socket_events.py")).read()
    socket_events = [
        ("message:send", "handle_message_send"),
        ("message:delivered", "handle_message_delivered"),
        ("message:seen", "handle_message_seen"),
        ("message:reaction:add", "handle_add_reaction"),
        ("message:reaction:remove", "handle_remove_reaction"),
        ("message:delete", "handle_message_delete"),
        ("message:edited", "handle_phase30_message_edited"),
        ("message:pinned", "handle_phase30_message_pinned"),
        ("message:forwarded", "handle_phase30_message_forwarded"),
        ("typing:start", "handle_typing_start"),
        ("typing:stop", "handle_typing_stop"),
        ("join_thread", "handle_join_thread"),
        ("leave_thread", "handle_leave_thread"),
        ("reconnect_sync", "handle_reconnect_sync"),
    ]
    for event_name, handler in socket_events:
        check(f"Socket event {event_name} -> {handler}", handler in socket_content, f"handler {handler} not found")
except Exception as e:
    check("socket_events.py readable", False, str(e))

# 6. UI controls verified via HTML content
try:
    thread_html = open(os.path.join(BASE, "templates", "messages", "thread.html")).read()
    index_html = open(os.path.join(BASE, "templates", "messages", "index.html")).read()

    ui_controls = [
        ("Send button", 'type="submit"', thread_html),
        ("Attachment button", "attachment", thread_html),
        ("Emoji picker", "emoji", thread_html),
        ("Reaction", "reaction", thread_html),
        ("Message composer", "composer", thread_html),
        ("Groups tab", "groups", index_html),
    ]
    for name, pattern, content in ui_controls:
        check(f"UI: {name} found in template", pattern.lower() in content.lower(), f"pattern '{pattern}' not found")
except Exception as e:
    check("Message template files readable", False, str(e))

print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
