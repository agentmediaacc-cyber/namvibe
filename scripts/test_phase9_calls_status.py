import sys
import os
import uuid
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.getcwd())

# Ensure fast local is off for tests
os.environ["CHAIN_FAST_LOCAL"] = "0"

# Mock socketio before other imports
import services.socketio_service
services.socketio_service.socketio = MagicMock()
services.socketio_service.emit_to_thread = MagicMock()
services.socketio_service.emit_to_profile = MagicMock()

from services.call_service import start_call, answer_call, end_call
from services.status_service import create_status, record_view, list_viewers
from services.messaging_engine import get_or_create_direct_thread, send_message
from services.neon_service import fast_query, write_query

class TestPhase9CallsStatus(unittest.TestCase):
    def setUp(self):
        # Create test profiles
        self.user_a = str(uuid.uuid4())
        self.user_b = str(uuid.uuid4())
        
        write_query("INSERT INTO chain_profiles (id, auth_user_id, username) VALUES (%s, %s, %s)", 
                    (str(self.user_a), str(uuid.uuid4()), f"test_a_{uuid.uuid4().hex[:6]}"))
        write_query("INSERT INTO chain_profiles (id, auth_user_id, username) VALUES (%s, %s, %s)", 
                    (str(self.user_b), str(uuid.uuid4()), f"test_b_{uuid.uuid4().hex[:6]}"))

    def test_call_flow(self):
        print("Testing call initiation...")
        thread_id = get_or_create_direct_thread(self.user_a, self.user_b)
        call = start_call(thread_id, self.user_a, self.user_b, call_type='video')
        self.assertIsNotNone(call)
        call_id = call['id']
        
        print("Testing answering call...")
        answered_call, err = answer_call(call_id, self.user_b)
        self.assertIsNone(err)
        self.assertEqual(answered_call['call_status'], 'answered')
        
        print("Testing ending call...")
        ended_call, err = end_call(call_id, self.user_a)
        self.assertIsNone(err)
        self.assertEqual(ended_call['call_status'], 'ended')
        self.assertGreaterEqual(ended_call['duration_seconds'], 0)

    def test_missed_call(self):
        print("Testing missed call flow...")
        thread_id = get_or_create_direct_thread(self.user_a, self.user_b)
        call = start_call(thread_id, self.user_a, self.user_b, call_type='audio')
        call_id = call['id']
        
        # Caller ends before receiver answers
        end_call(call_id, self.user_a)
        
        # Verify status is missed
        rows = fast_query("SELECT call_status FROM chain_call_sessions WHERE id = %s", (call_id,))
        self.assertEqual(rows[0]['call_status'], 'missed')
        
        # Verify notification
        notif_rows = fast_query("SELECT * FROM chain_notifications WHERE recipient_profile_id = %s AND event_type = 'missed_call'", (self.user_b,))
        self.assertGreater(len(notif_rows), 0)

    def test_status_flow(self):
        print("Testing status creation...")
        status = create_status(self.user_a, "My first status", visibility="public")
        self.assertIsNotNone(status)
        status_id = status['id']
        
        print("Testing status view...")
        record_view(status_id, self.user_b)
        
        viewers = list_viewers(status_id)
        self.assertEqual(len(viewers), 1)
        self.assertEqual(viewers[0]['username'].startswith('test_b'), True)
        
        print("Testing status reply...")
        thread_id = get_or_create_direct_thread(self.user_b, self.user_a)
        reply = send_message(thread_id, self.user_b, body="Cool status!", status_id=status_id)
        self.assertTrue(reply.get("success"))
        
        # Verify status reference in message
        rows = fast_query("SELECT status_id FROM chain_messages WHERE id = %s", (reply['id'],))
        self.assertEqual(str(rows[0]['status_id']), status_id)

    def tearDown(self):
        # Cleanup
        write_query("DELETE FROM chain_profiles WHERE id IN (%s, %s)", (self.user_a, self.user_b))

if __name__ == "__main__":
    unittest.main()
