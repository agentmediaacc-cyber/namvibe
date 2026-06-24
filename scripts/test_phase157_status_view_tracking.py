"""Phase 157 Test C: Status view tracking."""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.status_service import create_status, record_view, list_viewers, get_status, delete_status
from services.neon_service import fast_query

def get_test_profiles(count=2):
    rows = fast_query(f"SELECT id FROM chain_profiles LIMIT {count}", default=[])
    return [str(r["id"]) for r in rows]

def run():
    profiles = get_test_profiles(2)
    if len(profiles) < 2:
        print("SKIP: Need at least 2 profiles in DB")
        return
    owner_id, viewer_id = profiles[0], profiles[1]

    status, err = create_status(owner_id, "View tracking test", visibility="followers", duration_seconds=30)
    assert err is None, f"Create failed: {err}"
    sid = status["id"]

    ok = record_view(sid, viewer_id)
    assert ok, "record_view should succeed"

    rows = fast_query(
        "SELECT * FROM chain_status_views WHERE status_id = %s AND viewer_profile_id = %s",
        (sid, viewer_id), default=[]
    )
    assert rows, f"Expected view row in chain_status_views"

    viewers = list_viewers(sid, owner_id)
    vids = [v["viewer_id"] for v in viewers]
    assert viewer_id in vids, f"Expected {viewer_id} in {vids}"

    viewers_not_owner = list_viewers(sid, viewer_id)
    assert viewers_not_owner == [], "Non-owner should get empty list"

    sr = get_status(sid)
    assert int(sr.get("views_count", 0)) >= 1, f"views_count should be >= 1"

    ok = record_view(sid, viewer_id)
    assert ok, "Duplicate view should succeed"

    delete_status(sid, owner_id)
    print("PASS: test_phase157_status_view_tracking")

if __name__ == "__main__":
    run()
