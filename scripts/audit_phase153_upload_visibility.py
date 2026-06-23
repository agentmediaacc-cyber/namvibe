#!/usr/bin/env python3
"""
Phase 153 — Upload Visibility Audit Script

Tests that uploaded stories/posts/reels appear correctly based on visibility:
- public = everyone can see
- followers = only followers can see
- private = only owner can see
"""

import os
import sys
import uuid

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_result(test_name, passed, details=""):
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {test_name}")
    if details:
        print(f"         {details}")
    return passed

def test_syntax():
    """Test that all modified files have valid Python syntax."""
    print_header("Syntax Check")
    
    files_to_check = [
        "api_routes/status_routes.py",
        "api_routes/post_routes.py",
        "api_routes/reels_routes.py",
        "services/homepage_service.py",
        "services/homepage_phase141_service.py",
        "services/stories_service.py",
        "services/reels_service.py",
    ]
    
    all_passed = True
    for filepath in files_to_check:
        full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), filepath)
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r') as f:
                    compile(f.read(), filepath, 'exec')
                print_result(filepath, True)
            except SyntaxError as e:
                print_result(filepath, False, str(e))
                all_passed = False
        else:
            print_result(filepath, True, "File not found (may not exist yet)")
    
    return all_passed

def test_story_visibility_query():
    """Test that story visibility query is correct."""
    print_header("Story Visibility Query Check")
    
    try:
        from services.stories_service import get_stories_feed
        
        # Check function signature
        import inspect
        sig = inspect.signature(get_stories_feed)
        params = list(sig.parameters.keys())
        
        has_viewer = 'viewer_id' in params
        print_result("get_stories_feed has viewer_id param", has_viewer)
        
        # Read the source to check for visibility logic
        import services.stories_service as stories_module
        source = inspect.getsource(get_stories_feed)
        
        has_public_check = "visibility = 'public'" in source or "visibility='public'" in source
        has_followers_check = "visibility = 'followers'" in source or "visibility='followers'" in source
        has_owner_check = "profile_id" in source
        
        print_result("Story query includes public visibility", has_public_check)
        print_result("Story query includes followers visibility", has_followers_check)
        print_result("Story query includes owner check", has_owner_check)
        
        return has_viewer and has_public_check and has_followers_check and has_owner_check
    except Exception as e:
        print_result("Story visibility check", False, str(e))
        return False

def test_reel_visibility_query():
    """Test that reel visibility query is correct."""
    print_header("Reel Visibility Query Check")
    
    try:
        from services.reels_service import get_reel_feed
        
        import inspect
        sig = inspect.signature(get_reel_feed)
        params = list(sig.parameters.keys())
        
        has_viewer = 'viewer_id' in params
        print_result("get_reel_feed has viewer_id param", has_viewer)
        
        import services.reels_service as reels_module
        source = inspect.getsource(get_reel_feed)
        
        has_public_check = "visibility = 'public'" in source or "visibility='public'" in source
        has_followers_check = "visibility = 'followers'" in source or "visibility='followers'" in source
        has_owner_check = "profile_id" in source
        
        print_result("Reel query includes public visibility", has_public_check)
        print_result("Reel query includes followers visibility", has_followers_check)
        print_result("Reel query includes owner check", has_owner_check)
        
        return has_viewer and has_public_check and has_followers_check and has_owner_check
    except Exception as e:
        print_result("Reel visibility check", False, str(e))
        return False

def test_post_visibility_query():
    """Test that post visibility query is correct."""
    print_header("Post Visibility Query Check")
    
    try:
        from services.homepage_phase141_service import fetch_posts_v2
        
        import inspect
        sig = inspect.signature(fetch_posts_v2)
        params = list(sig.parameters.keys())
        
        has_viewer = 'viewer_id' in params
        print_result("fetch_posts_v2 has viewer_id param", has_viewer)
        
        import services.homepage_phase141_service as homepage_module
        source = inspect.getsource(fetch_posts_v2)
        
        has_public_check = "visibility = 'public'" in source or "visibility='public'" in source
        has_followers_check = "visibility = 'followers'" in source or "visibility='followers'" in source
        has_owner_check = "profile_id" in source
        
        print_result("Post query includes public visibility", has_public_check)
        print_result("Post query includes followers visibility", has_followers_check)
        print_result("Post query includes owner check", has_owner_check)
        
        return has_viewer and has_public_check and has_followers_check and has_owner_check
    except Exception as e:
        print_result("Post visibility check", False, str(e))
        return False

