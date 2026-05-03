from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch

from django.utils import timezone

from accounts.models import Follow, FriendRequest, Notification
from accounts.supabase import supabase_profile_id_for_user
from communities.models import Community, CommunityMembership
from core.media import profile_avatar_url, profile_cover_url
from live.models import LiveSession
from stories.models import StoryItem
from .models import Comment, CommentReaction, FlyerMeta, Like, LiveAnnouncement, Poll, Post, PostView, Report, Save, Share
from .supabase_posts import create_post as supabase_create_post


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
        self.assertNotContains(response, "Flyer builder")
        self.assertNotContains(response, "Motion, poll, and engagement")


class UnifiedPostFlowTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="author", password="Pass12345", first_name="Author")
        self.viewer = User.objects.create_user(username="viewer", password="Pass12345")
        self.friend = User.objects.create_user(username="friend", password="Pass12345")

    def test_create_text_post_from_studio_publishes(self):
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("studio"),
            {
                "post_type": Post.PostType.TEXT,
                "title": "Hello Namvibe",
                "caption": "First database post",
                "hashtags_text": "#namvibe #windhoek",
                "mentions_text": "@viewer",
                "audience": Post.Audience.PUBLIC,
                "share_target": Post.ShareTarget.MAIN_FEED,
                "allow_comments": "on",
                "allow_sharing": "on",
            },
        )

        post = Post.objects.get(title="Hello Namvibe")
        self.assertRedirects(response, reverse("post_detail", kwargs={"uuid": post.uuid}), fetch_redirect_response=False)
        self.assertEqual(post.status, Post.Status.PUBLISHED)
        self.assertIsNotNone(post.published_at)
        self.assertEqual(post.hashtags, ["#namvibe", "#windhoek"])
        self.assertEqual(post.mentions, ["@viewer"])

    def test_save_draft_and_publish_draft(self):
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("save_draft"),
            {
                "post_type": Post.PostType.TEXT,
                "title": "Draft post",
                "caption": "Not ready",
                "audience": Post.Audience.PUBLIC,
                "share_target": Post.ShareTarget.MAIN_FEED,
            },
        )
        post = Post.objects.get(title="Draft post")

        self.assertRedirects(response, reverse("studio_draft", kwargs={"uuid": post.uuid}), fetch_redirect_response=False)
        self.assertEqual(post.status, Post.Status.DRAFT)
        self.assertIsNone(post.published_at)

        publish_response = self.client.post(reverse("publish_draft", kwargs={"uuid": post.uuid}))
        post.refresh_from_db()

        self.assertRedirects(publish_response, reverse("post_detail", kwargs={"uuid": post.uuid}), fetch_redirect_response=False)
        self.assertEqual(post.status, Post.Status.PUBLISHED)
        self.assertIsNotNone(post.published_at)

    def test_flyer_poll_and_live_metadata_are_created(self):
        self.client.force_login(self.author)

        self.client.post(
            reverse("studio"),
            {
                "post_type": Post.PostType.FLYER,
                "title": "Flyer",
                "caption": "Flyer caption",
                "audience": Post.Audience.PUBLIC,
                "share_target": Post.ShareTarget.MAIN_FEED,
                "flyer_title": "Market Night",
                "flyer_body": "Friday in Windhoek",
                "flyer_cta": "Book now",
            },
        )
        self.assertTrue(FlyerMeta.objects.filter(flyer_title="Market Night").exists())

        self.client.post(
            reverse("studio"),
            {
                "post_type": Post.PostType.POLL,
                "title": "Poll",
                "caption": "Vote",
                "audience": Post.Audience.PUBLIC,
                "share_target": Post.ShareTarget.MAIN_FEED,
                "poll_question": "Choose one",
                "poll_options": "One\nTwo",
            },
        )
        poll = Poll.objects.get(question="Choose one")
        self.assertEqual(poll.options.count(), 2)

        self.client.post(
            reverse("studio"),
            {
                "post_type": Post.PostType.LIVE,
                "title": "Live",
                "caption": "Join live",
                "audience": Post.Audience.PUBLIC,
                "share_target": Post.ShareTarget.LIVE,
                "stream_title": "Creator live",
                "scheduled_for": "2030-01-01T18:00",
                "access_type": "public",
                "ticket_price": "0",
            },
        )
        self.assertTrue(LiveAnnouncement.objects.filter(stream_title="Creator live").exists())

    def test_visibility_filters_public_followers_and_community_posts(self):
        community = Community.objects.create(name="Creators", slug="creators", owner=self.author)
        CommunityMembership.objects.create(community=community, user=self.viewer, status=CommunityMembership.Status.ACTIVE)
        public_post = Post.objects.create(author=self.author, title="Public", audience=Post.Audience.PUBLIC, status=Post.Status.PUBLISHED, published_at="2030-01-01T00:00Z")
        follower_post = Post.objects.create(author=self.author, title="Followers", audience=Post.Audience.FOLLOWERS, status=Post.Status.PUBLISHED, published_at="2030-01-01T00:00Z")
        community_post = Post.objects.create(author=self.author, title="Community", audience=Post.Audience.COMMUNITY, community=community, status=Post.Status.PUBLISHED, published_at="2030-01-01T00:00Z")
        private_post = Post.objects.create(author=self.author, title="Private", audience=Post.Audience.PRIVATE, status=Post.Status.PUBLISHED, published_at="2030-01-01T00:00Z")

        visible_before_follow = set(Post.objects.visible_to(self.viewer))
        self.assertIn(public_post, visible_before_follow)
        self.assertIn(community_post, visible_before_follow)
        self.assertNotIn(follower_post, visible_before_follow)
        self.assertNotIn(private_post, visible_before_follow)

        Follow.objects.create(follower=self.viewer, following=self.author)
        visible_after_follow = set(Post.objects.visible_to(self.viewer))
        self.assertIn(follower_post, visible_after_follow)

    def test_author_and_community_post_lists_load(self):
        community = Community.objects.create(name="Creators", slug="creators", owner=self.author)
        Post.objects.create(
            author=self.author,
            community=community,
            title="Community visible",
            audience=Post.Audience.PUBLIC,
            status=Post.Status.PUBLISHED,
            published_at="2030-01-01T00:00Z",
        )

        author_response = self.client.get(reverse("author_posts", kwargs={"username": self.author.profile.username}))
        community_response = self.client.get(reverse("community_posts", kwargs={"slug": community.slug}))

        self.assertEqual(author_response.status_code, 200)
        self.assertContains(author_response, "Community visible")
        self.assertEqual(community_response.status_code, 200)
        self.assertContains(community_response, "Community visible")

    def test_public_profile_page_shows_real_post_grid(self):
        Post.objects.create(
            author=self.author,
            title="Profile grid post",
            caption="Visible on the public profile",
            audience=Post.Audience.PUBLIC,
            status=Post.Status.PUBLISHED,
            published_at="2030-01-01T00:00Z",
        )

        response = self.client.get(reverse("profile_detail", kwargs={"username": self.author.profile.username}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Posts")
        self.assertContains(response, "Media")
        self.assertContains(response, "About")
        self.assertContains(response, "Profile grid post")

    def test_studio_create_alias_loads(self):
        self.client.force_login(self.author)

        response = self.client.get(reverse("studio_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Creator Studio")
        self.assertContains(response, "Preview before publishing")
        self.assertContains(response, "Publish now")

    @patch("posts.views.create_post")
    def test_feed_create_syncs_supabase_with_profile_uuid_not_session_integer(self, create_post_mock):
        self.client.force_login(self.author)
        session = self.client.session
        session["eharo_user_id"] = "15"
        session["eharo_full_name"] = "Wrong Session Name"
        session["eharo_username"] = "wrong-session"
        session["eharo_email"] = "wrong@example.com"
        session.save()

        image = SimpleUploadedFile("post.jpg", b"fake-image-bytes", content_type="image/jpeg")
        response = self.client.post(
            reverse("create_post"),
            {"content": "Studio sync test", "post_type": "photo", "media": image},
        )

        self.assertRedirects(response, reverse("feed"), fetch_redirect_response=False)
        self.assertEqual(create_post_mock.call_args.kwargs["user_id"], str(supabase_profile_id_for_user(self.author)))
        self.assertNotEqual(create_post_mock.call_args.kwargs["user_id"], "15")

    def test_feed_create_get_redirects_to_studio(self):
        self.client.force_login(self.author)

        response = self.client.get(reverse("create_post"))

        self.assertRedirects(response, reverse("studio"), fetch_redirect_response=False)

    def test_safe_profile_media_helpers_fallback_without_files(self):
        self.assertIn("default-avatar.svg", profile_avatar_url(self.author.profile))
        self.assertIn("default-cover.svg", profile_cover_url(self.author.profile))

    @patch("posts.supabase_posts._supabase_ready", return_value=True)
    @patch("posts.supabase_posts.requests.post")
    def test_supabase_create_post_skips_invalid_non_uuid_user_ids(self, requests_post, _supabase_ready):
        created = supabase_create_post(user_id="15", title="Broken UUID")

        self.assertIsNone(created)
        requests_post.assert_not_called()


class FeedDiscoveryInteractionTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="ranker", password="Pass12345", first_name="Ranker")
        self.other = User.objects.create_user(username="other", password="Pass12345", first_name="Other")
        self.viewer = User.objects.create_user(username="viewer2", password="Pass12345", first_name="Viewer")
        self.author.profile.display_name = "Ranked Creator"
        self.author.profile.location = "Windhoek"
        self.author.profile.save()
        self.viewer.profile.location = "Windhoek"
        self.viewer.profile.save()
        self.public_post = Post.objects.create(
            author=self.author,
            title="Public ranked post",
            caption="Searchable Namvibe content",
            hashtags=["#namvibe", "#windhoek"],
            audience=Post.Audience.PUBLIC,
            status=Post.Status.PUBLISHED,
            published_at=timezone.now(),
            like_count=5,
            comment_count=2,
        )
        self.followers_post = Post.objects.create(
            author=self.author,
            title="Followers only",
            audience=Post.Audience.FOLLOWERS,
            status=Post.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.other_post = Post.objects.create(
            author=self.other,
            title="Other public post",
            hashtags=["#coast"],
            audience=Post.Audience.PUBLIC,
            status=Post.Status.PUBLISHED,
            published_at=timezone.now(),
        )

    def test_feed_loads_database_posts(self):
        response = self.client.get(reverse("feed"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public ranked post")

    def test_following_feed_filters_correctly(self):
        Follow.objects.create(follower=self.viewer, following=self.author)
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("feed_following"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public ranked post")
        self.assertContains(response, "Followers only")
        self.assertNotContains(response, "Other public post")

    def test_trending_feed_returns_ranked_published_posts(self):
        response = self.client.get(reverse("feed_trending"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public ranked post")

    def test_hashtag_page_loads_matching_posts(self):
        response = self.client.get(reverse("hashtag", kwargs={"tag": "namvibe"}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public ranked post")
        self.assertNotContains(response, "Other public post")

    def test_search_results_include_posts_users_and_communities(self):
        Community.objects.create(name="Windhoek Creators", slug="windhoek-creators", owner=self.author)
        StoryItem.objects.create(
            author=self.author,
            media_type=StoryItem.MediaType.TEXT,
            text_content="Windhoek story pulse",
            audience=StoryItem.Audience.PUBLIC,
            expires_at=timezone.now() + timezone.timedelta(hours=4),
        )
        LiveSession.objects.create(
            host=self.author,
            title="Windhoek Live Session",
            description="City vibes",
            status=LiveSession.Status.LIVE,
            access_type=LiveSession.AccessType.PUBLIC,
        )

        response = self.client.get(reverse("discover_search"), {"q": "Windhoek"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public ranked post")
        self.assertContains(response, "@ranker")
        self.assertContains(response, "Windhoek Creators")
        self.assertContains(response, "Windhoek story pulse")
        self.assertContains(response, "Windhoek Live Session")

    def test_like_unlike(self):
        self.client.force_login(self.viewer)

        like_response = self.client.post(reverse("like_post", kwargs={"uuid": self.public_post.uuid}))
        unlike_response = self.client.post(reverse("like_post", kwargs={"uuid": self.public_post.uuid}))

        self.assertRedirects(like_response, reverse("post_detail", kwargs={"uuid": self.public_post.uuid}), fetch_redirect_response=False)
        self.assertRedirects(unlike_response, reverse("post_detail", kwargs={"uuid": self.public_post.uuid}), fetch_redirect_response=False)
        self.assertFalse(Like.objects.filter(user=self.viewer, post=self.public_post).exists())

    def test_save_unsave(self):
        self.client.force_login(self.viewer)

        self.client.post(reverse("save_post_toggle", kwargs={"uuid": self.public_post.uuid}))
        self.assertTrue(Save.objects.filter(user=self.viewer, post=self.public_post).exists())

        self.client.post(reverse("save_post_toggle", kwargs={"uuid": self.public_post.uuid}))
        self.assertFalse(Save.objects.filter(user=self.viewer, post=self.public_post).exists())

    def test_add_reply_and_delete_comment(self):
        self.client.force_login(self.viewer)

        add_response = self.client.post(reverse("add_comment", kwargs={"uuid": self.public_post.uuid}), {"body": "Great post"})
        comment = Comment.objects.get(body="Great post")
        reply_response = self.client.post(reverse("reply_comment", kwargs={"id": comment.id}), {"body": "Reply here"})
        delete_response = self.client.post(reverse("delete_comment", kwargs={"id": comment.id}))
        comment.refresh_from_db()

        self.assertRedirects(add_response, reverse("post_detail", kwargs={"uuid": self.public_post.uuid}), fetch_redirect_response=False)
        self.assertRedirects(reply_response, reverse("post_detail", kwargs={"uuid": self.public_post.uuid}), fetch_redirect_response=False)
        self.assertRedirects(delete_response, reverse("post_detail", kwargs={"uuid": self.public_post.uuid}), fetch_redirect_response=False)
        self.assertTrue(comment.is_deleted)

    def test_comment_reaction_toggle(self):
        self.client.force_login(self.viewer)
        comment = Comment.objects.create(post=self.public_post, author=self.author, body="Talk to me")

        first = self.client.post(reverse("react_comment", kwargs={"id": comment.id}), {"reaction_type": "love"})
        second = self.client.post(reverse("react_comment", kwargs={"id": comment.id}), {"reaction_type": "love"})

        self.assertRedirects(first, reverse("post_detail", kwargs={"uuid": self.public_post.uuid}), fetch_redirect_response=False)
        self.assertRedirects(second, reverse("post_detail", kwargs={"uuid": self.public_post.uuid}), fetch_redirect_response=False)
        self.assertFalse(CommentReaction.objects.filter(user=self.viewer, comment=comment).exists())

    def test_audience_restrictions_on_interactions(self):
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("like_post", kwargs={"uuid": self.followers_post.uuid}))

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Like.objects.filter(user=self.viewer, post=self.followers_post).exists())

    def test_share_creation(self):
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("share_post", kwargs={"uuid": self.public_post.uuid}), {"target": "direct", "message": "Look"})

        self.assertRedirects(response, reverse("post_detail", kwargs={"uuid": self.public_post.uuid}), fetch_redirect_response=False)
        self.assertTrue(Share.objects.filter(user=self.viewer, post=self.public_post, target=Share.Target.DIRECT).exists())

    def test_post_view_tracking(self):
        response = self.client.post(reverse("track_post_view", kwargs={"uuid": self.public_post.uuid}), {"duration_seconds": "7", "completed": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(PostView.objects.filter(post=self.public_post, duration_seconds=7, completed=True).exists())

    def test_post_view_tracking_does_not_duplicate_same_logged_in_viewer(self):
        self.client.force_login(self.viewer)

        first = self.client.post(reverse("track_post_view", kwargs={"uuid": self.public_post.uuid}), {"duration_seconds": "4"})
        second = self.client.post(reverse("track_post_view", kwargs={"uuid": self.public_post.uuid}), {"duration_seconds": "9", "completed": "1"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(PostView.objects.filter(post=self.public_post, user=self.viewer).count(), 1)
        view = PostView.objects.get(post=self.public_post, user=self.viewer)
        self.assertEqual(view.duration_seconds, 9)
        self.assertTrue(view.completed)

    def test_report_flow(self):
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("report_post", kwargs={"uuid": self.public_post.uuid}), {"reason": "spam", "details": "Bad"})

        self.assertRedirects(response, reverse("post_detail", kwargs={"uuid": self.public_post.uuid}), fetch_redirect_response=False)
        self.assertTrue(Report.objects.filter(reporter=self.viewer, post=self.public_post, reason=Report.Reason.SPAM).exists())

    def test_duplicate_report_prevention(self):
        self.client.force_login(self.viewer)

        first = self.client.post(reverse("report_post", kwargs={"uuid": self.public_post.uuid}), {"reason": "spam", "details": "Bad"})
        second = self.client.post(reverse("report_post", kwargs={"uuid": self.public_post.uuid}), {"reason": "spam", "details": "Bad again"})

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Report.objects.filter(reporter=self.viewer, post=self.public_post).count(), 1)

    def test_report_threshold_soft_hides_post(self):
        first = User.objects.create_user(username="reporter_one", password="Pass12345")
        second = User.objects.create_user(username="reporter_two", password="Pass12345")
        third = User.objects.create_user(username="reporter_three", password="Pass12345")

        for reporter in [first, second, third]:
            self.client.force_login(reporter)
            self.client.post(reverse("report_post", kwargs={"uuid": self.public_post.uuid}), {"reason": "spam", "details": "Bad"})

        self.public_post.refresh_from_db()
        self.assertTrue(self.public_post.is_hidden_by_moderation)

    def test_comment_creates_notification_for_post_author(self):
        self.client.force_login(self.viewer)

        response = self.client.post(reverse("add_comment", kwargs={"uuid": self.public_post.uuid}), {"body": "Notification test"})

        self.assertEqual(response.status_code, 302)
        notification = Notification.objects.filter(recipient=self.author, sender=self.viewer).latest("created_at")
        self.assertEqual(notification.notification_type, Notification.Type.COMMENT)

    def test_saved_posts_and_albums_pages_load(self):
        self.client.force_login(self.author)
        photo_post = Post.objects.create(
            author=self.author,
            title="Photo album item",
            post_type=Post.PostType.PHOTO,
            audience=Post.Audience.PUBLIC,
            status=Post.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        Save.objects.create(user=self.author, post=photo_post)

        saved_response = self.client.get(reverse("saved_posts"))
        albums_response = self.client.get(reverse("media_albums"))
        album_detail_response = self.client.get(reverse("media_album_detail", kwargs={"kind": "photos"}))

        self.assertEqual(saved_response.status_code, 200)
        self.assertContains(saved_response, "Saved content")
        self.assertEqual(albums_response.status_code, 200)
        self.assertContains(albums_response, "Media albums")
        self.assertEqual(album_detail_response.status_code, 200)
        self.assertContains(album_detail_response, "Photo album item")

    def test_reels_feed_loads_with_fullscreen_template(self):
        Post.objects.create(
            author=self.author,
            title="Reel post",
            post_type=Post.PostType.REEL,
            audience=Post.Audience.PUBLIC,
            status=Post.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("reels_feed"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/reels_fullscreen.html")
        self.assertIn("reels", response.context)
        self.assertIn("liked_post_ids", response.context)
        self.assertIn("saved_post_ids", response.context)
        self.assertContains(response, "Play")
        self.assertContains(response, "Share")
        self.assertContains(response, "Reply with video")
