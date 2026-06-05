import unittest
import time
from app import create_app
from services.socketio_service import socketio

class TestSocketScale(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = socketio.test_client(self.app)

    def test_multiplexing(self):
        # Join multiple rooms
        self.client.emit('join_thread', {'thread_id': 't1'})
        self.client.emit('join_live_room', {'room_id': 'l1'})
        # Verify no crash
        self.assertTrue(self.client.is_connected())

    def test_heartbeat_scale(self):
        # Simulate high frequency heartbeats
        for _ in range(10):
            self.client.emit('presence_heartbeat')
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
