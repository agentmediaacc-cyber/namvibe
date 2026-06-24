"""Phase 157 Test E: Locked/subscriber-only visibility."""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.status_service import create_status, can_view_status, delete_status
from services.neon_service import fast_query, write_query

def get_test_profiles(count=3):
    rows = fast_query(f"SELECT id FROM chain_profiles LIMIT {count}", default=[])
    return [str(r["id"]) for r in rows]

def run():
    profiles = get_test_profiles(3)
    if len(profiles) < 3:
        print("SKIP: Need at least 3 profiles in DB")
        return
    creator_id, subscriber_id, non_subscriber = profiles[0], profiles[1], profiles[2]

    # Create a subscription
    try:
        write_query(
            "INSERT INTO chain_creator_subscriptions (creator_profile_id, subscriber_profile_id, status, created_at) VALUES (%s, %s, 'active', now())",
            (creator_id, subscriber_id)
        )
    except Exception:
        pass  # might fail if FK on subscriber_id fails

    status, err = create_status(creator_id, "Subscriber-only", visibility="subscribers", duration_seconds=30)
    assert err is None, f"Create failed: {err}"
    sid = status["id"]

    allowed, reason = can_view_status(sid, non_subscriber)
    assert not allowed, "Non-subscriber should NOT view"
    assert reason == "subscriber_only", f"Expected subscriber_only, got {reason}"

    allowed, _ = can_view_status(sid, subscriber_id)
    assert allowed, "Subscriber should view"

    # Update to locked
    try:
        write_query("UPDATE chain_status_posts SET visibility = 'locked' WHERE id = %s", (sid,))
    except Exception:
        pass

    allowed, _ = can_view_status(sid, subscriber_id)
    assert allowed, "Subscriber should view locked"

    delete_status(sid, creator_id)
    print("PASS: test_phase157_locked_subscriber_visibility")

if __name__ == "__main__":
    run()
