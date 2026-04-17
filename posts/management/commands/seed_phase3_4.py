from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Follow
from communities.models import Community, CommunityMembership
from posts.models import Comment, Like, Post, PostView, Save, Share


class Command(BaseCommand):
    help = "Seed Phase 3/4 feed, discovery, and interaction demo data."

    @transaction.atomic
    def handle(self, *args, **options):
        creator, _ = User.objects.get_or_create(username="feed_creator", defaults={"email": "feed@namvibe.test", "first_name": "Feed Creator"})
        viewer, _ = User.objects.get_or_create(username="feed_viewer", defaults={"email": "viewer@namvibe.test", "first_name": "Feed Viewer"})
        friend, _ = User.objects.get_or_create(username="feed_friend", defaults={"email": "friend@namvibe.test", "first_name": "Feed Friend"})
        for user in [creator, viewer, friend]:
            user.set_password("NamvibeDemo1")
            user.save()
            user.profile.display_name = user.first_name or user.username
            user.profile.location = "Windhoek"
            user.profile.save()

        Follow.objects.get_or_create(follower=viewer, following=creator)
        community, _ = Community.objects.get_or_create(
            slug="feed-demo",
            defaults={"name": "Feed Demo", "description": "Trending-style demo posts.", "owner": creator},
        )
        CommunityMembership.objects.get_or_create(community=community, user=creator, defaults={"role": "owner", "status": "active"})
        CommunityMembership.objects.get_or_create(community=community, user=viewer, defaults={"role": "member", "status": "active"})

        posts = []
        for index, post_type in enumerate([Post.PostType.TEXT, Post.PostType.PHOTO, Post.PostType.REEL, Post.PostType.POLL, Post.PostType.FLYER]):
            post, _ = Post.objects.update_or_create(
                author=creator,
                title=f"Trending demo {index + 1}",
                defaults={
                    "post_type": post_type,
                    "caption": "Demo content with interactions for feed ranking.",
                    "hashtags": ["#namvibe", "#trending", "#windhoek"],
                    "audience": Post.Audience.PUBLIC,
                    "share_target": Post.ShareTarget.REELS if post_type == Post.PostType.REEL else Post.ShareTarget.MAIN_FEED,
                    "status": Post.Status.PUBLISHED,
                    "published_at": timezone.now() - timezone.timedelta(hours=index),
                    "like_count": index * 3,
                    "comment_count": index,
                    "share_count": index,
                    "save_count": index,
                    "view_count": 20 + index,
                },
            )
            posts.append(post)

        for post in posts:
            Like.objects.get_or_create(user=viewer, post=post, defaults={"reaction_type": Like.ReactionType.FIRE})
            Save.objects.get_or_create(user=viewer, post=post)
            Share.objects.get_or_create(user=viewer, post=post, target=Share.Target.FEED)
            PostView.objects.get_or_create(user=viewer, post=post, session_key="seed", defaults={"duration_seconds": 12, "completed": True})
            Comment.objects.get_or_create(post=post, author=viewer, body="This is strong Namvibe energy.")
            post.like_count = post.likes.count()
            post.save_count = post.saves.count()
            post.share_count = post.shares.count()
            post.view_count = post.views.count()
            post.comment_count = post.comments.filter(is_deleted=False).count()
            post.save(update_fields=["like_count", "save_count", "share_count", "view_count", "comment_count"])

        self.stdout.write(self.style.SUCCESS("Seeded Phase 3/4 feed and interaction data. Demo password: NamvibeDemo1"))
