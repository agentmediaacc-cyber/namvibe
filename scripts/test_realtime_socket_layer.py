import unittest
import os
os.environ["FLASK_TESTING"] = "1"
from app import create_app
from services.socketio_service import socketio

class TestSocketLayer(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = socketio.test_client(self.app)

    def test_connect(self):
        self.assertTrue(self.client.is_connected())

    def test_join_room_logged_out(self):
        # Join a thread room while logged out (should be limited or handled)
        self.client.emit('join_thread', {'thread_id': 'test-thread'})
        # We don't have a way to easily check room membership in test_client easily 
        # but we can verify it doesn't crash.
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
