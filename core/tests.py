from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Block, Notification
from ads.models import Advertisement
from core.homepage import homepage_context
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

    def test_logged_in_homepage_hides_join_and_login_ctas(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Create Story")
        self.assertNotContains(response, "Join Namvibe")
        self.assertNotContains(response, "Explore Feed")

    def test_anonymous_homepage_shows_join_login_and_explore(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Join Namvibe")
        self.assertContains(response, "Login")
        self.assertContains(response, "Explore Feed")

    def test_logged_in_homepage_shows_mobile_create_launcher(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="mobileCreateFab"')
        self.assertContains(response, "Create first story", count=1)

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

    def test_hidden_profiles_are_excluded_from_homepage_discovery(self):
        hidden_user = User.objects.create_user(username="hidden_home", password="Pass12345")
        hidden_user.profile.display_name = "Hidden Home"
        hidden_user.profile.is_hidden_by_moderation = True
        hidden_user.profile.save(update_fields=["display_name", "is_hidden_by_moderation"])

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Hidden Home")

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

    def test_public_profile_route_renders(self):
        response = self.client.get(
            reverse("profile_detail", kwargs={"username": self.author.profile.username})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"@{self.author.profile.username}")

    def test_notification_routes_mark_single_and_all_read(self):
        self.client.force_login(self.viewer)
        first = Notification.objects.create(
            recipient=self.viewer,
            sender=self.author,
            notification_type=Notification.Type.FOLLOW,
            message="Followed you",
        )
        Notification.objects.create(
            recipient=self.viewer,
            sender=self.author,
            notification_type=Notification.Type.COMMENT,
            message="Commented",
        )

        single = self.client.post(reverse("notification_mark_read", kwargs={"notification_id": first.id}), {"next": reverse("notifications")})
        first.refresh_from_db()
        self.assertEqual(single.status_code, 302)
        self.assertTrue(first.is_read)

        mark_all = self.client.post(reverse("notifications_mark_all_read"), {"next": reverse("notifications")})
        self.assertEqual(mark_all.status_code, 302)
        self.assertFalse(Notification.objects.filter(recipient=self.viewer, is_read=False).exists())

    def test_homepage_empty_db_and_feed_more_stay_online(self):
        Post.objects.all().delete()
        StoryItem.objects.all().delete()

        home = self.client.get(reverse("home"))
        more = self.client.get(reverse("feed_more"), {"page": 2})

        self.assertEqual(home.status_code, 200)
        self.assertEqual(more.status_code, 200)

    def test_homepage_context_caps_mixed_feed_to_twenty_items(self):
        for index in range(26):
            Post.objects.create(
                author=self.author,
                title=f"Extra post {index}",
                audience=Post.Audience.PUBLIC,
                status=Post.Status.PUBLISHED,
                published_at=timezone.now() - timezone.timedelta(minutes=index + 5),
            )

        request = RequestFactory().get("/")
        request.user = AnonymousUser()

        context = homepage_context(request)

        self.assertLessEqual(len(context["mixed_feed"]), 20)

    def test_feed_more_fragment_does_not_repeat_story_rail(self):
        response = self.client.get(reverse("feed_more"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Create story")
        self.assertNotContains(response, "Latest stories")

    def test_feed_more_empty_page_returns_empty_marker(self):
        response = self.client.get(reverse("feed_more"), {"page": 99})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-feed-empty="true"')

    def test_homepage_story_rail_shows_only_active_stories(self):
        StoryItem.objects.create(
            author=self.author,
            media_type=StoryItem.MediaType.TEXT,
            text_content="Expired homepage story",
            audience=StoryItem.Audience.PUBLIC,
            expires_at=timezone.now() - timezone.timedelta(minutes=5),
        )
        StoryItem.objects.create(
            author=self.viewer,
            media_type=StoryItem.MediaType.TEXT,
            text_content="Fresh homepage story",
            audience=StoryItem.Audience.PUBLIC,
            expires_at=timezone.now() + timezone.timedelta(hours=6),
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fresh homepage story")
        self.assertNotContains(response, "Expired homepage story")
