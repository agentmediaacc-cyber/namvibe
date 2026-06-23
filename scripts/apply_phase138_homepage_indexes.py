#!/usr/bin/env python3
"""
Phase 138: Apply Homepage Performance Indexes
==============================================
Applies partial indexes to optimize homepage queries.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.neon_service import fast_query, log_error, log_info


INDEXES = [
    ("idx_chain_posts_homepage", """
        CREATE INDEX IF NOT EXISTS idx_chain_posts_homepage 
        ON chain_posts (created_at DESC) 
        WHERE deleted_at IS NULL
    """),
    ("idx_chain_reels_homepage", """
        CREATE INDEX IF NOT EXISTS idx_chain_reels_homepage 
        ON chain_reels (created_at DESC) 
        WHERE deleted_at IS NULL
    """),
    ("idx_chain_stories_homepage", """
        CREATE INDEX IF NOT EXISTS idx_chain_stories_homepage 
        ON chain_stories (created_at DESC) 
        WHERE deleted_at IS NULL AND active = TRUE
    """),
    ("idx_chain_status_posts_homepage", """
        CREATE INDEX IF NOT EXISTS idx_chain_status_posts_homepage 
        ON chain_status_posts (created_at DESC) 
        WHERE deleted_at IS NULL AND (expires_at IS NULL OR expires_at > NOW())
    """),
    ("idx_chain_live_rooms_homepage", """
        CREATE INDEX IF NOT EXISTS idx_chain_live_rooms_homepage 
        ON chain_live_rooms (created_at DESC) 
        WHERE deleted_at IS NULL AND is_live = TRUE
    """),
    ("idx_chain_profiles_homepage", """
        CREATE INDEX IF NOT EXISTS idx_chain_profiles_homepage 
        ON chain_profiles (created_at DESC) 
        WHERE deleted_at IS NULL AND is_creator = TRUE
    """),
    ("idx_chain_profiles_username", """
        CREATE INDEX IF NOT EXISTS idx_chain_profiles_username 
        ON chain_profiles (username) 
        WHERE deleted_at IS NULL
    """),
    ("idx_chain_profiles_id", """
        CREATE INDEX IF NOT EXISTS idx_chain_profiles_id 
        ON chain_profiles (id) 
        WHERE deleted_at IS NULL
    """),
]


def apply_indexes():
    """Apply all indexes."""
    print("=" * 60)
    print("Phase 138: Applying Homepage Performance Indexes")
    print("=" * 60)
    print()
    
    results = []
    for name, sql in INDEXES:
        print(f"Applying {name}...")
        try:
            # Use a simple query to create the index
            result = fast_query(sql, timeout_ms=30000)
            print(f"  ✓ {name} applied successfully")
            results.append({"name": name, "status": "success"})
        except Exception as e:
            print(f"  ✗ {name} failed: {e}")
            log_error("index_creation_failed", index=name, error=str(e))
            results.append({"name": name, "status": "failed", "error": str(e)})
    
    print()
    print("=" * 60)
    print("INDEX APPLICATION SUMMARY")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"Applied: {success_count}/{len(results)} indexes")
    
    if success_count == len(results):
        print("Status: ALL INDEXES APPLIED")
    else:
        print("Status: SOME INDEXES FAILED")
        for r in results:
            if r["status"] != "success":
                print(f"  - {r['name']}: {r.get('error', 'unknown error')}")
    
    return success_count == len(results)


if __name__ == "__main__":
    success = apply_indexes()
    sys.exit(0 if success else 1)