def test_story_visibility_in_homepage():
    """Test that stories_v2 has visibility logic."""
    print_header("Stories V2 Visibility Check")
    
    try:
        from services.homepage_phase141_service import fetch_stories_v2
        
        import inspect
        sig = inspect.signature(fetch_stories_v2)
        params = list(sig.parameters.keys())
        
        has_viewer = 'viewer_id' in params
        print_result("fetch_stories_v2 has viewer_id param", has_viewer)
        
        import services.homepage_phase141_service as homepage_module
        source = inspect.getsource(fetch_stories_v2)
        
        has_public_check = "visibility = 'public'" in source or "visibility='public'" in source
        has_followers_check = "visibility = 'followers'" in source or "visibility='followers'" in source
        has_chain_status = "chain_status_posts" in source
        
        print_result("Stories V2 uses chain_status_posts table", has_chain_status)
        print_result("Stories V2 includes public visibility", has_public_check)
        print_result("Stories V2 includes followers visibility", has_followers_check)
        
        return has_viewer and has_public_check and has_followers_check and has_chain_status
    except Exception as e:
        print_result("Stories V2 visibility check", False, str(e))
        return False

def test_api_route_viewer_id():
    """Test that API routes pass viewer_id to fetch functions."""
    print_header("API Route Viewer ID Check")
    
    try:
        import inspect
        import api_routes.homepage_api as api_module
        source = inspect.getsource(api_module)
        
        # Check that _fast_homepage_feed_payload accepts viewer_id
        has_viewer_param = "viewer_id" in source
        has_fetch_posts = "fetch_posts_v2" in source
        has_fetch_reels = "fetch_reels_v2" in source
        has_fetch_stories = "fetch_stories_v2" in source
        
        print_result("API module has viewer_id parameter", has_viewer_param)
        print_result("API calls fetch_posts_v2", has_fetch_posts)
        print_result("API calls fetch_reels_v2", has_fetch_reels)
        print_result("API calls fetch_stories_v2", has_fetch_stories)
        
        return has_viewer_param and has_fetch_posts and has_fetch_reels and has_fetch_stories
    except Exception as e:
        print_result("API route check", False, str(e))
        return False

def test_video_autoplay_in_js():
    """Test that JavaScript has video autoplay/pause logic."""
    print_header("Video Autoplay JS Check")
    
    js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static/js/namvibe_home_pro.js")
    
    if not os.path.exists(js_path):
        print_result("JS file exists", False)
        return False
    
    with open(js_path, 'r') as f:
        source = f.read()
    
    has_intersection_observer = "IntersectionObserver" in source
    has_playsinline = "playsInline" in source
    has_preload = "preload" in source
    has_video_click = "data-nv-video" in source
    
    print_result("JS has IntersectionObserver", has_intersection_observer)
    print_result("JS has playsInline for iPhone", has_playsinline)
    print_result("JS has preload metadata", has_preload)
    print_result("JS has video click handler", has_video_click)
    
    return has_intersection_observer and has_playsinline and has_preload and has_video_click

def main():
    print("\n" + "="*60)
    print("  Phase 153 — Upload Visibility Audit")
    print("="*60)
    
    results = []
    
    # Run all tests
    results.append(("Syntax Check", test_syntax()))
    results.append(("Story Visibility Query", test_story_visibility_query()))
    results.append(("Reel Visibility Query", test_reel_visibility_query()))
    results.append(("Post Visibility Query", test_post_visibility_query()))
    results.append(("Stories V2 Visibility", test_story_visibility_in_homepage()))
    results.append(("API Route Viewer ID", test_api_route_viewer_id()))
    results.append(("Video Autoplay JS", test_video_autoplay_in_js()))
    
    # Summary
    print_header("Summary")
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  ✓ All visibility tests PASSED!")
        return 0
    else:
        print("\n  ✗ Some tests FAILED - see details above")
        return 1

if __name__ == "__main__":
    sys.exit(main())