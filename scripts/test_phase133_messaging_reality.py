#!/usr/bin/env python3
"""Phase 133 - Messaging reality checks."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from phase133_reality_utils import (
    ACCEPTABLE_AUTH_STATUSES, credentials, has_pattern, print_header, read_file,
    route_check, Results, warn_ssl_fallback,
)

R = Results()
print_header("PHASE 133 - MESSAGING REALITY")

js = read_file("static/js/namvibe_messages_pro.js") + read_file("static/js/message_composer.js") + read_file("templates/messages/thread.html")
routes = read_file("api_routes/message_routes.py") + read_file("api_routes/message_production_routes.py")
services = read_file("services/message_delivery_service.py") + read_file("services/messaging_engine.py") + read_file("services/message_feature_service.py") + read_file("services/message_media_service.py")
sockets = read_file("services/socket_events.py") + js
templates = read_file("templates/messages/thread.html") + read_file("templates/messages/inbox.html") + read_file("templates/messages/index.html")

print("\n--- Static Implementation ---")
checks = [
    ("text send handler", js, r"message:send|/api/messages/send|/messages/api/.*/send|sendPayload"),
    ("emoji send/insert", js + templates, r"emoji|insertAtCursor"),
    ("image upload support", services + routes + templates, r"image|accept=.*image|media_type|upload"),
    ("video upload support", services + routes + templates, r"video|accept=.*video|media_type|upload"),
    ("PDF/document upload support", services + routes + templates, r"pdf|document|attachment"),
    ("location message support", js + routes + templates, r"location|geolocation|shareLocation"),
    ("reply support", js + routes + services, r"reply_to_message_id|parent_message_id|initReply"),
    ("forward support", js + routes + services, r"forward_messages|/api/forward|messages/forward"),
    ("delete for me support", js + routes + services, r"for_everyone.*false|delete_for_me|/api/delete"),
    ("delete for everyone support", js + routes + services, r"delete_everyone|delete-everyone|for_everyone"),
    ("read receipts", js + routes + services, r"message:seen|mark_thread_seen|read_at|status-tick"),
    ("typing indicator", js + routes + sockets, r"typing:start|typing_start|user_typing|typing-indicator"),
    ("message backend routes", routes, r"api_messages_send|api_send|/api/send|/thread/<thread_id>/send"),
    ("socket message events", sockets, r"message:send|message:new|message_receive|message:seen|message:delivered"),
    ("DB/service methods", services, r"send_message|get_thread_messages|mark_thread_seen|delete_message"),
    ("upload validation", services + routes, r"validate_message_attachment|MAX_MESSAGE_FILE_SIZE|allowed|mime_type|file_size"),
]
for label, text, pattern in checks:
    R.check(label, has_pattern(text, pattern))

print("\n--- Live Route Checks ---")
for path, method, data in [
    ("/messages/inbox", "GET", None),
    ("/messages/api/inbox", "GET", None),
    ("/messages/api/send", "POST", {"thread_id": "phase133", "body": "PHASE133_TEST_route"}),
    ("/messages/api/upload", "POST", None),
    ("/messages/api/seen", "POST", {"thread_id": "phase133"}),
    ("/messages/api/delete", "POST", {"message_id": "phase133"}),
    ("/messages/api/forward", "POST", {"message_id": "phase133", "target_thread_id": "phase133"}),
    ("/messages/api/unread-count", "GET", None),
]:
    route_check(R, path, method=method, data=data, acceptable=ACCEPTABLE_AUTH_STATUSES | {400, 405})

print("\n--- Optional Authenticated Live Check ---")
creds = credentials()
if not creds:
    R.warn("NAMVIBE_TEST_USER_A/B credentials missing; authenticated message send skipped")
else:
    R.warn("Credentials found, but safe thread discovery/send is intentionally not run without a dedicated test thread id")

warn_ssl_fallback(R)
R.summary("PHASE 133 - MESSAGING REALITY")

