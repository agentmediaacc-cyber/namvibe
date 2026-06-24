"""Phase 157 Test A: Status visibility is followers-only by default."""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.status_service import create_status, can_view_status, delete_status
from services.neon_service import fast_query

def get_test_profile():
    rows = fast_query("SELECT id FROM chain_profiles LIMIT 1", default=[])
    return str(rows[0]["id"]) if rows else None

def run():
    owner_id = get_test_profile()
    if not owner_id:
        print("SKIP: No profiles in DB")
        return
    viewer_id = str(uuid.uuid4())

    status, err = create_status(owner_id, "Test followers-only", visibility="followers")
    assert err is None, f"Create failed: {err}"
    assert status["visibility"] == "followers"

    allowed, reason = can_view_status(status["id"], viewer_id)
    assert not allowed, "Non-follower should NOT view"
    assert reason == "followers_only", f"Expected followers_only, got {reason}"

    allowed, _ = can_view_status(status["id"], owner_id)
    assert allowed, "Owner should view"

    delete_status(status["id"], owner_id)
    print("PASS: test_phase157_status_followers_only")

if __name__ == "__main__":
    run()
