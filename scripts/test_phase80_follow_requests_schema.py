"""Phase 80 — Follow Requests Schema Test."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_service import fast_query

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
    global FAIL
    print("Phase 80: Follow Requests Schema")
    
    # Columns
    cols = fast_query("SELECT column_name FROM information_schema.columns WHERE table_name = 'chain_follow_requests'", timeout_ms=15000)
    if not cols:
        print("  FAIL table chain_follow_requests columns not found (or table missing)")
        FAIL += 1
        return False
        
    col_names = [c["column_name"] for c in cols]
    for c in ["id", "requester_profile_id", "target_profile_id", "status", "message", "created_at", "responded_at", "updated_at"]:
        check(f"column {c} exists", c in col_names)
        
    # Indexes
    idxs = fast_query("SELECT indexname FROM pg_indexes WHERE tablename = 'chain_follow_requests'")
    idx_names = [i["indexname"] for i in idxs]
    check("index idx_follow_requests_target_status_created exists", "idx_follow_requests_target_status_created" in idx_names)
    check("index idx_follow_requests_requester_status_created exists", "idx_follow_requests_requester_status_created" in idx_names)
    
    print(f"\nPhase 80 Schema: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
