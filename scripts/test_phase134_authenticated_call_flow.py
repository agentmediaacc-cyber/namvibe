#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from phase134_test_auth_utils import get_credentials, has_credentials, login, make_session, print_header, request_json, Results, warn_missing_credentials

R = Results()
print_header("PHASE 134 - AUTHENTICATED CALL FLOW")

if not has_credentials():
    warn_missing_credentials(R)
    R.warn("authenticated call flow skipped")
else:
    creds = get_credentials()
    sa, sb = make_session(), make_session()
    ra, rb = login(sa, creds["user_a"]), login(sb, creds["user_b"])
    R.ok("user A login") if "/auth/login" not in ra.url else R.fail("user A login failed")
    R.ok("user B login") if "/auth/login" not in rb.url else R.fail("user B login failed")
    target = os.environ.get("NAMVIBE_TEST_USER_B_ID")
    if not target:
        R.warn("NAMVIBE_TEST_USER_B_ID missing; call target cannot be resolved safely")
    else:
        call_id = None
        res, data = request_json(sa, "POST", "/api/calls/start", {"receiver_id": target, "call_type": "audio"})
        if res.status_code >= 500:
            R.fail(f"audio call start returned {res.status_code}")
        elif res.status_code in (200, 201, 409):
            R.ok(f"audio call start safely handled ({res.status_code})")
            call_id = (data.get("call") or {}).get("id") or data.get("call_id")
        elif res.status_code == 404:
            R.fail("audio call start returned 404")
        else:
            R.warn(f"audio call start returned {res.status_code}")
        if call_id:
            res, _ = request_json(sb, "POST", "/api/calls/reject", {"call_id": call_id})
            R.ok("reject call endpoint works") if res.status_code in (200, 201, 404) else R.fail(f"reject call returned {res.status_code}") if res.status_code >= 500 else R.warn(f"reject call returned {res.status_code}")
            for endpoint in ("/api/calls/history", "/api/calls/missed", "/api/calls/active"):
                res, _ = request_json(sa, "GET", endpoint)
                R.ok(f"{endpoint} reachable") if res.status_code in (200, 401, 403) else R.fail(f"{endpoint} returned {res.status_code}") if res.status_code >= 500 or res.status_code == 404 else R.warn(f"{endpoint} returned {res.status_code}")
            res, _ = request_json(sa, "POST", "/api/calls/reconnect", {"call_id": call_id})
            R.ok("reconnect endpoint safely handled") if res.status_code in (200, 400, 404) else R.fail(f"reconnect returned {res.status_code}") if res.status_code >= 500 else R.warn(f"reconnect returned {res.status_code}")
            request_json(sa, "POST", "/api/calls/end", {"call_id": call_id})
            request_json(sa, "POST", "/api/calls/cancel", {"call_id": call_id})
        else:
            R.warn("no call_id returned; reject/history-on-created-call checks skipped")
        res, _ = request_json(sa, "POST", "/api/calls/safety/check", {"target_id": target})
        R.ok("call safety check reachable") if res.status_code in (200, 400, 401, 403) else R.fail(f"safety check returned {res.status_code}") if res.status_code >= 500 or res.status_code == 404 else R.warn(f"safety check returned {res.status_code}")
        res, _ = request_json(sa, "POST", "/api/calls/start", {"receiver_id": target, "call_type": "video"})
        R.ok("video call start safely handled") if res.status_code in (200, 201, 409) else R.fail(f"video call start returned {res.status_code}") if res.status_code >= 500 or res.status_code == 404 else R.warn(f"video call start returned {res.status_code}")

R.summary("PHASE 134 - AUTHENTICATED CALL FLOW")

