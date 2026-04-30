from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import StoryItem, StoryView
from .services import mark_story_viewed


class StoryViewTrackingTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="story_author", password="Pass12345")
        self.viewer = User.objects.create_user(username="story_viewer", password="Pass12345")
        self.story = StoryItem.objects.create(
            author=self.author,
            media_type=StoryItem.MediaType.TEXT,
            text_content="Story tracking",
            audience=StoryItem.Audience.PUBLIC,
            expires_at=timezone.now() + timezone.timedelta(hours=6),
        )

    def test_story_view_tracking_does_not_duplicate_same_logged_in_viewer(self):
        first = mark_story_viewed(self.viewer, self.story, "session-a")
        second = mark_story_viewed(self.viewer, self.story, "session-a")

        self.assertIsNotNone(first)
        self.assertEqual(first.id, second.id)
        self.assertEqual(StoryView.objects.filter(story=self.story, viewer=self.viewer).count(), 1)

    def test_story_owner_view_does_not_increment_count(self):
        view = mark_story_viewed(self.author, self.story, "owner-session")

        self.assertIsNone(view)
        self.assertEqual(StoryView.objects.filter(story=self.story).count(), 0)

    def test_story_create_page_mentions_public_story_rail(self):
        self.client.force_login(self.author)

        response = self.client.get(reverse("story_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public stories appear on the homepage story rail.")
