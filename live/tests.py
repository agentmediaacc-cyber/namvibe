from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Follow
from .models import LiveMessage, LiveReaction, LiveSession


class LiveCreatorSystemTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="host_live", password="Pass12345", first_name="Host")
        self.viewer = User.objects.create_user(username="viewer_live", password="Pass12345", first_name="Viewer")
        self.other = User.objects.create_user(username="other_live", password="Pass12345", first_name="Other")

    def test_create_scheduled_live_session(self):
        self.client.force_login(self.host)
        response = self.client.post(
            reverse("live_start"),
            {
                "title": "Scheduled Show",
                "description": "Upcoming",
                "starts_at": "2030-01-01T20:00",
                "access_type": LiveSession.AccessType.PUBLIC,
                "chat_enabled": "on",
                "start_mode": "schedule",
            },
        )
        session = LiveSession.objects.get(title="Scheduled Show")
        self.assertRedirects(response, reverse("live_room", kwargs={"uuid": session.uuid}), fetch_redirect_response=False)
        self.assertEqual(session.status, LiveSession.Status.SCHEDULED)

    def test_start_live_session(self):
        self.client.force_login(self.host)
        response = self.client.post(
            reverse("live_start"),
            {
                "title": "Live Now",
                "description": "Now",
                "starts_at": "2030-01-01T20:00",
                "access_type": LiveSession.AccessType.PUBLIC,
                "chat_enabled": "on",
                "start_mode": "now",
            },
        )
        session = LiveSession.objects.get(title="Live Now")
        self.assertRedirects(response, reverse("live_room", kwargs={"uuid": session.uuid}), fetch_redirect_response=False)
        self.assertEqual(session.status, LiveSession.Status.LIVE)

    def test_end_live_session(self):
        session = LiveSession.objects.create(host=self.host, title="End Me", status=LiveSession.Status.LIVE)
        self.client.force_login(self.host)
        response = self.client.post(reverse("live_end", kwargs={"uuid": session.uuid}))
        session.refresh_from_db()
        self.assertRedirects(response, reverse("live_room", kwargs={"uuid": session.uuid}), fetch_redirect_response=False)
        self.assertEqual(session.status, LiveSession.Status.ENDED)

    def test_live_landing_only_shows_live_now_for_live_section(self):
        LiveSession.objects.create(host=self.host, title="Actually Live", status=LiveSession.Status.LIVE)
        LiveSession.objects.create(host=self.host, title="Already Ended", status=LiveSession.Status.ENDED)
        response = self.client.get(reverse("live_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Actually Live")
        self.assertNotContains(response, "Already Ended")

    def test_followers_only_access_is_enforced(self):
        session = LiveSession.objects.create(host=self.host, title="Followers Room", status=LiveSession.Status.LIVE, access_type=LiveSession.AccessType.FOLLOWERS)
        self.client.force_login(self.viewer)
        denied = self.client.get(reverse("live_room", kwargs={"uuid": session.uuid}))
        self.assertEqual(denied.status_code, 403)
        Follow.objects.create(follower=self.viewer, following=self.host)
        allowed = self.client.get(reverse("live_room", kwargs={"uuid": session.uuid}))
        self.assertEqual(allowed.status_code, 200)

    def test_public_session_accessible(self):
        session = LiveSession.objects.create(host=self.host, title="Public Room", status=LiveSession.Status.LIVE)
        response = self.client.get(reverse("live_room", kwargs={"uuid": session.uuid}))
        self.assertEqual(response.status_code, 200)

    def test_chat_message_can_be_posted(self):
        session = LiveSession.objects.create(host=self.host, title="Chat Room", status=LiveSession.Status.LIVE)
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("live_message", kwargs={"uuid": session.uuid}), {"body": "Hello live"})
        self.assertRedirects(response, reverse("live_room", kwargs={"uuid": session.uuid}), fetch_redirect_response=False)
        self.assertTrue(LiveMessage.objects.filter(session=session, user=self.viewer, body="Hello live").exists())

    def test_host_controls_visible_only_to_host(self):
        session = LiveSession.objects.create(host=self.host, title="Control Room", status=LiveSession.Status.LIVE)
        self.client.force_login(self.host)
        host_response = self.client.get(reverse("live_room", kwargs={"uuid": session.uuid}))
        self.assertContains(host_response, "Host controls")
        self.client.force_login(self.viewer)
        viewer_response = self.client.get(reverse("live_room", kwargs={"uuid": session.uuid}))
        self.assertNotContains(viewer_response, "Host controls")

    def test_profile_live_badge_appears(self):
        session = LiveSession.objects.create(host=self.host, title="Profile Live", status=LiveSession.Status.LIVE)
        response = self.client.get(reverse("profile_detail", kwargs={"username": self.host.profile.username}))
        self.assertContains(response, "LIVE now")
        self.assertContains(response, "Profile Live")

    def test_react_endpoint(self):
        session = LiveSession.objects.create(host=self.host, title="React Room", status=LiveSession.Status.LIVE)
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("live_react", kwargs={"uuid": session.uuid}), {"reaction_type": "fire"})
        self.assertRedirects(response, reverse("live_room", kwargs={"uuid": session.uuid}), fetch_redirect_response=False)
        self.assertTrue(LiveReaction.objects.filter(session=session, user=self.viewer, reaction_type="fire").exists())
