#!/usr/bin/env python3
"""Test profile completion uses registration data."""
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
print("PHASE 158D - PROFILE COMPLETION REGISTRATION DATA")
print("=" * 60)

try:
    from services.profile_completion_service import (
        calculate_completion, get_completion, update_completion_percentage, COMPLETION_FIELDS
    )
    test("profile_completion_service imports", True)
except ImportError as e:
    test("profile_completion_service imports", False, str(e))

# Test calculate_completion with full profile
full_profile = {
    "full_name": "John Doe",
    "username": "johndoe",
    "avatar_url": "https://example.com/avatar.jpg",
    "cover_url": "https://example.com/cover.jpg",
    "bio": "Hello world",
    "phone": "+123456789",
    "email": "john@example.com",
    "date_of_birth": "1990-01-01",
    "gender": "male",
    "town": "New York",
    "country": "USA",
    "location": "NYC",
    "website": "https://example.com",
    "interests": '["music","sports"]',
    "profile_photo": "https://example.com/photo.jpg",
}
result = calculate_completion(full_profile)
test("calculate_completion returns dict", isinstance(result, dict))
test("completion percentage > 0", result["percentage"] > 0)
test("completion has completed list", "completed" in result)
test("completion has missing list", "missing" in result)
test("full profile 100%", result["percentage"] == 100, f"Got {result['percentage']}%")

# Test with empty profile
empty_profile = {k: "" for k in COMPLETION_FIELDS}
empty_result = calculate_completion(empty_profile)
test("empty profile 0%", empty_result["percentage"] == 0, f"Got {empty_result['percentage']}%")

# Test with partial profile
partial_profile = {
    "full_name": "John",
    "username": "john",
    "avatar_url": "",
    "cover_url": "",
    "bio": "",
    "phone": "",
    "email": "john@test.com",
    "date_of_birth": "",
    "gender": "",
    "town": "",
    "country": "",
    "location": "",
    "website": "",
    "interests": "",
    "profile_photo": "",
}
partial_result = calculate_completion(partial_profile)
test("partial completion > 0 and < 100", 0 < partial_result["percentage"] < 100, f"Got {partial_result['percentage']}%")
test("partial has some completed", len(partial_result["completed"]) > 0)
test("partial has some missing", len(partial_result["missing"]) > 0)

# Test None
null_result = calculate_completion(None)
test("None profile returns safe", null_result["percentage"] == 0)

# Verify the registration fields match what auth collects
registration_fields = ["full_name", "username", "email", "phone", "date_of_birth", "gender", "location", "country", "town"]
for f in registration_fields:
    test(f"registration field '{f}' in completion fields", f in COMPLETION_FIELDS)

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
