import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import LiveComment, LiveGift, LiveRoom


class LiveRoomFlowTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(
            username="host",
            email="host@example.com",
            password="Pass12345",
            first_name="Host Name",
        )
        self.viewer = User.objects.create_user(username="viewer", email="viewer@example.com", password="Pass12345")

    def _login_host(self):
        self.client.login(username="host", password="Pass12345")
        session = self.client.session
        session["eharo_user_id"] = str(self.host.id)
        session["eharo_full_name"] = "Host Name"
        session["eharo_username"] = "host"
        session["eharo_email"] = "host@example.com"
        session.save()

    def _post_json(self, url, payload=None):
        return self.client.post(
            url,
            data=json.dumps(payload or {}),
            content_type="application/json",
        )

    def test_host_creates_scheduled_room_and_starts_live(self):
        self._login_host()

        create_response = self._post_json(
            reverse("create_live_room_api"),
            {"title": "Launch Live", "audience": "Public", "room_access": "Open Room"},
        )
        room = LiveRoom.objects.get()

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(room.status, LiveRoom.STATUS_SCHEDULED)
        self.assertEqual(room.host, self.host)

        start_response = self._post_json(reverse("start_live_room_api", args=[room.id]))
        room.refresh_from_db()

        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(room.status, LiveRoom.STATUS_LIVE)
        self.assertIsNotNone(room.started_at)

    def test_only_host_can_manage_broadcast(self):
        room = LiveRoom.objects.create(host=self.host, title="Host Only")
        self.client.login(username="viewer", password="Pass12345")

        broadcast_response = self.client.get(reverse("live_broadcast", args=[room.id]))
        start_response = self._post_json(reverse("start_live_room_api", args=[room.id]))

        self.assertEqual(broadcast_response.status_code, 403)
        self.assertEqual(start_response.status_code, 403)

    def test_private_room_requires_login_for_viewer(self):
        room = LiveRoom.objects.create(
            host=self.host,
            title="Private Live",
            audience="Private Room",
            room_access="Invite Only",
        )

        response = self.client.get(reverse("live_join", args=[room.id]))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_comments_and_gifts_persist_to_room(self):
        room = LiveRoom.objects.create(host=self.host, title="Interactive Live", status=LiveRoom.STATUS_LIVE)
        self.client.login(username="viewer", password="Pass12345")

        comment_response = self._post_json(
            reverse("create_live_comment_api", args=[room.id]),
            {"message": "Hello live"},
        )
        gift_response = self._post_json(
            reverse("create_live_gift_api", args=[room.id]),
            {"gift_name": "Star", "token_amount": 10},
        )

        self.assertEqual(comment_response.status_code, 200)
        self.assertEqual(gift_response.status_code, 200)
        self.assertEqual(LiveComment.objects.get().message, "Hello live")
        self.assertEqual(LiveGift.objects.get().sender_username, "viewer")
