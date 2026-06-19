"""Verify phase86_relationship_indexes.py contains all required indexes."""

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

print("Phase 86: Indexes")

script_path = "scripts/phase86_relationship_indexes.py"
with open(script_path) as f:
    content = f.read()

check("idx_friends_pair_fast exists", "idx_friends_pair_fast" in content)
check("idx_friend_requests_pair_status_fast exists", "idx_friend_requests_pair_status_fast" in content)
check("idx_follows_pair_fast exists", "idx_follows_pair_fast" in content)
check("idx_follow_requests_pair_status_fast exists", "idx_follow_requests_pair_status_fast" in content)
check("idx_notifications_unread_fast exists", "idx_notifications_unread_fast" in content)
check("5 indexes defined", content.count("CREATE INDEX IF NOT EXISTS") == 5)

print(f"\nPhase 86 Indexes: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
