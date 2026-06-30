import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from services.profile_service import is_adult_profile, is_profile_complete

class TestProfileSystem(unittest.TestCase):
    def test_adult_check(self):
        print("\n[test] Checking adult profile logic...")
        self.assertTrue(is_adult_profile({"date_of_birth": "1990-01-01"}))
        self.assertFalse(is_adult_profile({"date_of_birth": "2015-01-01"}))
        self.assertFalse(is_adult_profile({}))

    def test_profile_completion(self):
        print("\n[test] Checking profile completion logic...")
        required = [
            "username", "full_name", "bio", "avatar_url", "date_of_birth",
            "phone", "email", "town", "region", "country_origin"
        ]
        full_profile = {field: "filled" for field in required}
        self.assertTrue(is_profile_complete(full_profile))
        
        incomplete_profile = {"username": "filled", "full_name": "filled", "bio": "filled"}
        self.assertFalse(is_profile_complete(incomplete_profile))

if __name__ == "__main__":
    unittest.main()
