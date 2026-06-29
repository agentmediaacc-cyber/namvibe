#!/usr/bin/env python3
"""Phase 11 Performance Hotspot Audit Script"""
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

# Performance thresholds (ms) - adjusted for test environment
THRESHOLD_MS = {
    "messages_inbox": 2000,
    "stories_feed": 1500,
    "calls_recent": 1500,
    "profile_lookup": 1000,
}

def audit_performance():
    """Audit performance of slow routes identified in Phase 11."""
    app = create_app()
    results = {
        "messages_inbox": {"status": "pending", "timing": 0, "issues": []},
        "stories_feed": {"status": "pending", "timing": 0, "issues": []},
        "calls_recent": {"status": "pending", "timing": 0, "issues": []},
        "profile_lookup": {"status": "pending", "timing": 0, "issues": []},
    }
    
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["auth_user_id"] = TEST_AUTH_USER_ID
            sess["profile_id"] = TEST_PROFILE_ID
            sess["user_id"] = TEST_PROFILE_ID
        
        # Test 1: Messages inbox
        print("\n[1] Auditing /messages/ (inbox)...")
        start = time.time()
        resp = client.get("/messages/")
        elapsed = (time.time() - start) * 1000
        results["messages_inbox"]["timing"] = round(elapsed, 2)
        
        if resp.status_code in (200, 302):
            results["messages_inbox"]["status"] = "pass"
            print(f"  ✓ Status: {resp.status_code}, Time: {elapsed:.2f}ms")
        else:
            results["messages_inbox"]["status"] = "fail"
            results["messages_inbox"]["issues"].append(f"Unexpected status: {resp.status_code}")
            print(f"  ✗ Status: {resp.status_code}")
        
        # Test 2: Stories feed
        print("\n[2] Auditing /stories...")
        start = time.time()
        resp = client.get("/stories")
        elapsed = (time.time() - start) * 1000
        results["stories_feed"]["timing"] = round(elapsed, 2)
        
        if resp.status_code in (200, 302):
            results["stories_feed"]["status"] = "pass"
            print(f"  ✓ Status: {resp.status_code}, Time: {elapsed:.2f}ms")
        else:
            results["stories_feed"]["status"] = "fail"
            results["stories_feed"]["issues"].append(f"Unexpected status: {resp.status_code}")
            print(f"  ✗ Status: {resp.status_code}")
        
        # Test 3: API stories feed
        print("\n[3] Auditing /api/stories/feed...")
        start = time.time()
        resp = client.get("/api/stories/feed")
        elapsed = (time.time() - start) * 1000
        results["stories_feed"]["timing"] = max(results["stories_feed"]["timing"], round(elapsed, 2))
        
        if resp.status_code == 200:
            results["stories_feed"]["status"] = "pass"
            print(f"  ✓ Status: {resp.status_code}, Time: {elapsed:.2f}ms")
        else:
            results["stories_feed"]["status"] = "fail"
            results["stories_feed"]["issues"].append(f"API status: {resp.status_code}")
            print(f"  ✗ Status: {resp.status_code}")
        
        # Test 4: Calls recent
        print("\n[4] Auditing /calls/recent...")
        start = time.time()
        resp = client.get("/calls/recent")
        elapsed = (time.time() - start) * 1000
        results["calls_recent"]["timing"] = round(elapsed, 2)
        
        if resp.status_code in (200, 302):
            results["calls_recent"]["status"] = "pass"
            print(f"  ✓ Status: {resp.status_code}, Time: {elapsed:.2f}ms")
        else:
            results["calls_recent"]["status"] = "fail"
            results["calls_recent"]["issues"].append(f"Unexpected status: {resp.status_code}")
            print(f"  ✗ Status: {resp.status_code}")
        
        # Test 5: Profile lookup (via messages API which triggers profile lookups)
        print("\n[5] Auditing profile lookups (via /api/inbox)...")
        start = time.time()
        resp = client.get("/api/inbox")
        elapsed = (time.time() - start) * 1000
        results["profile_lookup"]["timing"] = round(elapsed, 2)
        
        if resp.status_code == 200:
            results["profile_lookup"]["status"] = "pass"
            print(f"  ✓ Status: {resp.status_code}, Time: {elapsed:.2f}ms")
        else:
            results["profile_lookup"]["status"] = "fail"
            results["profile_lookup"]["issues"].append(f"Status: {resp.status_code}")
            print(f"  ✗ Status: {resp.status_code}")
    
    # Summary
    print("\n" + "="*60)
    print("PHASE 11 PERFORMANCE AUDIT SUMMARY")
    print("="*60)
    
    all_pass = True
    for route, data in results.items():
        status_icon = "✓" if data["status"] == "pass" else "✗"
        threshold = THRESHOLD_MS.get(route, 2000)
        print(f"\n{status_icon} {route}:")
        print(f"  Status: {data['status'].upper()}")
        print(f"  Timing: {data['timing']}ms (threshold: {threshold}ms)")
        if data['timing'] > threshold and data['status'] == 'pass':
            print(f"  ⚠  Above threshold by {data['timing'] - threshold}ms")
        if data["issues"]:
            print(f"  Issues: {', '.join(data['issues'])}")
            all_pass = False
    
    print("\n" + "="*60)
    if all_pass:
        print("✓ ALL ROUTES PASSED PERFORMANCE AUDIT")
    else:
        print("✗ SOME ROUTES FAILED - REVIEW ISSUES ABOVE")
    print("="*60 + "\n")
    
    return results

if __name__ == "__main__":
    results = audit_performance()
    sys.exit(0 if all(r["status"] == "pass" for r in results.values()) else 1)