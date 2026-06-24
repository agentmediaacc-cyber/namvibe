"""Phase 157 Test B: Status video duration validation.
Verifies:
1. validate_status_duration() rejects >120 seconds
2. Status with valid duration passes
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.status_service import validate_status_duration, MAX_STATUS_DURATION_SECONDS

def run():
    ok, err = validate_status_duration(30)
    assert ok, f"Expected ok for 30s, got {err}"
    
    ok, err = validate_status_duration(120)
    assert ok, f"Expected ok for 120s, got {err}"
    
    ok, err = validate_status_duration(121)
    assert not ok, "Should reject 121s"
    assert "120" in (err or ""), f"Expected error mentioning 120, got {err}"
    
    ok, err = validate_status_duration(999)
    assert not ok, "Should reject 999s"
    
    assert MAX_STATUS_DURATION_SECONDS == 120, f"Expected 120, got {MAX_STATUS_DURATION_SECONDS}"
    
    print("PASS: test_phase157_status_video_duration")

if __name__ == "__main__":
    run()
