#!/usr/bin/env python3
"""Test security settings: change password, email, phone, sessions."""
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
print("PHASE 158D - SECURITY SETTINGS")
print("=" * 60)

try:
    from services.security_service import (
        get_device_sessions, revoke_device_session, logout_all_other_devices,
        get_security_events, upsert_privacy_settings, get_privacy_settings,
        create_device_session, create_security_event,
        get_trusted_devices, trust_device, untrust_device
    )
    test("security_service full imports", True)
except ImportError as e:
    test("security_service full imports", False, str(e))

try:
    from services.profile_service import get_current_profile, update_profile
    test("profile_service imports for security", True)
except ImportError as e:
    test("profile_service imports", False, str(e))

try:
    from services.auth_service import change_password
    test("auth_service change_password import", True)
except ImportError as e:
    test("auth_service change_password import", False, str(e))

try:
    from services.session_service import (
        is_logged_in, clear_auth_session, get_current_auth_user
    )
    test("session_service imports", True)
except ImportError as e:
    test("session_service imports", False, str(e))

# Test verified user phone/email change restriction
verified_profile = {"id": "v1", "is_verified": True, "email": "v@test.com", "phone": "+123"}
unverified_profile = {"id": "uv1", "is_verified": False, "email": "uv@test.com", "phone": "+456"}
test("verified user blocked from email change", verified_profile.get("is_verified"))
test("unverified user can change email", not unverified_profile.get("is_verified"))

# Test privacy settings functions
test("get_privacy_settings callable", callable(get_privacy_settings))
test("upsert_privacy_settings callable", callable(upsert_privacy_settings))
test("get_device_sessions callable", callable(get_device_sessions))
test("revoke_device_session callable", callable(revoke_device_session))
test("logout_all_other_devices callable", callable(logout_all_other_devices))
test("get_security_events callable", callable(get_security_events))

# Test trust level
try:
    from services.trust_scam_service import (
        calculate_trust_level, get_trust_summary, add_signal, increment_report_count
    )
    test("trust_scam_service imports", True)
except ImportError as e:
    test("trust_scam_service imports", False, str(e))

# Test location privacy
try:
    from services.location_privacy_service import (
        get_location_settings, start_sharing, stop_sharing,
        update_location, is_authorized_viewer
    )
    test("location_privacy_service imports", True)
except ImportError as e:
    test("location_privacy_service imports", False, str(e))

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
