"""Phase 80 — Full Follow Privacy Integration Test."""

import os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.follow_request_service import send_follow_request, approve_follow_request, decline_follow_request
from services.relationship_privacy_service import can_view_by_rule, can_view_posts
from services.engagement_service import unfollow_profile
from services.neon_service import write_query, fast_query

PASS = 0
FAIL = 0

def check(name, condition):
    global PASS, FAIL
    if condition:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1

def run():
    print("Phase 80: Full Follow Privacy Integration")
    
    # Setup temp profiles
    UID_A = str(uuid.uuid4()) # Requester
    UID_B = str(uuid.uuid4()) # Private Target
    AUTH_A = str(uuid.uuid4())
    AUTH_B = str(uuid.uuid4())
    
    write_query("INSERT INTO chain_profiles (id, auth_user_id, username, profile_visibility) VALUES (%s, %s, %s, 'private')", (UID_B, AUTH_B, f"private_{UID_B[:8]}"))
    write_query("INSERT INTO chain_profiles (id, auth_user_id, username, profile_visibility) VALUES (%s, %s, %s, 'public')", (UID_A, AUTH_A, f"public_{UID_A[:8]}"))
    
    UID_C = str(uuid.uuid4())
    AUTH_C = str(uuid.uuid4())
    UID_D = str(uuid.uuid4())
    AUTH_D = str(uuid.uuid4())

    try:
        # 1. Private profile - cannot view posts initially
        p_target = {"id": UID_B, "profile_visibility": "private"}
        check("1. Private profile hidden initially", not can_view_posts(UID_A, p_target))
        
        # 2. Send follow request
        res = send_follow_request(UID_A, UID_B)
        check("2. Send follow request status is pending", res.get("status") == "request_pending")
        
        # 3. Still cannot view posts (pending)
        check("3. Still hidden when pending", not can_view_posts(UID_A, p_target))
        
        # 4. Approve request
        reqs = fast_query("SELECT id FROM chain_follow_requests WHERE requester_profile_id = %s AND target_profile_id = %s", (UID_A, UID_B))
        if reqs:
            approve_follow_request(reqs[0]["id"], UID_B)
            check("4. Approved follower can view posts", can_view_posts(UID_A, p_target))
        else:
            check("4. Approved follower can view posts", False)
        
        # 5. Unfollow - back to hidden
        unfollow_profile(UID_A, UID_B)
        check("5. Hidden after unfollow", not can_view_posts(UID_A, p_target))
        
        # 6. Public profile - immediate follow and view
        write_query("INSERT INTO chain_profiles (id, auth_user_id, username, profile_visibility) VALUES (%s, %s, %s, 'public')", (UID_C, AUTH_C, f"public_{UID_C[:8]}"))
        p_public = {"id": UID_C, "profile_visibility": "public"}
        
        res_pub = send_follow_request(UID_A, UID_C)
        check("6. Public follow is immediate", res_pub.get("status") == "following")
        check("7. Can view public posts", can_view_posts(UID_A, p_public))
        
        # 8. Followers-only rule check
        check("8. followers_only rule works for approved", can_view_by_rule(UID_A, UID_C, "followers_only"))
        
        # 9. Decline follow request
        write_query("INSERT INTO chain_profiles (id, auth_user_id, username, profile_visibility) VALUES (%s, %s, %s, 'private')", (UID_D, AUTH_D, f"private_{UID_D[:8]}"))
        p_private_d = {"id": UID_D, "profile_visibility": "private"}
        
        send_follow_request(UID_A, UID_D)
        reqs_d = fast_query("SELECT id FROM chain_follow_requests WHERE requester_profile_id = %s AND target_profile_id = %s", (UID_A, UID_D))
        if reqs_d:
            decline_follow_request(reqs_d[0]["id"], UID_D)
            check("9. Declined request means still hidden", not can_view_posts(UID_A, p_private_d))
        else:
            check("9. Declined request means still hidden", False)
        
        # 10. Self check
        check("10. Self can always view", can_view_posts(UID_B, p_target))

    finally:
        # Cleanup
        write_query("DELETE FROM chain_follow_requests WHERE requester_profile_id IN (%s, %s, %s, %s) OR target_profile_id IN (%s, %s, %s, %s)", (UID_A, UID_B, UID_C, UID_D, UID_A, UID_B, UID_C, UID_D))
        write_query("DELETE FROM chain_follows WHERE follower_profile_id IN (%s, %s, %s, %s) OR following_profile_id IN (%s, %s, %s, %s)", (UID_A, UID_B, UID_C, UID_D, UID_A, UID_B, UID_C, UID_D))
        write_query("DELETE FROM chain_profiles WHERE id IN (%s, %s, %s, %s)", (UID_A, UID_B, UID_C, UID_D))

    print(f"\nPhase 80 Full Privacy: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
