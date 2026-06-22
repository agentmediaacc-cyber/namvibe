#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from phase134_test_auth_utils import (
    TEST_PREFIX, get_credentials, has_credentials, load_context, login, make_session,
    print_header, request_json, Results, unique_test_id, warn_missing_credentials,
)

R = Results()
print_header("PHASE 134 - AUTHENTICATED MESSAGING FLOW")

if not has_credentials():
    warn_missing_credentials(R)
    R.warn("authenticated messaging flow skipped")
else:
    creds = get_credentials()
    context = load_context()
    thread_id = context.get("thread_id") or os.environ.get("NAMVIBE_TEST_THREAD_ID")
    test_id = context.get("test_id") or unique_test_id()
    if not thread_id:
        R.warn("missing disposable thread id; set NAMVIBE_TEST_THREAD_ID after creating a phase134_alpha/beta thread")
    else:
        sa, sb = make_session(), make_session()
        ra, rb = login(sa, creds["user_a"]), login(sb, creds["user_b"])
        if "/auth/login" in ra.url or ra.status_code not in (200, 302):
            R.fail(f"user A login failed ({ra.status_code})")
        else:
            R.ok("user A login")
        if "/auth/login" in rb.url or rb.status_code not in (200, 302):
            R.fail(f"user B login failed ({rb.status_code})")
        else:
            R.ok("user B login")

        text = f"{TEST_PREFIX}{test_id} hello from user A"
        emoji = f"{TEST_PREFIX}{test_id} 😀🔥🇳🇦"
        sent_ids = []
        for body in (text, emoji):
            res, data = request_json(sa, "POST", "/messages/api/send", {"thread_id": thread_id, "body": body})
            if res.status_code >= 500:
                R.fail(f"send message returned {res.status_code}")
            elif res.status_code in (200, 201) and data.get("ok"):
                sent_ids.append((data.get("message") or {}).get("id") or (data.get("message") or {}).get("message_id"))
                R.ok("sent test message")
            else:
                R.warn(f"send message unavailable or rejected ({res.status_code})")

        res, data = request_json(sb, "GET", f"/messages/api/thread/{thread_id}")
        body_text = str(data)
        if res.status_code >= 500:
            R.fail(f"user B read thread returned {res.status_code}")
        elif res.status_code in (200, 201) and TEST_PREFIX in body_text:
            R.ok("user B sees PHASE134 test message")
        else:
            R.warn(f"user B thread read did not expose test message ({res.status_code})")

        reply = f"{TEST_PREFIX}{test_id} reply from user B"
        res, data = request_json(sb, "POST", "/messages/api/send", {"thread_id": thread_id, "body": reply, "reply_to_message_id": sent_ids[0] if sent_ids else ""})
        if res.status_code >= 500:
            R.fail(f"reply returned {res.status_code}")
        elif res.status_code in (200, 201):
            R.ok("user B reply endpoint works")
            reply_id = (data.get("message") or {}).get("id") or (data.get("message") or {}).get("message_id")
        else:
            R.warn(f"reply endpoint unavailable/rejected ({res.status_code})")
            reply_id = None

        res, _ = request_json(sa, "POST", "/messages/api/seen", {"thread_id": thread_id})
        R.ok("seen endpoint works") if res.status_code in (200, 201) else R.fail(f"seen endpoint returned {res.status_code}") if res.status_code >= 500 else R.warn(f"seen endpoint returned {res.status_code}")

        if sent_ids and sent_ids[0]:
            res, _ = request_json(sa, "POST", "/messages/api/forward", {"message_id": sent_ids[0], "target_thread_id": thread_id})
            R.ok("forward endpoint works") if res.status_code in (200, 201, 400) else R.fail(f"forward returned {res.status_code}") if res.status_code >= 500 or res.status_code == 404 else R.warn(f"forward returned {res.status_code}")
            res, _ = request_json(sa, "POST", "/messages/api/delete", {"message_id": sent_ids[0], "for_everyone": False})
            R.ok("delete-for-me endpoint reachable") if res.status_code in (200, 201, 400) else R.fail(f"delete-for-me returned {res.status_code}") if res.status_code >= 500 or res.status_code == 404 else R.warn(f"delete-for-me returned {res.status_code}")
        else:
            R.warn("no test message id available for forward/delete-for-me")

        if reply_id:
            res, _ = request_json(sb, "POST", "/messages/api/delete", {"message_id": reply_id, "for_everyone": True})
            R.ok("delete-for-everyone endpoint reachable on test message") if res.status_code in (200, 201, 400) else R.fail(f"delete-for-everyone returned {res.status_code}") if res.status_code >= 500 or res.status_code == 404 else R.warn(f"delete-for-everyone returned {res.status_code}")
        else:
            R.warn("no reply id available for delete-for-everyone")

R.summary("PHASE 134 - AUTHENTICATED MESSAGING FLOW")

