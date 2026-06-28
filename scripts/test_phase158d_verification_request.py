#!/usr/bin/env python3
"""Test verification request submission and status."""
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
print("PHASE 158D - VERIFICATION REQUEST")
print("=" * 60)

try:
    from services.verification_request_service import (
        submit_verification, get_verification_status, get_pending_verifications,
        get_verification_detail, approve_verification, reject_verification,
        request_more_info
    )
    test("verification_request_service imports", True)
except ImportError as e:
    test("verification_request_service imports", False, str(e))

# Test submit_verification
result = submit_verification(
    "profile1",
    id_front_url="https://example.com/id_front.jpg",
    id_back_url="https://example.com/id_back.jpg",
    address_proof_url="https://example.com/bill.pdf",
    selfie_video_url="https://example.com/selfie.mp4",
    whatsapp_phone="+265123456789",
    whatsapp_code="123456"
)
test("submit_verification returns dict", isinstance(result, dict))

# Test get_verification_status
status = get_verification_status("nonexistent")
test("nonexistent verification status", status.get("status") == "none" or status.get("submitted") == False)

test("get_pending_verifications callable", callable(get_pending_verifications))
test("get_verification_detail callable", callable(get_verification_detail))
test("approve_verification callable", callable(approve_verification))
test("reject_verification callable", callable(reject_verification))
test("request_more_info callable", callable(request_more_info))

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
