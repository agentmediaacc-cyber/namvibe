"""Phase 157 Test D: Status expiry and cleanup."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.status_service import expire_old_statuses
from services.neon_service import write_query, fast_query
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from engines.cache_engine import delete_cache, cache_key

def get_test_profile():
    rows = fast_query("SELECT id FROM chain_profiles LIMIT 1", default=[])
    return str(rows[0]["id"]) if rows else None

def run():
    profile_id = get_test_profile()
    if not profile_id:
        print("SKIP: No profiles in DB")
        return

    status_id = str(uuid4())
    future = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    write_query(
        "INSERT INTO chain_status_posts (id, profile_id, caption, visibility, expires_at, created_at, duration_seconds) VALUES (%s, %s, %s, %s, %s, %s, 30)",
        (status_id, profile_id, "Expiry test", "public", future, past)
    )

    # Direct DB check: should be active (not expired yet)
    active = fast_query("SELECT id FROM chain_status_posts WHERE id = %s AND deleted_at IS NULL", (status_id,), default=[])
    assert active, "Status should be active before expiry"

    # Manually set expires_at to the past
    write_query("UPDATE chain_status_posts SET expires_at = %s WHERE id = %s", (past, status_id))

    # Run expiry
    expire_old_statuses()

    # Direct DB check: should be marked deleted
    deleted = fast_query("SELECT id FROM chain_status_posts WHERE id = %s AND deleted_at IS NOT NULL", (status_id,), default=[])
    assert deleted, "Status should be deleted after expiry"

    print("PASS: test_phase157_status_expiry_supabase_cleanup")

if __name__ == "__main__":
    run()
