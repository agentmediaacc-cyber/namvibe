import sys
import os
from flask import Flask

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

def test_visible_nav_routes():
    print("Testing Visible Navigation Routes...")
    
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()
    
    routes_to_test = [
        "/",
        "/discover/",
        "/live/",
        "/discover/trending",
        "/reels/",
        "/status/",
        "/notifications/",
        "/messages/",
        "/favorites",
        "/history",
        "/wallet/",
        "/live/studio",
        "/profile/",
        "/auth/login",
        "/search",
        "/stories/",
        "/live/create"
    ]
    
    failed = False
    for route in routes_to_test:
        res = client.get(route, follow_redirects=False)
        status = res.status_code
        
        # We accept 200 (OK), 302 (Redirect to login or other real route), or 301 (Permanent redirect)
        if status not in [200, 301, 302]:
            print(f"[FAIL] {route} returned {status}")
            failed = True
            continue
            
        # If it's a 200, check it's not the "FEATURE" placeholder or 404 template
        if status == 200:
            data = res.data.decode('utf-8')
            if "FEATURE" in data and "This feature is part of the CHAIN premium ecosystem" in data:
                print(f"[FAIL] {route} returned the FEATURE placeholder")
                failed = True
                continue
            if "404 - Not Found" in data:
                print(f"[FAIL] {route} returned a 200 but content says 404")
                failed = True
                continue
        
        # If it's a redirect, we're mostly happy as long as it's not a 404 on the target (but we won't follow here for simplicity)
        # The user specifically mentioned accepting 302 to /auth/login for protected links.
        if status in [301, 302]:
            print(f"[OK] {route} -> {status} (Redirect to {res.location})")
        else:
            print(f"[OK] {route} -> 200")

    if failed:
        print("\nVisible Navigation Route Tests FAILED!")
        sys.exit(1)
    else:
        print("\nVisible Navigation Route Tests PASSED!")

if __name__ == "__main__":
    test_visible_nav_routes()
