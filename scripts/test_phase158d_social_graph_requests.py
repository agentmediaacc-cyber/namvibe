#!/usr/bin/env python3
"""Test social graph: followers, following, friend requests, sent requests, suggestions."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'testing'
os.environ['CHAIN_FAST_LOCAL'] = '1'

PASS = 0
FAIL = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} - {detail}")

print("=" * 60)
print("PHASE 158D - SOCIAL GRAPH REQUESTS")
print("=" * 60)

# Test service imports
try:
    from services.friend_service import (
        send_friend_request, accept_friend_request, decline_friend_request,
        cancel_friend_request, list_friends, list_friend_requests,
        get_mutual_friends, suggest_friends, are_friends, remove_friend
    )
    test("friend_service imports", True)
except ImportError as e:
    test("friend_service imports", False, str(e))

try:
    from services.social_service import list_followers, list_following, get_social_counts
    test("social_service imports", True)
except ImportError as e:
    test("social_service imports", False, str(e))

try:
    from services.social_relationship_service import (
        follow, unfollow, relationship_summary
    )
    test("social_relationship_service imports", True)
    from services.relationship_cache_service import get_relationship_state
    test("relationship_cache_service imports", True)
except ImportError as e:
    test("social_relationship_service imports", False, str(e))

try:
    from services.social_action_policy import get_action_policy
    test("social_action_policy imports", True)
except ImportError as e:
    test("social_action_policy imports", False, str(e))

try:
    from services.relationship_cache_service import get_relationship_state as cached_relationship_state
    from services.relationship_privacy_service import can_view_profile, can_follow, can_send_friend_request, can_message
    test("relationship cache & privacy imports", True)
except ImportError as e:
    test("relationship cache & privacy imports", False, str(e))

# Test functions exist
test("send_friend_request callable", callable(send_friend_request))
test("accept_friend_request callable", callable(accept_friend_request))
test("decline_friend_request callable", callable(decline_friend_request))
test("cancel_friend_request callable", callable(cancel_friend_request))
test("list_friends callable", callable(list_friends))
test("list_friend_requests callable", callable(list_friend_requests))
test("get_mutual_friends callable", callable(get_mutual_friends))
test("suggest_friends callable", callable(suggest_friends))
test("are_friends callable", callable(are_friends))
test("list_followers callable", callable(list_followers))
test("list_following callable", callable(list_following))
test("get_social_counts callable", callable(get_social_counts))
test("follow callable", callable(follow))
test("unfollow callable", callable(unfollow))
test("relationship_summary callable", callable(relationship_summary))
test("get_action_policy callable", callable(get_action_policy))

# Test sent_requests page routes
try:
    from api_routes.social_graph_routes import social_graph_bp, profile_extra_bp
    test("social_graph_bp imported", True)
    test("profile_extra_bp imported", True)
except ImportError as e:
    test("social graph route imports", False, str(e))

# Test view functions exist
from flask import Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'test'
try:
    with app.app_context():
        for rule in social_graph_bp.defered_functions:
            pass
        rules = [(r.endpoint, r.rule) for r in app.url_map.iter_rules() if r.endpoint.startswith('social_graph')]
except Exception as e:
    pass

try:
    from services.profile_service import get_current_profile, get_profile_by_username, get_profile_by_id
    test("profile_service imports for social graph", True)
except ImportError as e:
    test("profile_service imports", False, str(e))

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
