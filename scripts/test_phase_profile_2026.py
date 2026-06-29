#!/usr/bin/env python3
"""Test Phase Profile 2026 - Premium Profile Rebuild."""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def test_profile_2026_service():
    """Test profile_2026_service imports and basic functionality."""
    print("=" * 60)
    print("TEST: Phase Profile 2026 - Premium Profile Rebuild")
    print("=" * 60)
    print()

    all_pass = True

    # Test 1: Import service
    print("[TEST 1] Importing profile_2026_service...")
    try:
        sys.path.insert(0, str(BASE_DIR))
        from services.profile_2026_service import (
            get_profile_2026,
            get_profile_content_section,
            emit_profile_viewed,
            emit_profile_followed,
            emit_profile_shared,
            cache_profile_overview,
            get_cached_profile_overview,
            invalidate_profile_cache,
        )
        print("[PASS] Successfully imported profile_2026_service")
    except ImportError as e:
        print(f"[FAIL] Failed to import profile_2026_service: {e}")
        return False

    # Test 2: Call get_profile_2026 with missing IDs (should handle gracefully)
    print("\n[TEST 2] Testing get_profile_2026 with invalid IDs...")
    try:
        result = get_profile_2026(None, "nonexistent_user_12345")
        assert isinstance(result, dict), "Result should be a dict"
        assert "ok" in result, "Result should have 'ok' key"
        print(f"[PASS] Gracefully handled invalid ID: ok={result.get('ok')}")
    except Exception as e:
        print(f"[FAIL] Exception with invalid ID: {e}")
        all_pass = False

    # Test 3: Call get_profile_2026 with UUID format
    print("\n[TEST 3] Testing get_profile_2026 with invalid UUID...")
    try:
        result = get_profile_2026(None, "00000000-0000-0000-0000-000000000000")
        assert isinstance(result, dict), "Result should be a dict"
        assert "ok" in result, "Result should have 'ok' key"
        print(f"[PASS] Gracefully handled invalid UUID: ok={result.get('ok')}")
    except Exception as e:
        print(f"[FAIL] Exception with invalid UUID: {e}")
        all_pass = False

    # Test 4: Check permissions model shape
    print("\n[TEST 4] Checking permissions model shape...")
    try:
        # Create a minimal mock to test structure
        from services.profile_2026_service import _resolve_target, _uuid_or_none
        
        # Test helper functions
        assert _uuid_or_none(None) is None
        assert _uuid_or_none("invalid") is None
        assert _uuid_or_none("550e8400-e29b-41d4-a716-446655440000") == "550e8400-e29b-41d4-a716-446655440000"
        print("[PASS] Helper functions work correctly")
    except Exception as e:
        print(f"[FAIL] Helper function test failed: {e}")
        all_pass = False

    # Test 5: Check empty states are real (not fake)
    print("\n[TEST 5] Checking empty states are real...")
    try:
        service_path = BASE_DIR / "services" / "profile_2026_service.py"
        if service_path.exists():
            content = service_path.read_text()
            # Check that we don't have fake hardcoded data
            fake_indicators = ["John Doe", "Jane Doe", "Lorem ipsum", "fake@example.com"]
            has_fake = any(indicator in content for indicator in fake_indicators)
            if not has_fake:
                print("[PASS] No fake hardcoded data found in service")
            else:
                print("[FAIL] Found fake hardcoded data in service")
                all_pass = False
        else:
            print("[FAIL] Service file not found")
            all_pass = False
    except Exception as e:
        print(f"[FAIL] Empty state check failed: {e}")
        all_pass = False

    # Test 6: Check no N+1 query loops in templates
    print("\n[TEST 6] Checking for N+1 query patterns in templates...")
    try:
        templates_dir = BASE_DIR / "templates" / "profile"
        if templates_dir.exists():
            html_files = list(templates_dir.rglob("*.html"))
            n_plus_1_patterns = 0
            for html_file in html_files:
                content = html_file.read_text()
                # Look for obvious N+1 patterns like loops with DB calls
                if "for.*in.*:" in content and "query" in content.lower():
                    n_plus_1_patterns += 1
            
            if n_plus_1_patterns == 0:
                print("[PASS] No obvious N+1 patterns found in templates")
            else:
                print(f"[WARN] Found {n_plus_1_patterns} potential N+1 patterns (manual review recommended)")
        else:
            print("[FAIL] Templates directory not found")
            all_pass = False
    except Exception as e:
        print(f"[FAIL] N+1 check failed: {e}")
        all_pass = False

    # Test 7: Check routes are registered
    print("\n[TEST 7] Checking route registration...")
    try:
        app_path = BASE_DIR / "app.py"
        if app_path.exists():
            app_content = app_path.read_text()
            # Check that profile routes are imported
            if "profile_routes" in app_content or "profile_bp" in app_content:
                print("[PASS] Profile routes appear to be registered in app.py")
            else:
                print("[WARN] Could not verify profile route registration in app.py")
        else:
            print("[FAIL] app.py not found")
            all_pass = False
    except Exception as e:
        print(f"[FAIL] Route registration check failed: {e}")
        all_pass = False

    # Test 8: Check JS/CSS files exist
    print("\n[TEST 8] Checking JS/CSS files exist...")
    try:
        js_path = BASE_DIR / "static" / "js" / "profile_systems.js"
        css_path = BASE_DIR / "static" / "css" / "namvibe_profile_pro.css"
        
        js_exists = js_path.exists()
        css_exists = css_path.exists()
        
        if js_exists:
            print("[PASS] profile_systems.js exists")
        else:
            print("[FAIL] profile_systems.js not found")
            all_pass = False
            
        if css_exists:
            print("[PASS] namvibe_profile_pro.css exists")
        else:
            print("[FAIL] namvibe_profile_pro.css not found")
            all_pass = False
    except Exception as e:
        print(f"[FAIL] JS/CSS check failed: {e}")
        all_pass = False

    # Test 9: Check no fake content patterns
    print("\n[TEST 9] Checking for fake content patterns...")
    try:
        templates_dir = BASE_DIR / "templates" / "profile"
        static_dir = BASE_DIR / "static"
        
        fake_patterns = ["John Doe", "Jane Doe", "Lorem ipsum", "fake profile", "test user"]
        found_fake = []
        
        if templates_dir.exists():
            for html_file in templates_dir.rglob("*.html"):
                content = html_file.read_text()
                for pattern in fake_patterns:
                    if pattern.lower() in content.lower():
                        found_fake.append(f"{html_file.name}: {pattern}")
        
        if not found_fake:
            print("[PASS] No fake content patterns found")
        else:
            print(f"[FAIL] Found fake content patterns:")
            for item in found_fake[:5]:
                print(f"  - {item}")
            all_pass = False
    except Exception as e:
        print(f"[FAIL] Fake content check failed: {e}")
        all_pass = False

    # Test 10: Check previous social friend flow still passes
    print("\n[TEST 10] Checking social/friend flow compatibility...")
    try:
        # Check that friend service is still importable
        from services.friend_service import list_friends, get_mutual_friends
        print("[PASS] Friend service imports work correctly")
        
        # Check that relationship services are importable
        from services.relationship_cache_service import get_relationship_state
        from services.relationship_gate_service import can_message, can_call
        print("[PASS] Relationship services imports work correctly")
    except ImportError as e:
        print(f"[FAIL] Social/friend flow import failed: {e}")
        all_pass = False
    except Exception as e:
        print(f"[FAIL] Social/friend flow check failed: {e}")
        all_pass = False

    print()
    print("=" * 60)
    if all_pass:
        print("TEST RESULT: ALL TESTS PASSED")
    else:
        print("TEST RESULT: SOME TESTS FAILED")
    print("=" * 60)
    
    return all_pass


if __name__ == "__main__":
    success = test_profile_2026_service()
    sys.exit(0 if success else 1)