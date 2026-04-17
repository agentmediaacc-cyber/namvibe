from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from communities.models import Community, CommunityMembership
from posts.models import FlyerMeta, LiveAnnouncement, Poll, Post


class Command(BaseCommand):
    help = "Seed Phase 2 sample posts for every unified post type."

    @transaction.atomic
    def handle(self, *args, **options):
        author, _ = User.objects.get_or_create(
            username="phase2_creator",
            defaults={"email": "phase2@namvibe.test", "first_name": "Phase Two Creator"},
        )
        author.set_password("NamvibeDemo1")
        author.save()
        author.profile.display_name = "Phase Two Creator"
        author.profile.username = "phase2_creator"
        author.profile.is_creator = True
        author.profile.location = "Windhoek"
        author.profile.save()

        community, _ = Community.objects.get_or_create(
            slug="phase2-creators",
            defaults={
                "name": "Phase 2 Creators",
                "description": "Demo community for unified posts.",
                "owner": author,
            },
        )
        CommunityMembership.objects.get_or_create(
            community=community,
            user=author,
            defaults={"role": CommunityMembership.Role.OWNER, "status": CommunityMembership.Status.ACTIVE},
        )
        community.member_count = CommunityMembership.objects.filter(community=community, status=CommunityMembership.Status.ACTIVE).count()
        community.save(update_fields=["member_count"])

        samples = [
            (Post.PostType.TEXT, "Windhoek creator note", "Building a new Namvibe creator ecosystem."),
            (Post.PostType.PHOTO, "Photo drop", "A placeholder photo post ready for media uploads."),
            (Post.PostType.VIDEO, "Video update", "A placeholder video post ready for storage-backed media."),
            (Post.PostType.STORY, "Story moment", "A story-style post that can be mirrored into stories later."),
            (Post.PostType.REEL, "Reel teaser", "Short-form vertical video metadata is ready."),
        ]
        for post_type, title, caption in samples:
            Post.objects.update_or_create(
                author=author,
                title=title,
                defaults={
                    "post_type": post_type,
                    "caption": caption,
                    "hashtags": ["#namvibe", "#phase2"],
                    "mentions": [],
                    "audience": Post.Audience.PUBLIC,
                    "share_target": Post.ShareTarget.REELS if post_type == Post.PostType.REEL else Post.ShareTarget.MAIN_FEED,
                    "status": Post.Status.PUBLISHED,
                    "published_at": timezone.now(),
                },
            )

        flyer, _ = Post.objects.update_or_create(
            author=author,
            title="Creator Market Flyer",
            defaults={
                "post_type": Post.PostType.FLYER,
                "caption": "Join the creator market in Windhoek.",
                "hashtags": ["#windhoek", "#creatormarket"],
                "audience": Post.Audience.PUBLIC,
                "share_target": Post.ShareTarget.MAIN_FEED,
                "status": Post.Status.PUBLISHED,
                "published_at": timezone.now(),
            },
        )
        FlyerMeta.objects.update_or_create(
            post=flyer,
            defaults={
                "flyer_title": "Creator Market",
                "body": "Music, fashion, food, art, and local makers.",
                "call_to_action": "Book a stall",
                "background_style": "gradient-violet",
                "text_color": "#ffffff",
                "layout_style": "centered",
            },
        )

        poll_post, _ = Post.objects.update_or_create(
            author=author,
            title="Community poll",
            defaults={
                "post_type": Post.PostType.POLL,
                "caption": "Vote for the next community feature.",
                "hashtags": ["#poll", "#community"],
                "audience": Post.Audience.PUBLIC,
                "share_target": Post.ShareTarget.MAIN_FEED,
                "status": Post.Status.PUBLISHED,
                "published_at": timezone.now(),
            },
        )
        poll, _ = Poll.objects.update_or_create(
            post=poll_post,
            defaults={"question": "What should Namvibe build next?", "multiple_choice": False},
        )
        poll.options.all().delete()
        for index, text in enumerate(["Reels", "Stories", "Communities"]):
            poll.options.create(text=text, sort_order=index)

        live_post, _ = Post.objects.update_or_create(
            author=author,
            title="Friday live announcement",
            defaults={
                "post_type": Post.PostType.LIVE,
                "caption": "Live Q&A for creators.",
                "hashtags": ["#live", "#namvibe"],
                "audience": Post.Audience.COMMUNITY,
                "community": community,
                "share_target": Post.ShareTarget.LIVE,
                "status": Post.Status.PUBLISHED,
                "published_at": timezone.now(),
            },
        )
        LiveAnnouncement.objects.update_or_create(
            post=live_post,
            defaults={
                "stream_title": "Creator Q&A Live",
                "scheduled_for": timezone.now() + timezone.timedelta(days=3),
                "access_type": LiveAnnouncement.AccessType.PUBLIC,
                "ticket_price": 0,
            },
        )

        self.stdout.write(self.style.SUCCESS("Seeded Phase 2 sample posts. Demo password: NamvibeDemo1"))
