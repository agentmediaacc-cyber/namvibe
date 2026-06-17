"""Phase 80 — Follow Request Service Test."""

import os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.follow_request_service import (
    is_private_follow_required, get_follow_status, send_follow_request,
    approve_follow_request, decline_follow_request
)

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
    print("Phase 80: Follow Request Service")
    
    UID_A = str(uuid.uuid4())
    UID_B = str(uuid.uuid4())
    
    # 1. is_private_follow_required
    check("public profile no request", is_private_follow_required(UID_A, {"id": UID_B, "profile_visibility": "public"}) == False)
    check("private profile requires request", is_private_follow_required(UID_A, {"id": UID_B, "profile_visibility": "private"}) == True)
    check("self no request", is_private_follow_required(UID_A, {"id": UID_A, "profile_visibility": "private"}) == False)
    
    # 2. get_follow_status (none)
    # This requires DB but we can check if it returns "none" for random IDs
    check("status none for random", get_follow_status(str(uuid.uuid4()), str(uuid.uuid4())) == "none")
    check("status self", get_follow_status(UID_A, UID_A) == "self")

    # 3. send_follow_request logic check
    # Cannot really test DB operations without real IDs or mocking neon_service.
    # We can at least check import and signature.
    check("send_follow_request exists", callable(send_follow_request))
    check("approve_follow_request exists", callable(approve_follow_request))
    check("decline_follow_request exists", callable(decline_follow_request))

    print(f"\nPhase 80 Service: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
