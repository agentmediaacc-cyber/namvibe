"""
Phase: Friendship System
Safely creates/upgrades chain_friend_requests table and indexes.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.neon_service import write_query, fast_query


CREATE_FRIEND_REQUESTS = """
CREATE TABLE IF NOT EXISTS chain_friend_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    recipient_profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled')),
    message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    responded_at TIMESTAMPTZ,
    UNIQUE(sender_profile_id, recipient_profile_id)
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_friend_requests_sender ON chain_friend_requests(sender_profile_id);",
    "CREATE INDEX IF NOT EXISTS idx_friend_requests_receiver ON chain_friend_requests(recipient_profile_id);",
    "CREATE INDEX IF NOT EXISTS idx_friend_requests_status ON chain_friend_requests(status);",
]


def run():
    print("=== Phase: Friendship System Migration ===")

    print("[1/2] Creating chain_friend_requests table...")
    write_query(CREATE_FRIEND_REQUESTS)
    print("  OK - chain_friend_requests ready")

    print("[2/2] Adding indexes...")
    for idx in INDEXES:
        write_query(idx)
        print(f"  OK - index created")

    print("=== Phase Friendship System Complete ===")


if __name__ == "__main__":
    run()
