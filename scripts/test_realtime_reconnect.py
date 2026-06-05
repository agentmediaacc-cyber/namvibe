import unittest
from unittest.mock import patch

from app import create_app
from services.socketio_service import socketio


class TestRealtimeReconnect(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def _socket(self):
        return socketio.test_client(self.app, flask_test_client=self.client)

    def test_duplicate_client_event_returns_same_message(self):
        with patch("services.socket_events._get_profile_id", return_value="p1"), \
             patch("services.socket_events.set_online"), \
             patch("services.socket_events.set_offline"), \
             patch("services.socket_events.set_add"), \
             patch("services.socket_events.set_members", return_value={"sid"}), \
             patch("services.socket_events.get_json", return_value={"rooms": []}), \
             patch("services.socket_events.set_json"), \
             patch("services.socket_events.send_message", return_value={"success": True, "server_message_id": "m1", "client_event_id": "evt-1", "duplicate": True}):
            sock = self._socket()
            result = sock.emit("send_message", {"thread_id": "t1", "client_event_id": "evt-1", "body": "hi"}, callback=True)
            self.assertTrue(result["duplicate"])
            self.assertEqual(result["server_message_id"], "m1")
            sock.disconnect()

    def test_unauthenticated_private_send_rejected(self):
        sock = self._socket()
        result = sock.emit("send_message", {"thread_id": "t1", "body": "hi"}, callback=True)
        self.assertFalse(result["success"])
        sock.disconnect()


if __name__ == "__main__":
    unittest.main(verbosity=2)
