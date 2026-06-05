import os
import unittest
from services.profile_service import is_adult_profile, is_profile_complete, required_profile_fields

class TestProfileSystem(unittest.TestCase):
    def test_adult_check(self):
        print("\n[test] Checking adult profile logic...")
        self.assertTrue(is_adult_profile({"date_of_birth": "1990-01-01"}))
        self.assertFalse(is_adult_profile({"date_of_birth": "2015-01-01"}))
        self.assertFalse(is_adult_profile({}))

    def test_profile_completion(self):
        print("\n[test] Checking profile completion logic...")
        required = required_profile_fields()
        full_profile = {field: "filled" for field in required}
        self.assertTrue(is_profile_complete(full_profile))
        
        incomplete_profile = {field: "filled" for field in required[:-1]}
        self.assertFalse(is_profile_complete(incomplete_profile))

if __name__ == "__main__":
    unittest.main()
