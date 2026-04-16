from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch


class PremiumPostStudioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="creator",
            email="creator@example.com",
            password="Pass12345",
            first_name="Creator Name",
        )

    def _login_with_session(self):
        self.client.login(username="creator", password="Pass12345")
        session = self.client.session
        session["eharo_user_id"] = str(self.user.id)
        session["eharo_full_name"] = "Creator Name"
        session["eharo_username"] = "creator"
        session["eharo_email"] = "creator@example.com"
        session.save()

    @patch("posts.views.create_post")
    def test_save_post_passes_premium_studio_metadata(self, create_post_mock):
        self._login_with_session()

        response = self.client.post(reverse("save_post"), {
            "post_type": "flyer",
            "media_type": "flyer",
            "title": "Launch Night",
            "caption": "Join the creator drop",
            "hashtags": "#namvibe #launch",
            "tagged_users": "@maria",
            "audience": "Specific user",
            "share_to": "Specific user",
            "specific_user": "maria",
            "community_name": "Creators",
            "flyer_title": "Creator Launch",
            "flyer_body": "Friday in Windhoek",
            "flyer_cta": "Book now",
            "flyer_background": "gradient-sunset",
            "flyer_text_color": "#ffffff",
            "flyer_layout": "banner",
            "music_track": "namvibe-rise",
            "motion_effect": "slow-zoom",
            "poll_question": "Are you joining?",
            "poll_options": "Yes\nMaybe",
            "allow_comments": "on",
            "allow_share": "on",
            "premium_badge": "on",
        })

        self.assertRedirects(response, f"{reverse('user_dashboard')}?section=posts", fetch_redirect_response=False)
        kwargs = create_post_mock.call_args.kwargs
        self.assertEqual(kwargs["post_type"], "flyer")
        self.assertEqual(kwargs["hashtags"], "#namvibe #launch")
        self.assertEqual(kwargs["tagged_users"], "@maria")
        self.assertEqual(kwargs["audience"], "Specific user")
        self.assertEqual(kwargs["specific_user"], "maria")
        self.assertEqual(kwargs["flyer_title"], "Creator Launch")
        self.assertEqual(kwargs["motion_effect"], "slow-zoom")
        self.assertEqual(kwargs["poll_question"], "Are you joining?")

    @patch("accounts.views.get_posts_by_user", return_value=[])
    def test_dashboard_renders_premium_post_studio(self, _posts):
        self._login_with_session()

        response = self.client.get(reverse("user_dashboard"), {"section": "posts"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Creator Studio")
        self.assertContains(response, "Flyer builder")
        self.assertContains(response, "Motion, poll, and engagement")
