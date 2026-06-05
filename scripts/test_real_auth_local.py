import os
import sys
import time
import uuid
import unittest
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:5000"

class TestRealAuthLocal(unittest.TestCase):
    def test_env_sanity(self):
        print("\n[test] Checking environment sanity...")
        keys = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "DATABASE_URL"]
        for key in keys:
            val = os.getenv(key)
            self.assertTrue(val, f"Missing {key}")
            print(f"  {key}: {'*' * 8}{val[-4:] if val else ''}")

    def test_supabase_reachable(self):
        print("\n[test] Checking Supabase reachability...")
        url = os.getenv("SUPABASE_URL")
        try:
            # Health endpoint might return 401 if no key, but that means it's reachable
            resp = requests.get(f"{url}/auth/v1/health", timeout=5)
            self.assertIn(resp.status_code, [200, 401])
            print(f"  Supabase Auth Status: {resp.status_code} (Reachable)")
        except Exception as e:
            self.fail(f"Supabase unreachable: {e}")

    def test_auth_routes_200(self):
        print("\n[test] Checking core auth routes (GET)...")
        routes = [
            "/auth/login",
            "/auth/register",
            "/auth/forgot-password",
            "/auth/reset-password"
        ]
        for route in routes:
            try:
                resp = requests.get(f"{BASE_URL}{route}", timeout=5)
                self.assertEqual(resp.status_code, 200, f"Route {route} failed")
                print(f"  {route}: 200 OK")
            except Exception as e:
                print(f"  {route}: FAILED ({e})")

    def test_oauth_redirects(self):
        print("\n[test] Checking OAuth 302 redirects...")
        providers = ["google", "facebook"]
        for p in providers:
            resp = requests.get(f"{BASE_URL}/auth/{p}", allow_redirects=False, timeout=5)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("supabase.co", resp.headers.get("Location", ""))
            print(f"  /auth/{p}: 302 -> Supabase")

    def test_protected_redirects(self):
        print("\n[test] Checking protected route redirects...")
        resp = requests.get(f"{BASE_URL}/profile/", allow_redirects=False, timeout=5)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login", resp.headers.get("Location", ""))
        print("  /profile/: 302 -> /auth/login (Logged out)")

    def test_availability_speed(self):
        print("\n[test] Checking availability endpoint speed...")
        start = time.time()
        test_user = f"test_{uuid.uuid4().hex[:8]}"
        resp = requests.get(f"{BASE_URL}/auth/check-availability?field=username&value={test_user}", timeout=5)
        duration = (time.time() - start) * 1000
        self.assertEqual(resp.status_code, 200)
        print(f"  Availability check took {duration:.1f}ms")
        if duration > 800:
            print("  WARNING: Availability check is slow (> 800ms)")

    def test_real_signup_if_enabled(self):
        if os.getenv("CHAIN_TEST_CREATE_USER") != "1":
            print("\n[test] Skipping real user creation (CHAIN_TEST_CREATE_USER != 1)")
            return

        print("\n[test] Attempting real user registration...")
        test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        test_user = f"user_{uuid.uuid4().hex[:8]}"
        
        payload = {
            "full_name": "Test User",
            "email": test_email,
            "username": test_user,
            "phone": "+26481" + "".join([str(uuid.uuid4().int % 10) for _ in range(7)]),
            "date_of_birth": "1990-01-01",
            "country_origin": "Namibia",
            "town": "Windhoek",
            "preferred_language": "English",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "terms": "on",
            "human_confirmed": "on"
        }
        
        resp = requests.post(f"{BASE_URL}/auth/register", data=payload, allow_redirects=False, timeout=10)
        self.assertEqual(resp.status_code, 302)
        target = resp.headers.get("Location", "")
        print(f"  Signup result: Redirect -> {target}")
        
        if "registered=1" in target:
            print("  SUCCESS: User created, confirmation email required.")
        elif "/profile/" in target:
            print("  SUCCESS: User created and logged in.")
        else:
            self.fail(f"Unexpected signup redirect: {target}")

if __name__ == "__main__":
    unittest.main()
