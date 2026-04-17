from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from live.models import LiveMessage, LiveSession


class Command(BaseCommand):
    help = "Seed demo live creators, sessions, and chat messages."

    @transaction.atomic
    def handle(self, *args, **options):
        hosts = []
        for username, name, location in [
            ("live_mina", "Mina Live", "Windhoek"),
            ("live_coast", "Coast Creator", "Swakopmund"),
            ("live_north", "Northern Voice", "Oshakati"),
        ]:
            user, _ = User.objects.get_or_create(username=username, defaults={"email": f"{username}@namvibe.test", "first_name": name})
            user.set_password("NamvibeDemo1")
            user.save()
            user.profile.display_name = name
            user.profile.location = location
            user.profile.is_creator = True
            user.profile.save()
            hosts.append(user)

        live, _ = LiveSession.objects.update_or_create(
            host=hosts[0],
            title="Windhoek Night Vibes",
            defaults={
                "description": "Music, chat, and creator talk from Windhoek.",
                "status": LiveSession.Status.LIVE,
                "access_type": LiveSession.AccessType.PUBLIC,
                "starts_at": timezone.now(),
                "viewer_count": 42,
                "peak_viewer_count": 67,
                "is_featured": True,
            },
        )
        LiveMessage.objects.get_or_create(session=live, user=hosts[1], body="This live is moving.")
        LiveSession.objects.update_or_create(
            host=hosts[1],
            title="Coastal Creator Session",
            defaults={
                "description": "Upcoming beachside creator hangout.",
                "status": LiveSession.Status.SCHEDULED,
                "access_type": LiveSession.AccessType.PUBLIC,
                "starts_at": timezone.now() + timezone.timedelta(days=1),
                "is_featured": True,
            },
        )
        LiveSession.objects.update_or_create(
            host=hosts[2],
            title="Ended Community Replay",
            defaults={
                "description": "A completed live room.",
                "status": LiveSession.Status.ENDED,
                "access_type": LiveSession.AccessType.PUBLIC,
                "starts_at": timezone.now() - timezone.timedelta(days=1),
                "ends_at": timezone.now() - timezone.timedelta(hours=20),
            },
        )
        self.stdout.write(self.style.SUCCESS("Seeded live demo data. Demo password: NamvibeDemo1"))
