"""Phase 81 — Profile Self Actions Test."""

import os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.social_action_policy import get_action_policy

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
    print("Phase 81: Profile Self Actions")
    
    UID = str(uuid.uuid4())
    profile = {"id": UID, "username": "tester"}
    
    policy = get_action_policy(UID, profile)
    
    check("is_self is True", policy["is_self"] is True)
    check("primary_action is self", policy["primary_action"] == "self")
    check("can_chat is False", policy["can_chat"] is False)
    check("can_call is False", policy.get("can_call") is False)
    check("can_message_self is False", policy.get("can_message_self") is False)
    check("can_call_self is False", policy.get("can_call_self") is False)
    check("can_like is False", policy.get("can_like") is False)
    
    # Check that it doesn't accidentally allow calling self
    from services.social_action_policy import can_chat
    check("can_chat helper returns False for self", can_chat(UID, UID) is False)

    with open("templates/profile/partials/profile_header.html", "r") as f:
        header = f.read()
    marker = '<div class="hero-actions">'
    action_area = header[header.find(marker):]
    owner_start = action_area.find("{% if own_profile %}")
    owner_end = action_area.find("{% else %}", owner_start)
    owner_block = action_area[owner_start:owner_end]
    check("Owner header renders Edit Profile", "Edit Profile" in owner_block)
    check("Owner header renders Create/Wallet/Privacy", all(text in owner_block for text in ["Create", "Wallet", "Privacy"]))
    check("Owner header does not render Message", "Message" not in owner_block)
    check("Owner header does not render Audio", "Audio" not in owner_block)
    check("Owner header does not render Video", "Video" not in owner_block)

    print(f"\nPhase 81 Self Actions: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
