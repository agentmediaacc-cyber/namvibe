"""Phase 87 — Messages/Calls Static Test."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0

def check(name, ok):
    global PASS, FAIL
    if ok:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1

def run():
    global PASS, FAIL
    print("Phase 87: Messages/Calls Static")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Check message routes exist
    try:
        __import__("api_routes.message_routes")
        check("message_routes module loads", True)
    except Exception as e:
        check(f"message_routes module ({e})", False)

    try:
        __import__("api_routes.call_routes")
        check("call_routes module loads", True)
    except Exception as e:
        check(f"call_routes module ({e})", False)

    # Check key JS files
    js_files = [
        "static/js/webrtc_calls.js",
        "static/js/calls.js",
        "static/js/group_calls.js",
        "static/js/message_composer.js",
        "static/js/message_requests.js",
    ]
    for jf in js_files:
        path = os.path.join(root, jf)
        check(f"{jf} exists", os.path.isfile(path))

    # Check call templates exist
    calls_dir = os.path.join(root, "templates", "calls")
    for t in ["video.html", "group_call.html", "recent.html"]:
        path = os.path.join(calls_dir, t)
        check(f"calls/{t} exists", os.path.isfile(path))

    print(f"\nPhase 87 Messages/Calls: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
