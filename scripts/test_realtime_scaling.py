import unittest
from unittest.mock import patch

from app import create_app
from services.socketio_service import socketio


class TestRealtimeScaling(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.http_client = self.app.test_client()

    def _socket_client(self):
        return socketio.test_client(self.app, flask_test_client=self.http_client)

    def test_room_join_leave_and_recovery(self):
        with patch("services.socket_events._get_profile_id", return_value="profile-1"), \
             patch("services.socket_events.set_online"), \
             patch("services.socket_events.set_offline"), \
             patch("services.socket_events.set_add"), \
             patch("services.socket_events.set_members", return_value=set()), \
             patch("services.socket_events.get_thread", return_value={"id": "thread-2"}), \
             patch("services.socket_events.set_json") as mock_set_json, \
             patch("services.socket_events.get_json", return_value={"rooms": ["thread:thread-1"]}):
            client = self._socket_client()
            connect_events = client.get_received()
            self.assertTrue(any(event["name"] == "socket:recovered" for event in connect_events))
            response = client.emit("join_thread", {"thread_id": "thread-2"}, callback=True)
            self.assertEqual(response["thread_id"], "thread-2")
            leave_response = client.emit("leave_thread", {"thread_id": "thread-2"}, callback=True)
            self.assertEqual(leave_response["thread_id"], "thread-2")
            client.disconnect()
            self.assertTrue(mock_set_json.called)

    def test_message_delivery_ack_and_duplicate_join_prevention(self):
        with patch("services.socket_events._get_profile_id", return_value="profile-1"), \
             patch("services.socket_events.set_online"), \
             patch("services.socket_events.set_offline"), \
             patch("services.socket_events.set_add"), \
             patch("services.socket_events.set_members", return_value={"sid-1"}), \
             patch("services.socket_events.get_json", return_value={"rooms": []}), \
             patch("services.socket_events.set_json"), \
             patch("services.socket_events._mark_socket_event", side_effect=[True, False]), \
             patch("services.socket_events.send_message", return_value={"id": "m1", "message_id": "m1", "server_message_id": "m1", "client_event_id": "c1", "success": True, "duplicate": False}), \
             patch("services.socket_events.acknowledge_delivery", return_value={"message_id": "m1", "profile_id": "profile-1", "acked_at": "2026-05-25T10:00:00+00:00"}):
            client = self._socket_client()
            first = client.emit("room:join", {"room": "thread:thread-1", "event_id": "evt-1"}, callback=True)
            second = client.emit("room:join", {"room": "thread:thread-1", "event_id": "evt-1"}, callback=True)
            send_result = client.emit("message:send", {"thread_id": "thread-1", "body": "hello", "client_event_id": "c1"}, callback=True)
            ack_result = client.emit("message:delivered", {"thread_id": "thread-1", "message_id": "m1"}, callback=True)
            self.assertTrue(first["joined"])
            self.assertFalse(second["joined"])
            self.assertTrue(send_result["success"])
            self.assertTrue(ack_result["ok"])
            client.disconnect()

    def test_heartbeat_cleanup_path(self):
        with patch("services.socket_events._get_profile_id", return_value="profile-1"), \
             patch("services.socket_events.set_online"), \
             patch("services.socket_events.set_offline"), \
             patch("services.socket_events.set_add"), \
             patch("services.socket_events.set_members", return_value={"sid-1"}), \
             patch("services.socket_events.heartbeat") as mock_heartbeat, \
             patch("services.socket_events.set_json") as mock_set_json, \
             patch("services.socket_events.get_json", return_value={"rooms": ["thread:thread-9"]}):
            client = self._socket_client()
            response = client.emit("presence_heartbeat", callback=True)
            self.assertTrue(response["ok"])
            self.assertTrue(mock_heartbeat.called)
            self.assertTrue(mock_set_json.called)
            client.disconnect()

    def test_logged_out_cannot_send_private_message_and_room_names(self):
        client = self._socket_client()
        result = client.emit("send_message", {"thread_id": "thread-1", "body": "hello"}, callback=True)
        self.assertFalse(result["success"])
        from services.socketio_service import live_room, profile_room, thread_room
        self.assertEqual(profile_room("p1"), "profile:p1")
        self.assertEqual(thread_room("t1"), "thread:t1")
        self.assertEqual(live_room("l1"), "live:l1")
        client.disconnect()

    def test_reconnect_sync_returns_messages(self):
        with patch("services.socket_events._get_profile_id", return_value="profile-1"), \
             patch("services.socket_events.set_online"), \
             patch("services.socket_events.set_offline"), \
             patch("services.socket_events.set_add"), \
             patch("services.socket_events.set_members", return_value={"sid-1"}), \
             patch("services.socket_events.set_json"), \
             patch("services.socket_events.get_json", return_value={"rooms": []}), \
             patch("services.socket_events.sync_thread_messages", return_value=[{"id": "m1"}]):
            client = self._socket_client()
            result = client.emit("reconnect_sync", {"thread_id": "thread-1", "last_seen_message_id": "m0"}, callback=True)
            self.assertTrue(result["success"])
            self.assertEqual(result["messages"][0]["id"], "m1")
            client.disconnect()


if __name__ == "__main__":
    unittest.main(verbosity=2)
