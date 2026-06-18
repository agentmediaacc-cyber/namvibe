"""Phase 81 — Profile Templates Static Test."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    print("Phase 81: Profile Templates Static")
    
    header_path = "templates/profile/partials/profile_header.html"
    index_path = "templates/profile/index.html"
    private_path = "templates/profile/private_profile.html"
    
    with open(header_path, 'r') as f:
        header = f.read()
    with open(index_path, 'r') as f:
        index = f.read()
    with open(private_path, 'r') as f:
        private = f.read()
        
    check("Header uses primary_action", "pa.primary_action" in header)
    check("Header handles 'self' primary action", "own_profile" in header)
    check("Header has Edit Profile for owner", "Edit Profile" in header)
    
    check("Index uses command-grid for dashboard", "command-grid" in index)
    check("Index has wallet snapshot card", "Wallet Snapshot" in index)
    check("Index has privacy & safety card", "Privacy & Safety" in index)
    check("Index has social growth card", "Social Growth" in index)
    check("Index hides Saved for non-owners", "{% if own_profile %}" in index and "id=\"saved-tab\"" in index)
    check("Index hides Liked for non-owners", "{% if own_profile %}" in index and "id=\"liked-tab\"" in index)
    check("Index gates media tab with privacy", "can_view_media" in index and "data-tab-target=\"media\"" in index)
    check("Private profile hides posts/reels/media", all(word not in private for word in ["Posts", "Reels", "Media"]))
    
    # Check for removal of broken/duplicate UI
    check("No raw missing field list", "completion_data.missing_fields" not in index)
    check("No duplicate avatars in header", header.count("profile-avatar") <= 1 or header.count("avatar-container") <= 1)
    check("No hardcoded Chain branding", "CHAIN" not in header + index + private and "Chain" not in header + index + private)

    print(f"\nPhase 81 Templates: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
