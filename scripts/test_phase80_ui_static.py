"""Phase 80 — Follow Request UI Static Test."""

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
    print("Phase 80: Follow Request UI Static")
    
    def safe_read(path):
        if not os.path.exists(path): return ""
        with open(path, "r") as f: return f.read()

    # Templates
    discover = safe_read("templates/discover/index.html")
    header = safe_read("templates/profile/partials/profile_header.html")
    messages = safe_read("templates/messages/index.html")
    
    check("discover has Request Follow", "Request Follow" in discover)
    check("discover has Requested", "Requested" in discover)
    check("discover has follow_request_controls.js", "follow_request_controls.js" in discover)
    
    check("header has Request Follow", "Request Follow" in header)
    check("header has Requested", "Requested" in header)
    
    check("messages has Follow Requests section", "Follow Requests" in messages)
    check("messages has followRequestsList", "followRequestsList" in messages)

    # JS
    fr_js = safe_read("static/js/follow_request_controls.js")
    msg_req_js = safe_read("static/js/message_requests.js")
    notif_js = safe_read("static/js/namvibe_notifications.js")
    
    check("follow_request_controls.js handles request_pending", "request_pending" in fr_js)
    check("follow_request_controls.js handles approve", "approve" in fr_js)
    
    check("message_requests.js handles follow requests", "follow_requests" in msg_req_js)
    check("message_requests.js handles approveFollowRequest", "approveFollowRequest" in msg_req_js)
    
    check("namvibe_notifications.js handles follow_request", "follow_request" in notif_js)
    check("namvibe_notifications.js handles follow_request_approved", "follow_request_approved" in notif_js)

    print(f"\nPhase 80 UI: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
