"""Phase 82: reconnect banner is dismissible and not permanently visible."""
import os
import sys

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
    print("Phase 82: Reconnect Banner Static")
    base = open("templates/base.html").read()
    sock = open("static/js/namvibe_socket_manager.js").read()
    presence = open("static/js/realtime_presence.js").read()

    check("banner has data attribute", "data-reconnect-banner" in base)
    check("banner has close button", "data-reconnect-close" in base)
    check("banner starts hidden", 'aria-hidden="true"' in base)
    check("socket waits for initial attempt", "initialAttemptComplete" in sock)
    check("socket checks polling fallback", "/system/socketio-status" in sock)
    check("socket supports dismissal", "closedByUser" in sock and "data-reconnect-close" in sock)
    check("base inline checks fallback status", "/system/socketio-status" in base)
    check("presence reuses shared socket", "window.chainSocket" in presence)

    print(f"\nPhase 82 Reconnect Banner: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
