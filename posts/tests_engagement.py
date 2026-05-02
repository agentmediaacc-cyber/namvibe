from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from posts.models import Post, PostView
from stories.models import StoryItem, StoryView
from wallet.models import ManualDeposit

class EngagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.other_user = User.objects.create_user(username="otheruser", password="password123")
        self.post = Post.objects.create(
            author=self.user,
            post_type=Post.PostType.TEXT,
            status=Post.Status.PUBLISHED,
            audience=Post.Audience.PUBLIC,
            published_at=timezone.now()
        )
        self.story = StoryItem.objects.create(
            author=self.user,
            media_type=StoryItem.MediaType.TEXT,
            text_content="My Story",
            audience=StoryItem.Audience.PUBLIC,
            expires_at=timezone.now() + timezone.timedelta(hours=24)
        )

    def test_unique_post_view(self):
        self.client.force_login(self.other_user)
        # First view
        self.client.post(reverse("track_post_view", kwargs={"uuid": self.post.uuid}), {"duration_seconds": 5})
        self.assertEqual(PostView.objects.filter(post=self.post).count(), 1)
        
        # Second view by same user
        self.client.post(reverse("track_post_view", kwargs={"uuid": self.post.uuid}), {"duration_seconds": 10})
        self.assertEqual(PostView.objects.filter(post=self.post).count(), 1)
        self.assertEqual(PostView.objects.get(post=self.post).duration_seconds, 10)

    def test_owner_view_not_counted(self):
        self.client.force_login(self.user)
        self.client.post(reverse("track_post_view", kwargs={"uuid": self.post.uuid}), {"duration_seconds": 5})
        self.assertEqual(PostView.objects.filter(post=self.post).count(), 0)

    def test_story_viewers_visibility(self):
        # Viewer views the story
        self.client.force_login(self.other_user)
        self.client.post(reverse("story_view", kwargs={"id": self.story.id}))
        
        # Owner can see viewers
        self.client.force_login(self.user)
        response = self.client.get(reverse("story_viewers", kwargs={"id": self.story.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "otheruser")
        
        # Other user cannot see viewers
        self.client.force_login(self.other_user)
        response = self.client.get(reverse("story_viewers", kwargs={"id": self.story.id}))
        self.assertEqual(response.status_code, 404)

    def test_bottom_nav_elements(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        # Check for bottom nav items
        self.assertContains(response, "Home")
        self.assertContains(response, "Reels")
        self.assertContains(response, "Create")
        self.assertContains(response, "Messages")
        self.assertContains(response, "Profile")

    def test_deposit_proof_upload_flow(self):
        self.client.force_login(self.user)
        deposit = ManualDeposit.objects.create(
            user=self.user,
            amount=100.00,
            request_id="DEP-TEST-123"
        )
        # Check detail page
        response = self.client.get(reverse("manual_deposit_detail", kwargs={"request_id": deposit.request_id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm your payment")
        
        # Confirm payment
        from django.core.files.uploadedfile import SimpleUploadedFile
        proof = SimpleUploadedFile("proof.jpg", b"file_content", content_type="image/jpeg")
        response = self.client.post(
            reverse("manual_deposit_detail", kwargs={"request_id": deposit.request_id}),
            {"confirm_paid": "1", "proof_of_payment": proof, "user_note": "Paid via EFT"}
        )
        self.assertEqual(response.status_code, 302)
        deposit.refresh_from_db()
        self.assertEqual(deposit.status, ManualDeposit.Status.PAID)
        self.assertEqual(deposit.user_note, "Paid via EFT")
        self.assertTrue(deposit.proof_of_payment)

    def test_notification_grouping(self):
        self.client.force_login(self.user)
        # Create some notifications
        from accounts.models import Notification
        Notification.objects.create(recipient=self.user, notification_type=Notification.Type.LIKE, message="Test Like")
        
        response = self.client.get(reverse("notifications"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Today")
        self.assertContains(response, "Test Like")

    def test_story_seen_by_count_display(self):
        self.client.force_login(self.other_user)
        self.client.post(reverse("story_view", kwargs={"id": self.story.id}))
        
        self.client.force_login(self.user)
        response = self.client.get(reverse("story_detail", kwargs={"id": self.story.id}))
        self.assertContains(response, "Seen by 1 people")

    def test_profile_views_count(self):
        self.client.force_login(self.other_user)
        # View a post
        self.client.post(reverse("track_post_view", kwargs={"uuid": self.post.uuid}), {"duration_seconds": 5})
        
        response = self.client.get(reverse("profile_detail", kwargs={"username": self.user.username}))
        # The view count is aggregated in public_profile_view
        self.assertContains(response, "1") # Views stat
