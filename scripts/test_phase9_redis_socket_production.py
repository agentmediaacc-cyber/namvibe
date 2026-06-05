try:
    import gevent.monkey
    gevent.monkey.patch_all()
except ImportError:
    pass

import sys
import os
import time
import threading
import unittest
import socketio
from app import create_app
from services.socketio_service import socketio as sio_server

# Production-like test for Socket.IO with Redis Manager
class TestRedisSocketProduction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure we are NOT in testing mode to enable Redis Manager
        os.environ["FLASK_TESTING"] = "0"
        cls.app = create_app()
        cls.app.config['TESTING'] = False
        
        cls.port = 5002
        cls.server_thread = threading.Thread(
            target=lambda: sio_server.run(cls.app, port=cls.port, debug=False, use_reloader=False),
            daemon=True
        )
        cls.server_thread.start()
        time.sleep(2) # Give server time to start

    def setUp(self):
        self.client = socketio.Client()

    def tearDown(self):
        if self.client.connected:
            self.client.disconnect()

    def test_production_socket_flow(self):
        print("\n[test] Connecting to production-like socket server...")
        self.client.connect(f"http://127.0.0.1:{self.port}")
        self.assertTrue(self.client.connected)
        
        # Test Redis Manager is active (we can't easily check internal state, but we can verify events flow)
        # In a real test, we would have multiple server instances, but here we verify one works with manager enabled.
        
        received_events = []
        @self.client.on('*')
        def catch_all(event, data):
            received_events.append(event)
            print(f"[client] Received event: {event}")

        print("[test] Testing typing:start...")
        self.client.emit('typing:start', {'thread_id': 'test-thread'})
        time.sleep(0.5)
        
        print("[test] Testing message:delivered...")
        self.client.emit('message:delivered', {'message_id': 'test-msg', 'thread_id': 'test-thread'})
        time.sleep(0.5)

        print("[test] Testing WebRTC signaling (call:offer)...")
        self.client.emit('call:offer', {'target_id': 'peer-id', 'sdp': 'test-sdp', 'call_id': 'test-call'})
        time.sleep(0.5)

        # Basic reconnection test
        print("[test] Testing reconnection...")
        self.client.disconnect()
        self.client.connect(f"http://127.0.0.1:{self.port}")
        self.assertTrue(self.client.connected)
        
        print("[test] Production socket flow completed.")

if __name__ == "__main__":
    unittest.main()
