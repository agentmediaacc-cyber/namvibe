#!/usr/bin/env python3
"""Phase 133 - Optional real user flow. WARN-only without disposable credentials/thread."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from phase133_reality_utils import credentials, has_pattern, print_header, read_file, route_check, Results, warn_ssl_fallback

R = Results()
print_header("PHASE 133 - OPTIONAL LIVE USER FLOW")

routes = read_file("api_routes/message_routes.py") + read_file("api_routes/message_production_routes.py") + read_file("api_routes/call_routes.py")
R.check("login route exists", has_pattern(read_file("api_routes/auth_routes.py") + read_file("templates/auth/login.html"), r"/login|def login|auth.login"), warn_only=True)
R.check("open/create thread support", has_pattern(routes, r"get_or_create_direct_thread|create.*thread|/api/inbox|message_requests"), warn_only=True)
R.check("send text/emoji/reply support", has_pattern(routes, r"/api/send|reply_to_message_id|parent_message_id"), warn_only=True)
R.check("mark seen support", has_pattern(routes, r"/api/seen|mark_thread_seen"), warn_only=True)
R.check("start/reject call support", has_pattern(routes, r"/start|/reject|api_calls_start|api_calls_reject"), warn_only=True)
R.check("missed/history support", has_pattern(routes, r"/missed|/history|missed-count"), warn_only=True)

if not credentials():
    R.warn("NAMVIBE_TEST_USER_A/B credentials missing; optional live user flow skipped")
else:
    test_thread_id = os.environ.get("NAMVIBE_TEST_THREAD_ID")
    if not test_thread_id:
        R.warn("credentials found but NAMVIBE_TEST_THREAD_ID missing; destructive live user flow skipped")
    else:
        R.warn("credentials and test thread present; HTTP session flow intentionally not enabled until CSRF/login contract is pinned")

print("\n--- Non-destructive Live Route Presence ---")
for path, method, data in [
    ("/messages/inbox", "GET", None),
    ("/messages/api/seen", "POST", {"thread_id": "PHASE133_TEST_route"}),
    ("/api/calls/start", "POST", {"receiver_id": "PHASE133_TEST_route", "call_type": "audio"}),
    ("/api/calls/reject", "POST", {"call_id": "PHASE133_TEST_route"}),
    ("/api/calls/missed", "GET", None),
    ("/api/calls/history", "GET", None),
]:
    route_check(R, path, method=method, data=data)

warn_ssl_fallback(R)
R.summary("PHASE 133 - OPTIONAL LIVE USER FLOW")

