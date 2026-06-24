"""Phase 157 Test F: Public feed ranking engine.
Verifies:
1. rank_feed() returns scored items sorted by score
2. Empty input returns empty list
3. rank_feed() does not crash on missing fields
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.feed_ranking_service import rank_feed

def run():
    # Empty
    result = rank_feed([])
    assert result == [], f"Empty input should return empty list, got {result}"
    
    # Single item
    items = [{"id": "1", "profile_id": "p1", "created_at": "2026-06-23T12:00:00Z", "likes_count": 10, "comments_count": 5}]
    result = rank_feed(items)
    assert len(result) == 1, f"Should have 1 item, got {len(result)}"
    
    # Multiple items, sorted by score
    old = {"id": "1", "profile_id": "p1", "created_at": "2026-06-20T12:00:00Z", "likes_count": 0, "comments_count": 0}
    new = {"id": "2", "profile_id": "p2", "created_at": "2026-06-23T12:00:00Z", "likes_count": 100, "comments_count": 50}
    items = [old, new]
    result = rank_feed(items)
    assert result[0]["id"] == "2", f"Expected newer/higher-engagement item first, got id={result[0]['id']}"
    
    # Items with missing fields should not crash
    bad = [{"id": "3"}, {"id": "4", "created_at": "invalid-date"}]
    result = rank_feed(bad)
    assert len(result) == 2, f"Should handle bad items gracefully, got {len(result)}"
    
    # With viewer
    result = rank_feed(items, viewer_id="viewer1")
    assert len(result) == 2, f"Should work with viewer, got {len(result)}"
    
    print("PASS: test_phase157_public_feed_ranking")

if __name__ == "__main__":
    run()
