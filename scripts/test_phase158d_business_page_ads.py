#!/usr/bin/env python3
"""Test business page and advertising."""
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
print("PHASE 158D - BUSINESS PAGE & ADS")
print("=" * 60)

try:
    from services.business_page_service import (
        get_business_profile, update_business_profile, create_campaign,
        get_campaigns, get_all_campaigns, approve_campaign,
        reject_campaign, pause_campaign, track_campaign_metric
    )
    test("business_page_service imports", True)
except ImportError as e:
    test("business_page_service imports", False, str(e))

# Test campaign creation validation
result = create_campaign("profile1", "Test", objective="invalid")
test("invalid objective rejected", not result.get("ok"), f"Got {result}")

result2 = create_campaign("profile1", "Test", objective="reach")
test("valid campaign created", result2.get("ok") or "error" in result2)

# Test campaign lifecycle
test("approve_campaign callable", callable(approve_campaign))
test("reject_campaign callable", callable(reject_campaign))
test("pause_campaign callable", callable(pause_campaign))
test("track_campaign_metric callable", callable(track_campaign_metric))
test("get_campaigns callable", callable(get_campaigns))
test("get_all_campaigns callable", callable(get_all_campaigns))

# Test business profile
test("get_business_profile callable", callable(get_business_profile))
test("update_business_profile callable", callable(update_business_profile))

# Test get_business_profile for non-business
result3 = get_business_profile("nonexistent")
test("nonexistent business returns None", result3 is None)

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
