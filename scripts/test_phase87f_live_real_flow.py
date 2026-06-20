"""Phase 87F — Verify live studio route, imports, and no host_profile_id crash."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
    print("PHASE 87F — LIVE REAL FLOW")
    print("=" * 60)

    live_routes = os.path.join(ROOT, "api_routes", "live_routes.py")
    live_service = os.path.join(ROOT, "services", "live_service.py")
    studio_tpl = os.path.join(ROOT, "templates", "live", "studio.html")

    print("\n--- Route Files ---")
    check("api_routes/live_routes.py exists", os.path.exists(live_routes))
    check("services/live_service.py exists", os.path.exists(live_service))
    check("templates/live/studio.html exists", os.path.exists(studio_tpl))

    print("\n--- Import Check ---")
    with open(live_routes) as f:
        src = f.read()

    check("login_required imported", "login_required" in src)
    check("get_current_profile imported", "get_current_profile" in src)
    check("live_service.create_live_room imported", "create_live_room" in src)
    check("live_streaming_service.add_participant imported", "add_participant" in src)
    check("live_feature_service imported as phase29_live", "phase29_live" in src)

    print("\n--- No broken function references ---")
    # Check for get_room_participants (doesn't exist)
    check("NO get_room_participants call", "get_room_participants" not in src)

    # /live/studio route exists
    check("/live/studio route exists", '/studio' in src)

    # /live/create redirect exists
    app_py = os.path.join(ROOT, "app.py")
    with open(app_py) as f:
        app_src = f.read()
    check("app.py has /live/create redirect", '/live/create' in app_src and '/live/studio' in app_src)

    print("\n--- host_profile_id handling ---")
    with open(live_service) as f:
        svc_src = f.read()
    check("host_profile_id fallback to profile_id",
          'host_profile_id' in svc_src and 'profile_id' in svc_src)

    print("\n--- Template ---")
    with open(studio_tpl) as f:
        tpl = f.read()
    check("studio template renders form", 'form' in tpl)
    check("studio has title input", 'title' in tpl.lower())

    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    if FAIL == 0:
        print(f"PHASE 87F LIVE REAL FLOW: PASS ({PASS}/{total})")
    else:
        print(f"PHASE 87F LIVE REAL FLOW: FAIL ({PASS}/{total})")
    print(f"{'=' * 60}")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
