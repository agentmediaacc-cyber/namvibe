"""Phase 80 — Private Follow Requests Schema.

Adds the chain_follow_requests table and supporting indexes.
Run: python3 scripts/phase80_follow_requests_schema.py
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_service import write_query, fast_query

MIGRATION_NAME = "phase80_follow_requests"

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chain_follow_requests (
    id UUID PRIMARY KEY,
    requester_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    target_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, declined, cancelled
    message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    responded_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(requester_profile_id, target_profile_id)
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_follow_requests_target_status_created ON chain_follow_requests(target_profile_id, status, created_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_follow_requests_requester_status_created ON chain_follow_requests(requester_profile_id, status, created_at DESC);"
]

def run():
    print(f"[{MIGRATION_NAME}] Starting schema migration...")
    try:
        # Create table
        write_query(TABLE_SQL)
        print("  OK  table: chain_follow_requests")
        
        # Create indexes
        for idx in INDEXES:
            write_query(idx)
            print(f"  OK  index: {idx.split(' ')[5]}")
            
        print(f"[{MIGRATION_NAME}] Done.")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
