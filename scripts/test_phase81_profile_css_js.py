"""Phase 81 — Profile CSS & JS Test."""

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
    print("Phase 81: Profile CSS & JS")
    
    css_path = "static/css/profile_command_center.css"
    js_path = "static/js/profile_command_center.js"
    base_path = "templates/profile/base_profile.html"
    
    check("CSS exists", os.path.exists(css_path))
    check("JS exists", os.path.exists(js_path))
    
    with open(css_path, 'r') as f:
        css = f.read()
    with open(js_path, 'r') as f:
        js = f.read()
    with open(base_path, 'r') as f:
        base = f.read()
        
    check("Base profile includes CSS", "profile_command_center.css" in base)
    check("Base profile includes JS", "profile_command_center.js" in base)
    
    check("CSS has dashboard grid", ".command-grid" in css)
    check("CSS has completion bar", ".progress-bar" in css)
    
    check("JS has tab switching", "initTabSwitching" in js)
    check("JS has copy URL", "initCopyProfileUrl" in js)
    check("JS has share fallback", "initShareProfile" in js)
    check("JS has QR fallback", "initQrFallback" in js)
    check("JS has toast", "showToast" in js and "profile-toast" in js)
    check("JS has social actions", "initSocialActions" in js)
    check("JS has action updates", "Request Sent" in js and "Following" in js)

    print(f"\nPhase 81 CSS/JS: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
