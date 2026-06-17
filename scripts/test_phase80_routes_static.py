"""Phase 80 — Follow Request Routes Static Test."""

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
    print("Phase 80: Follow Request Routes Static")
    
    from app import app
    routes = [str(r) for r in app.url_map.iter_rules()]
    
    check("POST /api/follow/request/<profile_id> exists", any("/api/follow/request/" in r for r in routes))
    check("POST /api/follow/approve/<request_id> exists", any("/api/follow/approve/" in r for r in routes))
    check("POST /api/follow/decline/<request_id> exists", any("/api/follow/decline/" in r for r in routes))
    check("POST /api/follow/cancel/<request_id> exists", any("/api/follow/cancel/" in r for r in routes))
    check("GET /api/follow/status/<profile_id> exists", any("/api/follow/status/" in r for r in routes))
    check("GET /api/follow/requests/incoming exists", "/api/follow/requests/incoming" in routes)
    check("GET /api/follow/requests/outgoing exists", "/api/follow/requests/outgoing" in routes)
    
    check("GET /messages/api/requests exists", "/messages/api/requests" in routes)

    print(f"\nPhase 80 Routes: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
