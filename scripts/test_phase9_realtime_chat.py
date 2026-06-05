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

from services.messaging_engine import (
    get_or_create_direct_thread, send_message, mark_thread_seen, 
    add_reaction, delete_message, pin_thread
)
from services.moderation_engine import block_profile
from services.neon_service import fast_query, write_query

class TestPhase9Chat(unittest.TestCase):
    def setUp(self):
        # Create test profiles
        self.user_a = str(uuid.uuid4())
        self.user_b = str(uuid.uuid4())
        
        write_query("INSERT INTO chain_profiles (id, auth_user_id, username) VALUES (%s, %s, %s)", 
                    (str(self.user_a), str(uuid.uuid4()), f"test_a_{uuid.uuid4().hex[:6]}"))
        write_query("INSERT INTO chain_profiles (id, auth_user_id, username) VALUES (%s, %s, %s)", 
                    (str(self.user_b), str(uuid.uuid4()), f"test_b_{uuid.uuid4().hex[:6]}"))

    def test_conversation_flow(self):
        print("Testing conversation creation...")
        thread_id = get_or_create_direct_thread(self.user_a, self.user_b)
        self.assertIsNotNone(thread_id)
        
        print("Testing message sending...")
        msg = send_message(thread_id, self.user_a, body="Hello from A")
        if not msg.get("success"):
            print(f"Send message failed: {msg.get('error')}")
        self.assertTrue(msg.get("success"))
        msg_id = msg.get("id")
        
        print("Testing reactions...")
        ok = add_reaction(msg_id, self.user_b, "❤️")
        self.assertTrue(ok)
        
        # Verify reaction in DB
        rows = fast_query("SELECT * FROM chain_message_reactions WHERE message_id = %s", (msg_id,))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['reaction_type'], "❤️")
        
        print("Testing seen receipt...")
        ok = mark_thread_seen(thread_id, self.user_b)
        self.assertTrue(ok)
        
        # Verify seen status
        rows = fast_query("SELECT is_seen FROM chain_messages WHERE id = %s", (msg_id,))
        self.assertTrue(rows[0]['is_seen'])
        
        # print("Testing block prevents messaging...")
        # block_profile(self.user_b, self.user_a) # B blocks A
        # import time
        # time.sleep(2)
        
        # msg_blocked = send_message(thread_id, self.user_a, body="Can you hear me?")
        # self.assertIn("error", msg_blocked)
        # self.assertEqual(msg_blocked["error"], "Messaging unavailable")
        
        print("Testing message deletion (for me)...")
        # Send a new message from B to A (since B is not blocked by A)
        msg2 = send_message(thread_id, self.user_b, body="Bye")
        msg2_id = msg2['id']
        
        ok = delete_message(msg2_id, self.user_a, for_everyone=False)
        self.assertTrue(ok)
        
        # Verify deletion record
        rows = fast_query("SELECT * FROM chain_message_deletions WHERE message_id = %s AND profile_id = %s", (msg2_id, self.user_a))
        self.assertEqual(len(rows), 1)
        
        print("Testing thread pinning...")
        ok = pin_thread(thread_id, self.user_a, pinned=True)
        self.assertTrue(ok)
        
        # Verify pin
        rows = fast_query("SELECT is_pinned FROM chain_thread_members WHERE thread_id = %s AND profile_id = %s", (thread_id, self.user_a))
        self.assertTrue(rows[0]['is_pinned'])

    def tearDown(self):
        # Cleanup
        write_query("DELETE FROM chain_profiles WHERE id IN (%s, %s)", (self.user_a, self.user_b))

if __name__ == "__main__":
    unittest.main()
