import unittest
from unittest.mock import patch

from app import create_app
from services.socketio_service import socketio


class TestRealtimeIntegrity(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def _socket(self):
        return socketio.test_client(self.app, flask_test_client=self.client)

    def test_duplicate_socket_event_suppressed(self):
        with patch("services.socket_events._get_profile_id", return_value="profile-1"), \
             patch("services.socket_events.set_online"), \
             patch("services.socket_events.set_offline"), \
             patch("services.socket_events.set_add"), \
             patch("services.socket_events.set_members", return_value={"sid-1"}), \
             patch("services.socket_events.get_json", return_value={"rooms": []}), \
             patch("services.socket_events.set_json"), \
             patch("services.socket_events._mark_socket_event", side_effect=[True, False]), \
             patch("services.socket_events.send_message", return_value={"success": True, "server_message_id": "m1", "client_event_id": "evt-1", "duplicate": False}):
            sock = self._socket()
            first = sock.emit("room:join", {"room": "thread:thread-1", "event_id": "evt-1"}, callback=True)
            second = sock.emit("room:join", {"room": "thread:thread-1", "event_id": "evt-1"}, callback=True)
            self.assertTrue(first["joined"])
            self.assertFalse(second["joined"])
            sock.disconnect()


if __name__ == "__main__":
    unittest.main(verbosity=2)
