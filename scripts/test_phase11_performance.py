#!/usr/bin/env python3
"""Phase 11 Performance Hotfix Test Script"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("FLASK_ENV", "development")

from app import create_app
import time

TEST_AUTH_USER_ID = "11111111-1111-4111-8111-111111111111"
TEST_PROFILE_ID = "22222222-2222-4222-8222-222222222222"

def test_performance():
    """Test that performance optimizations are in place."""
    app = create_app()
    failures = []
    passes = 0
    total = 0
    
    print("=" * 60)
    print("PHASE 11 PERFORMANCE HOTFIX TESTS")
    print("=" * 60)
    
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["auth_user_id"] = TEST_AUTH_USER_ID
            sess["profile_id"] = TEST_PROFILE_ID
            sess["user_id"] = TEST_PROFILE_ID
        
        # Test 1: Messages inbox loads
        total += 1
        print(f"\n[Test {total}] /messages/ loads...")
        start = time.time()
        resp = client.get("/messages/")
        elapsed = (time.time() - start) * 1000
        if resp.status_code in (200, 302):
            passes += 1
            print(f"  ✓ Status {resp.status_code} in {elapsed:.1f}ms")
        else:
            failures.append(f"/messages/ returned {resp.status_code}")
            print(f"  ✗ Status {resp.status_code}")
        
        # Test 2: Stories page loads
        total += 1
        print(f"\n[Test {total}] /stories loads...")
        start = time.time()
        resp = client.get("/stories")
        elapsed = (time.time() - start) * 1000
        if resp.status_code in (200, 302):
            passes += 1
            print(f"  ✓ Status {resp.status_code} in {elapsed:.1f}ms")
        else:
            failures.append(f"/stories returned {resp.status_code}")
            print(f"  ✗ Status {resp.status_code}")
        
        # Test 3: API stories feed
        total += 1
        print(f"\n[Test {total}] /api/stories/feed loads...")
        start = time.time()
        resp = client.get("/api/stories/feed")
        elapsed = (time.time() - start) * 1000
        if resp.status_code == 200:
            passes += 1
            print(f"  ✓ Status {resp.status_code} in {elapsed:.1f}ms")
        else:
            failures.append(f"/api/stories/feed returned {resp.status_code}")
            print(f"  ✗ Status {resp.status_code}")
        
        # Test 4: Calls recent page
        total += 1
        print(f"\n[Test {total}] /calls/recent loads...")
        start = time.time()
        resp = client.get("/calls/recent")
        elapsed = (time.time() - start) * 1000
        if resp.status_code in (200, 302):
            passes += 1
            print(f"  ✓ Status {resp.status_code} in {elapsed:.1f}ms")
        else:
            failures.append(f"/calls/recent returned {resp.status_code}")
            print(f"  ✗ Status {resp.status_code}")
        
        # Test 5: Profile lookup via get_current_profile
        total += 1
        print(f"\n[Test {total}] Profile lookup via /api/inbox...")
        start = time.time()
        resp = client.get("/api/inbox")
        elapsed = (time.time() - start) * 1000
        if resp.status_code == 200:
            passes += 1
            print(f"  ✓ Status {resp.status_code} in {elapsed:.1f}ms")
        else:
            failures.append(f"/api/inbox returned {resp.status_code}")
            print(f"  ✗ Status {resp.status_code}")
        
        # Test 6: Verify lightweight profile columns exist
        total += 1
        print(f"\n[Test {total}] Lightweight profile columns defined...")
        from services.profile_service import _LIGHTWEIGHT_FULL_COLUMNS, _LIGHTWEIGHT_PROFILE_COLUMNS
        if _LIGHTWEIGHT_FULL_COLUMNS and _LIGHTWEIGHT_PROFILE_COLUMNS:
            passes += 1
            print(f"  ✓ Lightweight columns defined")
        else:
            failures.append("Lightweight profile columns missing")
            print(f"  ✗ Lightweight columns missing")
        
        # Test 7: Verify _neon_get_profile_by supports use_lightweight
        total += 1
        print(f"\n[Test {total}] _neon_get_profile_by supports use_lightweight...")
        import inspect
        sig = inspect.signature(importlib.import_module('services.profile_service')._neon_get_profile_by)
        if 'use_lightweight' in sig.parameters:
            passes += 1
            print(f"  ✓ use_lightweight parameter present")
        else:
            failures.append("use_lightweight parameter missing from _neon_get_profile_by")
            print(f"  ✗ use_lightweight parameter missing")
        
        # Test 8: Verify migration file has all required indexes
        total += 1
        print(f"\n[Test {total}] Migration file has required indexes...")
        with open(ROOT / "migrations" / "004_performance_hotfix_indexes.sql") as f:
            content = f.read()
        required_indexes = [
            "idx_thread_members_profile_pinned",
            "idx_message_threads_updated",
            "idx_messages_unread_optimized",
            "idx_status_posts_feed",
            "idx_status_posts_visibility_feed",
            "idx_story_views_story",
            "idx_call_sessions_caller_covering",
            "idx_call_sessions_receiver_covering",
            "idx_profiles_lookup_covering",
            "idx_profiles_lightweight_full",
            "idx_message_deletions_message_profile",
        ]
        missing = [idx for idx in required_indexes if idx not in content]
        if not missing:
            passes += 1
            print(f"  ✓ All {len(required_indexes)} required indexes present")
        else:
            failures.append(f"Missing indexes: {missing}")
            print(f"  ✗ Missing indexes: {missing}")
        
        # Test 9: Verify call_service uses UNION instead of OR
        total += 1
        print(f"\n[Test {total}] Call service uses UNION optimization...")
        with open(ROOT / "services" / "call_service.py") as f:
            content = f.read()
        if "UNION" in content and "list_recent_calls" in content:
            passes += 1
            print(f"  ✓ UNION optimization present in list_recent_calls")
        else:
            failures.append("UNION optimization missing from call_service")
            print(f"  ✗ UNION optimization missing")
        
        # Test 10: Verify status_service uses CTE optimization
        total += 1
        print(f"\n[Test {total}] Status service uses CTE optimization...")
        with open(ROOT / "services" / "status_service.py") as f:
            content = f.read()
        if "follow_map" in content and "list_active_statuses" in content:
            passes += 1
            print(f"  ✓ CTE optimization present in list_active_statuses")
        else:
            failures.append("CTE optimization missing from status_service")
            print(f"  ✗ CTE optimization missing")
    
    # Summary
    print("\n" + "=" * 60)
    print(f"RESULTS: {passes}/{total} tests passed")
    print("=" * 60)
    
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  ✗ {f}")
        print()
        return False
    
    print("\n✓ ALL TESTS PASSED\n")
    return True

if __name__ == "__main__":
    import importlib
    success = test_performance()
    sys.exit(0 if success else 1)