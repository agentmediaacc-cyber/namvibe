from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Block
from ads.models import Advertisement
from posts.models import Post
from stories.models import StoryComment, StoryItem, StoryReaction, StoryShare, StoryView


class HomepageProductionTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="home_author", password="Pass12345", first_name="Home Author")
        self.viewer = User.objects.create_user(username="home_viewer", password="Pass12345")
        self.public_post = Post.objects.create(
            author=self.author,
            title="Homepage public post",
            caption="Visible on home",
            audience=Post.Audience.PUBLIC,
            status=Post.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.private_post = Post.objects.create(
            author=self.author,
            title="Homepage private post",
            audience=Post.Audience.PRIVATE,
            status=Post.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.story = StoryItem.objects.create(
            author=self.author,
            media_type=StoryItem.MediaType.TEXT,
            text_content="Public story",
            audience=StoryItem.Audience.PUBLIC,
            expires_at=timezone.now() + timezone.timedelta(hours=4),
        )

    def test_homepage_loads_and_shows_public_posts(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Homepage public post")
        self.assertNotContains(response, "Homepage private post")
        self.assertContains(response, "Public story")

    def test_expired_stories_do_not_appear(self):
        self.story.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        self.story.save(update_fields=["expires_at"])

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, "Public story")

    def test_blocked_user_stories_are_hidden(self):
        self.client.force_login(self.viewer)
        Block.objects.create(blocker=self.viewer, blocked=self.author)

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, "Public story")

    def test_story_creation_flow_works(self):
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse("story_create"),
            {
                "media_type": StoryItem.MediaType.TEXT,
                "text_content": "Viewer story",
                "caption": "Now",
                "background_style": "midnight",
                "text_style": "clean",
                "audience": StoryItem.Audience.PUBLIC,
                "duration_hours": "24",
            },
        )

        story = StoryItem.objects.get(author=self.viewer, text_content="Viewer story")
        self.assertRedirects(response, reverse("story_detail", kwargs={"id": story.id}), fetch_redirect_response=False)

    def test_story_like_comment_share_view_work(self):
        self.client.force_login(self.viewer)

        like_response = self.client.post(reverse("story_like", kwargs={"id": self.story.id}))
        comment_response = self.client.post(reverse("story_comment", kwargs={"id": self.story.id}), {"body": "Great story"})
        share_response = self.client.post(reverse("story_share", kwargs={"id": self.story.id}), {"target": "forward"})
        view_response = self.client.post(reverse("story_view", kwargs={"id": self.story.id}))

        self.assertEqual(like_response.status_code, 302)
        self.assertEqual(comment_response.status_code, 302)
        self.assertEqual(share_response.status_code, 302)
        self.assertEqual(view_response.status_code, 200)
        self.assertTrue(StoryReaction.objects.filter(story=self.story, user=self.viewer).exists())
        self.assertTrue(StoryComment.objects.filter(story=self.story, author=self.viewer).exists())
        self.assertTrue(StoryShare.objects.filter(story=self.story, user=self.viewer).exists())
        self.assertTrue(StoryView.objects.filter(story=self.story, viewer=self.viewer).exists())

    def test_sponsored_content_only_active_in_range_and_click_tracks(self):
        active_ad = Advertisement.objects.create(
            title="Active Home Ad",
            sponsor_name="Sponsor",
            description="Active",
            destination_url="https://example.com",
            placement=Advertisement.Placement.HOMEPAGE_TOP,
            status=Advertisement.Status.ACTIVE,
            starts_at=timezone.now() - timezone.timedelta(days=1),
            ends_at=timezone.now() + timezone.timedelta(days=1),
        )
        Advertisement.objects.create(
            title="Paused Home Ad",
            sponsor_name="Sponsor",
            placement=Advertisement.Placement.HOMEPAGE_TOP,
            status=Advertisement.Status.PAUSED,
            starts_at=timezone.now() - timezone.timedelta(days=1),
            ends_at=timezone.now() + timezone.timedelta(days=1),
        )

        response = self.client.get(reverse("home"))
        active_ad.refresh_from_db()

        self.assertContains(response, "Active Home Ad")
        self.assertNotContains(response, "Paused Home Ad")
        self.assertEqual(active_ad.impression_count, 1)

        click_response = self.client.get(reverse("ad_click", kwargs={"id": active_ad.id}))
        active_ad.refresh_from_db()

        self.assertEqual(click_response.status_code, 302)
        self.assertEqual(active_ad.click_count, 1)

    def test_reels_route_renders_video_posts(self):
        reel_post = Post.objects.create(
            author=self.author,
            title="Homepage reel",
            caption="Short-form",
            post_type=Post.PostType.REEL,
            audience=Post.Audience.PUBLIC,
            status=Post.Status.PUBLISHED,
            published_at=timezone.now(),
        )

        response = self.client.get(reverse("reels_feed"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reel_post.title)
        self.assertContains(response, "Reels")

    def test_feature_starter_routes_render_without_dead_end_copy(self):
        response = self.client.get(reverse("channels"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quick routes")
        self.assertContains(response, "Channels")

    def test_new_feature_routes_render(self):
        routes = [
            (reverse("pink_friday"), "Pink Friday"),
            (reverse("games_home"), "Games"),
            (reverse("live_shows"), "Live Shows"),
            (reverse("dating_live_match"), "Live Match Show"),
        ]

        for url, label in routes:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, label)
