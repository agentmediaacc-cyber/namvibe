"""Phase 87E — Verify notification polling is deduplicated."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name} {detail}")
        FAIL += 1

def run():
    global PASS, FAIL
    print("=" * 60)
    print("PHASE 87E — NOTIFICATION POLL DEDUPE")
    print("=" * 60)

    # 1. namvibe_global_badges.js — no independent setInterval
    with open("static/js/namvibe_global_badges.js", "r") as f:
        badges = f.read()
    
    check("no standalone setInterval in badges", "setInterval" not in badges)
    check("badges listens for custom notif:badge-update event", "notif:badge-update" in badges)
    check("badges responds to socket events", "socket.on" in badges)
    check("badges responds to visibilitychange", "visibilitychange" in badges)

    # 2. main.js dispatches custom event
    with open("static/js/main.js", "r") as f:
        main = f.read()
    
    check("main.js dispatches notif:badge-update event", "notif:badge-update" in main)
    check("main.js interval is at least 60s", "60000" in main)
    check("main.js prevents duplicate polls", "shouldPollNotifications" in main or "notificationRequestActive" in main)
    check("main.js dedupes by timestamp", "lastNotificationRequestAt" in main)

    # 3. sw.js does not poll unread-count
    sw_path = "static/js/sw.js"
    if os.path.exists(sw_path):
        with open(sw_path) as f:
            sw = f.read()
        check("sw.js has no unread-count polling", "unread-count" not in sw)
    else:
        check("sw.js exists", False)

    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    if FAIL == 0:
        print(f"PHASE 87E: PASS ({PASS}/{total})")
    else:
        print(f"PHASE 87E: FAIL ({PASS}/{total})")
    print(f"{'=' * 60}")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
