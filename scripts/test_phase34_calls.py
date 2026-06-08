#!/usr/bin/env python3
"""Phase 34 — Calls Feature Test"""

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
    from api_routes.call_routes import call_bp
    check("call_routes blueprint exists", True)
except Exception as e:
    check("call_routes blueprint exists", False, str(e))

# 2. Services exist
try:
    from services.call_service import (
        start_call, answer_call, end_call, reject_call,
        list_recent_calls, add_participant, record_call_event, check_call_timeouts
    )
    check("call_service: start_call", callable(start_call))
    check("call_service: answer_call", callable(answer_call))
    check("call_service: end_call", callable(end_call))
    check("call_service: reject_call", callable(reject_call))
    check("call_service: list_recent_calls", callable(list_recent_calls))
    check("call_service: add_participant", callable(add_participant))
    check("call_service: record_call_event", callable(record_call_event))
except Exception as e:
    check("call_service imports", False, str(e))

try:
    from services.call_feature_service import (
        start_call as f_start, start_group_call, answer_call as f_answer,
        end_call as f_end, recent_calls, get_call, add_participant as f_add,
        record_quality_event, save_device_settings, save_recording_setting,
        record_call_waiting, record_event
    )
    check("call_feature_service: start_call", callable(f_start))
    check("call_feature_service: start_group_call", callable(start_group_call))
    check("call_feature_service: answer_call", callable(f_answer))
    check("call_feature_service: end_call", callable(f_end))
    check("call_feature_service: recent_calls", callable(recent_calls))
    check("call_feature_service: get_call", callable(get_call))
    check("call_feature_service: record_quality_event", callable(record_quality_event))
    check("call_feature_service: save_device_settings", callable(save_device_settings))
    check("call_feature_service: record_call_waiting", callable(record_call_waiting))
except Exception as e:
    check("call_feature_service imports", False, str(e))

# 3. Templates exist
templates = [
    "templates/calls/recent.html",
    "templates/calls/video.html",
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

call_tables = [
    "chain_call_sessions", "chain_call_participants", "chain_call_events",
    "chain_call_quality_events", "chain_call_device_settings",
    "chain_call_recording_settings", "chain_call_waiting_events",
]
for tbl in call_tables:
    if tbl in all_sql:
        check(f"DB table {tbl} defined in SQL", True)
    else:
        check(f"DB table {tbl} defined in SQL", False, "NOT FOUND")

# 5. Socket events exist
try:
    socket_content = open(os.path.join(BASE, "services", "socket_events.py")).read()
    call_socket_events = [
        ("call:offer", "handle_call_offer"),
        ("call:answer", "handle_call_answer"),
        ("call:reject", "handle_call_reject"),
        ("call:ice-candidate", "handle_call_ice_candidate"),
        ("call:end", "handle_call_end"),
        ("call:media-state", "handle_call_media_state"),
        ("call:reconnect", "handle_call_reconnect"),
        ("call:signal", "handle_call_signal"),
        ("call:status", "handle_call_status"),
        ("call:quality", "handle_phase30_call_quality"),
        ("call:waiting", "handle_phase30_call_waiting"),
    ]
    for event, handler in call_socket_events:
        check(f"Socket event {event} -> {handler}", handler in socket_content, f"handler {handler} not found")
except Exception as e:
    check("socket_events.py readable", False, str(e))

# 6. UI controls in templates
try:
    video_html = open(os.path.join(BASE, "templates", "calls", "video.html")).read()
    recent_html = open(os.path.join(BASE, "templates", "calls", "recent.html")).read()

    ui_controls = [
        ("Mic toggle", "mic", video_html),
        ("Camera toggle", "camera", video_html),
        ("End call button", "end", video_html),
        ("Speaker toggle", "speaker", video_html),
        ("Screen share", "screen", video_html),
        ("Video element", "video", video_html),
        ("Call timer", "timer", video_html),
        ("Recent calls list", "recent", recent_html),
        ("Filter tabs", "All", recent_html),
        ("Missed filter", "Missed", recent_html),
    ]
    for name, pattern, content in ui_controls:
        check(f"UI: {name} found in template", pattern.lower() in content.lower(), f"pattern '{pattern}' not found")
except Exception as e:
    check("Call template files readable", False, str(e))

print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
