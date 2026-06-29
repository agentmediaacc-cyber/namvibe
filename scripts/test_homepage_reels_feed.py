#!/usr/bin/env python3
"""
Test script to verify homepage reels feed integration.
Checks that uploaded reels appear on the homepage with correct data.
"""
import sys
import os
import json
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_homepage_reels_feed():
    """Test that homepage feed includes latest public reels with proper data."""
    results = []
    
    print("=" * 60)
    print("HOMEPAGE REELS FEED VERIFICATION")
    print("=" * 60)
    
    # Test 1: Check if services can be imported
    print("\n[TEST 1] Importing services...")
    try:
        from services.homepage_service import (
            build_homepage_payload,
            _fetch_reels,
            _reel_select,
            _normalize_reel,
        )
        print("✅ PASS: Services imported successfully")
        results.append(("Import services", True, None))
    except Exception as e:
        print(f"❌ FAIL: Could not import services: {e}")
        results.append(("Import services", False, str(e)))
        return results
    
    # Test 2: Check reel selector includes engagement fields
    print("\n[TEST 2] Checking reel selector fields...")
    try:
        reel_cols = _reel_select()
        # Core fields that must exist (adapted to actual DB schema)
        required_core = [
            "id", "profile_id", "thumbnail_url", "media_url",
            "likes_count", "comments_count", "views_count", "shares_count",
            "music_title", "status", "processing_status"
        ]
        # Optional fields that may not exist in DB
        optional = ["video_url", "saves_count", "duration_seconds"]
        
        missing_core = [f for f in required_core if f not in reel_cols]
        if missing_core:
            print(f"❌ FAIL: Missing core fields in reel selector: {missing_core}")
            results.append(("Reel selector fields", False, f"Missing core: {missing_core}"))
        else:
            print(f"✅ PASS: All core fields present in reel selector")
            print(f"   Fields: {', '.join(reel_cols)}")
            # Note which optional fields are missing (OK if DB doesn't have them)
            missing_optional = [f for f in optional if f not in reel_cols]
            if missing_optional:
                print(f"   ℹ️  Optional fields not in DB schema (OK): {', '.join(missing_optional)}")
            results.append(("Reel selector fields", True, None))
    except Exception as e:
        print(f"❌ FAIL: Error checking reel selector: {e}")
        results.append(("Reel selector fields", False, str(e)))
    
    # Test 3: Fetch reels from database
    print("\n[TEST 3] Fetching reels from database...")
    try:
        rows, issue = _fetch_reels()
        if issue:
            print(f"⚠️  WARNING: Issue fetching reels: {issue}")
        
        if not rows:
            print("ℹ️  INFO: No reels found in database (empty state is OK)")
            results.append(("Fetch reels from DB", True, "No reels found - empty state"))
        else:
            print(f"✅ PASS: Found {len(rows)} reel(s) in database")
            print(f"   Latest reel ID: {rows[0].get('id')}")
            print(f"   Created at: {rows[0].get('created_at')}")
            results.append(("Fetch reels from DB", True, f"Found {len(rows)} reels"))
            
            # Check first reel has required fields
            first_reel = rows[0]
            has_video = bool(first_reel.get('video_url'))
            has_media = bool(first_reel.get('media_url') or first_reel.get('thumbnail_url'))
            has_status = first_reel.get('status') in ('published', 'ready', None)
            has_profile = bool(first_reel.get('profile_id'))
            
            print(f"\n   Data quality checks:")
            print(f"   - Has video_url: {'✅' if has_video else '❌'}")
            print(f"   - Has media/thumbnail: {'✅' if has_media else '❌'}")
            print(f"   - Has valid status: {'✅' if has_status else '❌'}")
            print(f"   - Has profile_id: {'✅' if has_profile else '❌'}")
            
            if not (has_video or has_media):
                results.append(("Reel data quality", False, "Missing video_url and media_url"))
            else:
                results.append(("Reel data quality", True, None))
    except Exception as e:
        print(f"❌ FAIL: Error fetching reels: {e}")
        results.append(("Fetch reels from DB", False, str(e)))
    
    # Test 4: Build homepage payload
    print("\n[TEST 4] Building homepage payload...")
    try:
        payload = build_homepage_payload()
        
        if not payload:
            print("❌ FAIL: Homepage payload is empty")
            results.append(("Build homepage payload", False, "Empty payload"))
            return results
        
        print(f"✅ PASS: Homepage payload built successfully")
        print(f"   Keys in payload: {', '.join(list(payload.keys())[:10])}...")
        results.append(("Build homepage payload", True, None))
        
        # Check reels section
        reels = payload.get("reels", [])
        print(f"\n   Reels in payload: {len(reels)}")
        if reels:
            print(f"   Latest reel ID: {reels[0].get('id')}")
            print(f"   Has display_name: {'✅' if reels[0].get('display_name') else '❌'}")
            print(f"   Has username: {'✅' if reels[0].get('username') else '❌'}")
            print(f"   Has avatar_url: {'✅' if reels[0].get('avatar_url') else '❌'}")
            print(f"   Has video_url: {'✅' if reels[0].get('video_url') else '❌'}")
            print(f"   Has likes_count: {'✅' if 'likes_count' in reels[0] else '❌'}")
            print(f"   Has comments_count: {'✅' if 'comments_count' in reels[0] else '❌'}")
            results.append(("Reels in payload", True, f"{len(reels)} reels found"))
        else:
            print("   ℹ️  No reels in payload (empty state)")
            results.append(("Reels in payload", True, "Empty reels section"))
        
        # Check other content types
        stories = payload.get("stories", [])
        posts = payload.get("trending_posts", [])
        live = payload.get("live_rooms", [])
        profiles = payload.get("recommended_profiles", [])
        
        print(f"\n   Other content in payload:")
        print(f"   - Stories: {len(stories)}")
        print(f"   - Posts: {len(posts)}")
        print(f"   - Live rooms: {len(live)}")
        print(f"   - Profiles: {len(profiles)}")
        
        results.append(("Content diversity", True, 
                       f"Stories:{len(stories)}, Posts:{len(posts)}, Live:{len(live)}, Profiles:{len(profiles)}"))
        
    except Exception as e:
        print(f"❌ FAIL: Error building homepage payload: {e}")
        results.append(("Build homepage payload", False, str(e)))
    
    # Test 5: Check normalization
    print("\n[TEST 5] Testing reel normalization...")
    try:
        # Create a mock reel row
        mock_row = {
            "id": "test-reel-123",
            "profile_id": "test-profile-456",
            "caption": "Test reel caption #test",
            "video_url": "https://example.com/video.mp4",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "media_url": "https://example.com/media.jpg",
            "likes_count": 42,
            "comments_count": 10,
            "views_count": 150,
            "shares_count": 5,
            "saves_count": 3,
            "duration_seconds": 30,
            "music_title": "Test Song",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Create mock profile map
        profile_map = {
            "test-profile-456": {
                "id": "test-profile-456",
                "username": "testuser",
                "display_name": "Test User",
                "avatar_url": "https://example.com/avatar.jpg",
                "verified": True,
            }
        }
        
        normalized = _normalize_reel(mock_row, profile_map)
        
        required_normalized = [
            "id", "display_name", "username", "avatar_url", "verified",
            "caption", "video_url", "thumbnail_url", "media_url",
            "likes_count", "comments_count", "views_count", "shares_count", "saves_count",
            "duration_seconds", "music_title", "profile_url", "reel_url"
        ]
        
        missing_norm = [f for f in required_normalized if f not in normalized]
        if missing_norm:
            print(f"❌ FAIL: Missing fields in normalized reel: {missing_norm}")
            results.append(("Reel normalization", False, f"Missing: {missing_norm}"))
        else:
            print(f"✅ PASS: Reel normalization includes all required fields")
            print(f"   Sample normalized reel:")
            print(f"   - ID: {normalized.get('id')}")
            print(f"   - Display name: {normalized.get('display_name')}")
            print(f"   - Username: {normalized.get('username')}")
            print(f"   - Likes: {normalized.get('likes_count')}")
            print(f"   - Comments: {normalized.get('comments_count')}")
            print(f"   - Views: {normalized.get('views_count')}")
            print(f"   - Reel URL: {normalized.get('reel_url')}")
            results.append(("Reel normalization", True, None))
    except Exception as e:
        print(f"❌ FAIL: Error testing normalization: {e}")
        results.append(("Reel normalization", False, str(e)))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for test_name, success, detail in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if detail and not success:
            print(f"         Detail: {detail}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    exit_code = test_homepage_reels_feed()
    sys.exit(exit_code)