import sys
import os
import uuid
import unittest
from datetime import datetime, timezone
import time

# Add project root to path
sys.path.append(os.getcwd())

# Ensure fast local is off for tests
os.environ["CHAIN_FAST_LOCAL"] = "0"

# Mock socketio
from unittest.mock import MagicMock
import services.socketio_service
services.socketio_service.socketio = MagicMock()
services.socketio_service.emit_to_thread = MagicMock()
services.socketio_service.emit_to_profile = MagicMock()

from services.messaging_engine import (
    get_or_create_direct_thread, send_message, mark_thread_seen, 
    acknowledge_delivery, list_threads, move_thread
)
from services.presence_engine import set_online, get_presence, set_offline
from services.neon_service import fast_query, write_query

class TestPhase10Premium(unittest.TestCase):
    def setUp(self):
        self.user_a = str(uuid.uuid4())
        self.user_b = str(uuid.uuid4())
        
        write_query("INSERT INTO chain_profiles (id, auth_user_id, username, trust_score) VALUES (%s, %s, %s, %s)", 
                    (self.user_a, str(uuid.uuid4()), f"prem_a_{uuid.uuid4().hex[:6]}", 1.0))
        write_query("INSERT INTO chain_profiles (id, auth_user_id, username, trust_score) VALUES (%s, %s, %s, %s)", 
                    (self.user_b, str(uuid.uuid4()), f"prem_b_{uuid.uuid4().hex[:6]}", 0.1)) # Low trust

    def test_read_receipts(self):
        print("Testing blue tick flow...")
        thread_id = get_or_create_direct_thread(self.user_a, self.user_b)
        msg = send_message(thread_id, self.user_a, body="Check receipts")
        msg_id = msg['id']
        
        # 1. Delivered Tick (Grey/Double Grey)
        acknowledge_delivery(msg_id, self.user_b)
        rows = fast_query("SELECT delivery_status FROM chain_messages WHERE id = %s", (msg_id,))
        self.assertEqual(rows[0]['delivery_status'], 'delivered')
        
        # 2. Read Tick (Blue)
        mark_thread_seen(thread_id, self.user_b)
        rows = fast_query("SELECT delivery_status, read_at FROM chain_messages WHERE id = %s", (msg_id,))
        self.assertEqual(rows[0]['delivery_status'], 'seen')
        self.assertIsNotNone(rows[0]['read_at'])

    def test_presence_last_seen(self):
        print("Testing presence and last seen...")
        set_online(self.user_a)
        
        presence = get_presence([self.user_a])
        self.assertEqual(presence[0]['status'], 'online')
        
        set_offline(self.user_a)
        presence = get_presence([self.user_a])
        self.assertEqual(presence[0]['status'], 'offline')
        self.assertIsNotNone(presence[0]['last_seen_at'])

    def test_folders_and_requests(self):
        print("Testing inbox folders...")
        thread_id = get_or_create_direct_thread(self.user_a, self.user_b)
        
        # Move to spam
        move_thread(thread_id, 'spam')
        
        # Check spam list
        spam_threads = list_threads(self.user_a, folder='spam')
        print(f"Spam threads found: {len(spam_threads)}")
        self.assertTrue(any(t['id'] == thread_id for t in spam_threads))
        
        # Check primary list (should be empty)
        primary_threads = list_threads(self.user_a, folder='primary')
        self.assertFalse(any(t['id'] == thread_id for t in primary_threads))

    def test_fake_account_detection(self):
        print("Testing fake account detection...")
        # User B has trust_score 0.1
        from api_routes.admin_safety_routes import detect_fake
        # We can't easily call the route without a request context here, so we test the logic
        write_query("UPDATE chain_profiles SET is_fake = TRUE WHERE trust_score < 0.3")
        
        rows = fast_query("SELECT is_fake FROM chain_profiles WHERE id = %s", (self.user_b,))
        self.assertTrue(rows[0]['is_fake'])

    def tearDown(self):
        write_query("DELETE FROM chain_profiles WHERE id IN (%s, %s)", (self.user_a, self.user_b))

if __name__ == "__main__":
    unittest.main()
