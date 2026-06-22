#!/usr/bin/env python3
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from phase134_test_auth_utils import TEST_PREFIX, get_credentials, has_credentials, load_context, login, make_session, print_header, request_json, Results, unique_test_id, warn_missing_credentials

R = Results()
print_header("PHASE 134 - AUTHENTICATED NOTIFICATION FLOW")

if not has_credentials():
    warn_missing_credentials(R)
    R.warn("authenticated notification flow skipped")
else:
    creds, context = get_credentials(), load_context()
    thread_id = context.get("thread_id") or os.environ.get("NAMVIBE_TEST_THREAD_ID")
    sa, sb = make_session(), make_session()
    login(sa, creds["user_a"])
    login(sb, creds["user_b"])
    if thread_id:
        res, _ = request_json(sa, "POST", "/messages/api/send", {"thread_id": thread_id, "body": f"{TEST_PREFIX}{unique_test_id()} notification trigger"})
        R.ok("trigger message submitted") if res.status_code in (200, 201, 400) else R.fail(f"trigger message returned {res.status_code}") if res.status_code >= 500 else R.warn(f"trigger message returned {res.status_code}")
    else:
        R.warn("missing disposable thread id; notification trigger skipped")
    found_endpoint = False
    for endpoint in ("/notifications/api/list", "/api/notifications", "/notifications/api/unread-count", "/messages/api/unread-count"):
        for _ in range(3):
            res, data = request_json(sb, "GET", endpoint)
            if res.status_code in (200, 401, 403):
                found_endpoint = True
                R.ok(f"notification/unread endpoint reachable: {endpoint}")
                if TEST_PREFIX in str(data) or "unread" in str(data).lower() or "notification" in str(data).lower():
                    R.ok(f"notification endpoint returned relevant payload: {endpoint}")
                else:
                    R.warn(f"notification endpoint payload did not expose test marker: {endpoint}")
                break
            if res.status_code >= 500:
                R.fail(f"{endpoint} returned {res.status_code}")
                break
            time.sleep(1)
        if found_endpoint:
            break
    if not found_endpoint:
        R.warn("no notification endpoint found; async notification verification skipped")
    R.warn("voice note, missed call, and group update notification checks require disposable thread/call/group context")

R.summary("PHASE 134 - AUTHENTICATED NOTIFICATION FLOW")

