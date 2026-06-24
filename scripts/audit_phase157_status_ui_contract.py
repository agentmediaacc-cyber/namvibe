"""Phase 157 Audit J: Status UI contract verification."""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.status_service import create_status, record_view, list_viewers, can_view_status, delete_status
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

    status, err = create_status(
        owner_id, caption="UI Contract Test", visibility="followers",
        media_type="text", duration_seconds=30, background_color="#000000",
        text_content="Hello from test"
    )
    assert err is None, f"Create failed: {err}"
    sid = status["id"]

    assert status.get("duration_seconds") == 30
    assert status.get("background_color") == "#000000"
    assert status.get("text_content") == "Hello from test"
    assert status.get("views_count") == 0
    assert status.get("visibility") == "followers"

    allowed, reason = can_view_status(sid, owner_id)
    assert allowed
    assert reason is None

    allowed, reason = can_view_status(sid, viewer_id)
    assert not allowed
    assert reason == "followers_only"

    ok = record_view(sid, viewer_id)
    assert ok

    viewers = list_viewers(sid, owner_id)
    assert len(viewers) >= 1
    v = viewers[0]
    assert "viewer_id" in v
    assert "username" in v
    assert "avatar_url" in v
    assert "viewed_at" in v

    delete_status(sid, owner_id)
    print("PASS: audit_phase157_status_ui_contract")

if __name__ == "__main__":
    run()
