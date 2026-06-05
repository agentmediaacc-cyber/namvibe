import unittest
from unittest.mock import patch

from app import create_app
from services.socketio_service import socketio


class TestSocketRecovery(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def _socket(self):
        return socketio.test_client(self.app, flask_test_client=self.client)

    def test_reconnect_recovers_rooms_and_heartbeat(self):
        with patch("services.socket_events._get_profile_id", return_value="profile-1"), \
             patch("services.socket_events.set_online"), \
             patch("services.socket_events.set_offline"), \
             patch("services.socket_events.set_add"), \
             patch("services.socket_events.set_members", return_value={"sid-1"}), \
             patch("services.socket_events.get_json", return_value={"rooms": ["thread:thread-1", "live:room-1"]}), \
             patch("services.socket_events.set_json"):
            sock = self._socket()
            events = sock.get_received()
            recovered = next(event for event in events if event["name"] == "socket:recovered")
            self.assertIn("thread:thread-1", recovered["args"][0]["rooms"])
            hb = sock.emit("presence_heartbeat", callback=True)
            self.assertTrue(hb["heartbeat_ack"])
            sock.disconnect()


if __name__ == "__main__":
    unittest.main(verbosity=2)
