#!/usr/bin/env python3
"""
Audit script for homepage bugfixes.
Checks for:
1. Required files exist
2. Routes are registered
3. Templates exist
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_file_exists(path):
    """Check if a file exists."""
    exists = os.path.exists(path)
    status = "✅" if exists else "❌"
    print(f"  {status} {path}")
    return exists

def check_route_registered(app, route):
    """Check if a route is registered in the Flask app."""
    rules = [r.rule for r in app.url_map.iter_rules()]
    found = route in rules
    status = "✅" if found else "❌"
    print(f"  {status} {route}")
    return found

def main():
    print("=" * 60)
    print("NamVibe Homepage Bugfix Audit")
    print("=" * 60)
    
    all_passed = True
    
    # 1. Check required files
    print("\n📁 File Checks:")
    files_to_check = [
        "templates/feedback.html",
        "api_routes/public_routes.py",
        "api_routes/reels_routes.py",
    ]
    for f in files_to_check:
        if not check_file_exists(f):
            all_passed = False
    
    # 2. Check CSS file
    print("\n📄 CSS File Checks:")
    css_files = [
        "static/css/namvibe_home_pro.css",
    ]
    for f in css_files:
        if not check_file_exists(f):
            all_passed = False
    
    # 3. Check routes
    print("\n🔗 Route Checks:")
    try:
        from app import create_app
        app = create_app()
        
        routes_to_check = [
            "/feedback/",
            "/reels/api/reels/view/batch",
        ]
        for route in routes_to_check:
            if not check_route_registered(app, route):
                all_passed = False
    except Exception as e:
        print(f"  ❌ Could not import app: {e}")
        all_passed = False
    
    # 4. Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All checks passed!")
        return 0
    else:
        print("❌ Some checks failed. Review above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())