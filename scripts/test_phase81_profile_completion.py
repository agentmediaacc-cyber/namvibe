"""Phase 81 — Profile Completion Service Test."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.profile_completion_service import calculate_profile_completion

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
    print("Phase 81: Profile Completion Service")
    
    # 1. Empty profile
    res1 = calculate_profile_completion({})
    check("Empty profile percent is 0", res1["percent"] == 0)
    check("Empty profile has missing tasks", len(res1["missing"]) > 0)
    check("Next best action is avatar_url", res1["next_best_action"]["key"] == "avatar_url")
    
    # 2. Partially filled profile
    profile2 = {
        "avatar_url": "http://example.com/a.jpg",
        "bio": "Hello",
        "email_verified": True
    }
    res2 = calculate_profile_completion(profile2)
    check("Partially filled profile percent > 0", res2["percent"] > 0)
    check("Partially filled profile percent < 100", res2["percent"] < 100)
    check("Missing tasks does not include bio", not any(m["key"] == "bio" for m in res2["missing"]))
    check("Missing tasks includes cover_url", any(m["key"] == "cover_url" for m in res2["missing"]))

    # 3. Custom field mapping check
    profile3 = {"town": "Windhoek"} # Should count as location
    res3 = calculate_profile_completion(profile3)
    check("Town counts as location", not any(m["key"] == "location" for m in res3["missing"]))

    with open("templates/profile/index.html", "r") as f:
        index = f.read()
    check("UI limits top missing tasks", "completion_data.missing[:3]" in index)
    check("UI uses Improve profile CTA", "Improve profile" in index)

    print(f"\nPhase 81 Completion: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
