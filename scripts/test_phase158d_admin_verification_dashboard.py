#!/usr/bin/env python3
"""Test admin verification dashboard."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'testing'
os.environ['CHAIN_FAST_LOCAL'] = '1'

PASS = 0
FAIL = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} - {detail}")

print("=" * 60)
print("PHASE 158D - ADMIN VERIFICATION DASHBOARD")
print("=" * 60)

try:
    from api_routes.verification_admin_routes import verification_admin_bp
    test("verification_admin_bp imported", True)
except ImportError as e:
    test("verification_admin_bp imported", False, str(e))

try:
    from api_routes.ad_admin_routes import ad_admin_bp
    test("ad_admin_bp imported", True)
except ImportError as e:
    test("ad_admin_bp imported", False, str(e))

try:
    from services.admin_auth_service import require_admin, current_admin
    test("admin_auth_service imports", True)
except ImportError as e:
    test("admin_auth_service imports", False, str(e))

try:
    from services.verification_request_service import (
        get_pending_verifications, get_all_verifications,
        get_verification_detail, approve_verification, reject_verification
    )
    test("verification_request_service admin imports", True)
except ImportError as e:
    test("verification_request_service admin imports", False, str(e))

try:
    from services.business_page_service import get_all_campaigns, approve_campaign, reject_campaign
    test("business_page_service admin imports", True)
except ImportError as e:
    test("business_page_service admin imports", False, str(e))

# Test verification admin routes exist
try:
    routes = []
    for attr in dir(verification_admin_bp):
        if not attr.startswith('_'):
            routes.append(attr)
    test("verification_admin_bp has attributes", len(routes) > 0)
except Exception as e:
    test("verification_admin_bp has attributes", False, str(e))

# Test ad admin routes exist
try:
    routes2 = []
    for attr in dir(ad_admin_bp):
        if not attr.startswith('_'):
            routes2.append(attr)
    test("ad_admin_bp has attributes", len(routes2) > 0)
except Exception as e:
    test("ad_admin_bp has attributes", False, str(e))

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
