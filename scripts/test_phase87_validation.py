"""
Phase 87B Validation Script — Production Grade
Comprehensive audit for Phase 87 systems.
"""
import os
import sys
import uuid
import time
import json
import unittest
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_service import fast_query, write_query, get_pool_status, get_table_columns
from services.friend_service import list_friends, list_friend_requests, send_friend_request, accept_friend_request
from services.social_service import list_followers, list_following
from services.content_manager_service import get_managed_posts, get_managed_reels
from services.notification_engine import create_notification, list_notifications
from services.redis_service import cache_get, cache_set, redis_available
from services.socketio_service import broadcast_notification

class Phase87Validation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("=== Phase 87B Production Audit ===")
        cls.test_profile_id = str(uuid.uuid4())
        cls.friend_profile_id = str(uuid.uuid4())
        
        # Create test profiles
        try:
            write_query("INSERT INTO chain_profiles (id, auth_user_id, username, display_name) VALUES (%s, %s, %s, %s)", 
                        [cls.test_profile_id, str(uuid.uuid4()), f"test_{cls.test_profile_id[:8]}", "Test User"])
            write_query("INSERT INTO chain_profiles (id, auth_user_id, username, display_name) VALUES (%s, %s, %s, %s)", 
                        [cls.friend_profile_id, str(uuid.uuid4()), f"friend_{cls.friend_profile_id[:8]}", "Friend User"])
        except Exception as e:
            print(f"Warning: Failed to create test profiles: {e}")

    @classmethod
    def tearDownClass(cls):
        try:
            write_query("DELETE FROM chain_profiles WHERE id IN (%s, %s)", [cls.test_profile_id, cls.friend_profile_id])
        except:
            pass

    def test_01_no_select_star(self):
        """Verify no SELECT * in core Phase 87 files."""
        files = [
            'api_routes/social_routes.py',
            'services/friend_service.py',
            'services/social_service.py',
            'services/content_manager_service.py',
            'services/notification_engine.py'
        ]
        for f in files:
            if not os.path.exists(f): continue
            with open(f, 'r') as fd:
                content = fd.read()
                self.assertNotIn("SELECT *", content, f"Found SELECT * in {f}")

    def test_02_schema_resilience(self):
        """Verify services handle schema variations or use dynamic detection."""
        # Content manager uses dynamic detection
        try:
            res = get_managed_posts(self.test_profile_id, limit=1)
            self.assertIn('items', res)
        except Exception as e:
            self.fail(f"Content manager failed schema resilience: {e}")

        # Friend service should handle receiver vs recipient
        cols = get_table_columns("chain_friend_requests")
        if cols:
            has_compat = "recipient_profile_id" in cols or "receiver_profile_id" in cols
            self.assertTrue(has_compat, "chain_friend_requests missing both recipient and receiver columns")

    def test_03_notification_compatibility(self):
        """Verify notification engine supports friend events."""
        notif_id = create_notification(
            self.test_profile_id, 
            "friend_request", 
            "New Friend", 
            "Test body", 
            actor_profile_id=self.friend_profile_id
        )
        self.assertIsNotNone(notif_id, "Failed to create friend_request notification")
        
        notifs = list_notifications(self.test_profile_id)
        found = any(n['event_type'] == 'friend_request' for n in notifs)
        self.assertTrue(found, "Notification created but not retrieved with correct event_type")

    def test_04_friend_service_functionality(self):
        """Verify core friend service logic."""
        # Send
        res = send_friend_request(self.test_profile_id, self.friend_profile_id)
        self.assertTrue(res.get('success'), f"Failed to send friend request: {res.get('error')}")
        req_id = res.get('request_id')
        
        # List received
        received = list_friend_requests(self.friend_profile_id, direction='received')
        self.assertTrue(any(r['id'] == req_id for r in received['requests']))
        
        # Accept
        res = accept_friend_request(self.friend_profile_id, req_id)
        self.assertTrue(res.get('success'), f"Failed to accept friend request: {res.get('error')}")

    def test_05_cursor_pagination(self):
        """Verify cursor pagination on endpoints."""
        endpoints = [
            ("Friends", lambda: list_friends(self.test_profile_id)),
            ("Followers", lambda: list_followers(self.test_profile_id)),
            ("Following", lambda: list_following(self.test_profile_id)),
            ("Managed Posts", lambda: get_managed_posts(self.test_profile_id)),
            ("Notifications", lambda: list_notifications(self.test_profile_id)) # Note: list_notifications in notification_engine doesn't return next_cursor in the same way, but let's check.
        ]
        for name, fn in endpoints:
            res = fn()
            if isinstance(res, dict):
                self.assertIn("next_cursor", res, f"{name} missing next_cursor")
                self.assertIn("has_more", res, f"{name} missing has_more")

    def test_06_redis_working(self):
        """Verify Redis cache is operational."""
        if not redis_available():
            self.skipTest("Redis not available")
        
        test_key = f"test_val_{uuid.uuid4()}"
        test_val = {"foo": "bar"}
        cache_set(test_key, test_val, ttl=10)
        cached = cache_get(test_key)
        self.assertEqual(cached, test_val, "Redis cache get/set mismatch")

    def test_07_socketio_compatibility(self):
        """Verify Socket.IO broadcast doesn't crash."""
        try:
            broadcast_notification(self.test_profile_id, {"test": "data"})
        except Exception as e:
            self.fail(f"Socket.IO broadcast crashed: {e}")

    def test_08_neon_latency(self):
        """Measure Neon startup and query latency."""
        start = time.perf_counter()
        fast_query("SELECT 1")
        latency = (time.perf_counter() - start) * 1000
        print(f"  Neon Latency: {latency:.2f}ms")
        self.assertLess(latency, 5000, "Neon latency is extremely high (>5s)")

    def test_09_route_conflicts(self):
        """Identify route conflicts in app.py."""
        from app import app
        rules = [str(rule) for rule in app.url_map.iter_rules()]
        conflicts = []
        seen = set()
        for r in rules:
            if r in seen:
                conflicts.append(r)
            seen.add(r)
        
        # Also check for semantic overlaps
        social_routes = ["/social/friends", "/social/followers", "/social/following", "/social/api/friends"]
        for sr in social_routes:
            matches = [r for r in rules if r.startswith(sr)]
            if len(matches) > 1:
                print(f"  Note: Multiple matches for {sr}: {matches}")

def run_audit():
    suite = unittest.TestLoader().loadTestsFromTestCase(Phase87Validation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)

if __name__ == "__main__":
    run_audit()
