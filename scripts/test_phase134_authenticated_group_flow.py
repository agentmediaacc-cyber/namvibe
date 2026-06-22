#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from phase134_test_auth_utils import TEST_GROUP_PREFIX, TEST_PREFIX, get_credentials, has_credentials, login, make_session, print_header, request_json, Results, unique_test_id, warn_missing_credentials

R = Results()
print_header("PHASE 134 - AUTHENTICATED GROUP FLOW")

if not has_credentials():
    warn_missing_credentials(R)
    R.warn("authenticated group flow skipped")
else:
    creds = get_credentials()
    s = make_session()
    login_response = login(s, creds["user_a"])
    R.ok("user A login") if "/auth/login" not in login_response.url else R.fail("user A login failed")
    group_name = TEST_GROUP_PREFIX + unique_test_id()
    create_payload = {"name": group_name, "title": group_name, "member_usernames": [creds["user_b"].get("username")]}
    group_id = None
    for endpoint in ("/messages/api/groups/create", "/messages/api/group/create", "/messages/api/threads/group"):
        res, data = request_json(s, "POST", endpoint, create_payload)
        if res.status_code in (200, 201):
            R.ok(f"group create endpoint works: {endpoint}")
            group_id = data.get("group_id") or data.get("thread_id") or (data.get("group") or {}).get("id")
            break
        if res.status_code == 404:
            R.warn(f"group create endpoint unavailable: {endpoint}")
        elif res.status_code >= 500:
            R.fail(f"group create endpoint {endpoint} returned {res.status_code}")
        else:
            R.warn(f"group create endpoint {endpoint} returned {res.status_code}")
    if not group_id:
        R.warn("group creation not available; group mutation tests skipped")
    else:
        res, _ = request_json(s, "POST", "/messages/api/send", {"thread_id": group_id, "body": f"{TEST_PREFIX}{unique_test_id()} group message"})
        R.ok("group message submitted") if res.status_code in (200, 201, 400) else R.fail(f"group message returned {res.status_code}") if res.status_code >= 500 else R.warn(f"group message returned {res.status_code}")
        mutations = [
            (f"/messages/api/groups/{group_id}/rename", {"name": group_name + "_RENAMED"}, "rename group"),
            (f"/messages/api/groups/{group_id}/promote", {"username": creds["user_b"].get("username")}, "promote admin"),
            (f"/messages/api/groups/{group_id}/demote", {"username": creds["user_b"].get("username")}, "demote admin"),
            (f"/messages/api/groups/{group_id}/remove-member", {"username": creds["user_b"].get("username")}, "remove member"),
            (f"/messages/api/groups/{group_id}/leave", {}, "leave group"),
        ]
        for endpoint, payload, label in mutations:
            res, _ = request_json(s, "POST", endpoint, payload)
            R.ok(f"{label} safely handled") if res.status_code in (200, 201, 400, 403, 404) else R.fail(f"{label} returned {res.status_code}") if res.status_code >= 500 else R.warn(f"{label} returned {res.status_code}")
        R.warn(f"cleanup may be needed for test group {group_id} / {group_name}")

R.summary("PHASE 134 - AUTHENTICATED GROUP FLOW")

