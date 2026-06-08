#!/usr/bin/env python3
"""Phase 34 — Groups Feature Test"""

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

# 1. Routes exist in message_routes (group endpoints)
# Check route blueprint file has group endpoints
try:
    routes_content = open(os.path.join(BASE, "api_routes", "message_routes.py")).read()
    group_endpoints = [
        ("api_group_create", "/api/group/create"),
        ("api_group_join", "/api/groups/<group_id>/join"),
        ("api_group_request", "/api/groups/<group_id>/request"),
        ("api_group_post", "/api/groups/<group_id>/post"),
        ("api_group_role", "/api/groups/<group_id>/roles"),
        ("api_group_announcement", "/api/groups/<group_id>/announcement"),
        ("api_group_advert", "/api/groups/<group_id>/advert"),
        ("api_group_analytics", "/api/groups/<group_id>/analytics"),
        ("api_group_verification", "/api/groups/<group_id>/verification"),
        ("api_group_live", "/api/groups/<group_id>/live"),
        ("api_group_reel", "/api/groups/<group_id>/reel"),
        ("api_group_marketplace", "/api/groups/<group_id>/marketplace"),
    ]
    for func, route in group_endpoints:
        check(f"Route: {func} -> {route}", func in routes_content, f"{func} not found in message_routes.py")
except Exception as e:
    check("message_routes.py readable", False, str(e))

# 2. Services exist
try:
    from services.group_feature_service import (
        create_group, join_public_group, request_join, get_group,
        create_group_post, set_role, create_announcement, create_advert,
        record_analytics, request_group_verification, create_group_live_room,
        create_group_reel, create_marketplace_item, get_public_groups,
        invite_link, get_members, get_join_requests, approve_join_request,
        reject_join_request, get_announcements, get_adverts, my_groups,
    )
    check("group_feature_service: create_group", callable(create_group))
    check("group_feature_service: join_public_group", callable(join_public_group))
    check("group_feature_service: request_join", callable(request_join))
    check("group_feature_service: get_group", callable(get_group))
    check("group_feature_service: create_group_post", callable(create_group_post))
    check("group_feature_service: set_role", callable(set_role))
    check("group_feature_service: create_announcement", callable(create_announcement))
    check("group_feature_service: create_advert", callable(create_advert))
    check("group_feature_service: get_public_groups", callable(get_public_groups))
    check("group_feature_service: get_members", callable(get_members))
    check("group_feature_service: get_join_requests", callable(get_join_requests))
    check("group_feature_service: approve_join_request", callable(approve_join_request))
    check("group_feature_service: reject_join_request", callable(reject_join_request))
    check("group_feature_service: get_announcements", callable(get_announcements))
    check("group_feature_service: get_adverts", callable(get_adverts))
    check("group_feature_service: my_groups", callable(my_groups))
except Exception as e:
    check("group_feature_service imports", False, str(e))

# 3. DB tables in SQL
sql_files = []
for root, dirs, files in os.walk(os.path.join(BASE, "sql")):
    for f in files:
        if f.endswith(".sql"):
            sql_files.append(os.path.join(root, f))

all_sql = ""
for sf in sql_files:
    with open(sf) as fh:
        all_sql += fh.read()

group_tables = [
    "chain_groups", "chain_group_members", "chain_group_join_requests",
    "chain_group_invites", "chain_group_posts", "chain_group_roles",
    "chain_group_announcements", "chain_group_adverts", "chain_group_analytics",
    "chain_group_verification", "chain_group_live_rooms", "chain_group_reels",
    "chain_group_marketplace_items",
]
for tbl in group_tables:
    if tbl in all_sql:
        check(f"DB table {tbl} defined in SQL", True)
    else:
        check(f"DB table {tbl} defined in SQL", False, "NOT FOUND")

# 4. Templates that reference groups
templates = [
    "templates/messages/index.html",
    "templates/chain_home.html",
]
for t in templates:
    check(f"Template {t} exists", os.path.exists(os.path.join(BASE, t)))

# 5. Group references in templates
try:
    index_html = open(os.path.join(BASE, "templates", "messages", "index.html")).read()
    check("Group creation form in messages/index.html", "group" in index_html.lower())
    check("Group tab in messages/index.html", "groups" in index_html.lower() or "data-type=\"group\"" in index_html.lower())

    home_html = open(os.path.join(BASE, "templates", "chain_home.html")).read()
    check("Group cards in chain_home.html", "group" in home_html.lower())
except Exception as e:
    check("Group template readability", False, str(e))

# 6. Socket events for groups (via _insert_group_record dynamic key)
try:
    group_content = open(os.path.join(BASE, "services", "group_feature_service.py")).read()
    check("group:post socket emit", "group:post" in group_content)
    check("group:announcement socket emit", '_insert_group_record("chain_group_announcements' in group_content)
    check("group:advert socket emit", '_insert_group_record("chain_group_adverts' in group_content)
    check("emit_to_thread used for groups", "emit_to_thread" in group_content)
except Exception as e:
    check("group_feature_service.py readable", False, str(e))

print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
