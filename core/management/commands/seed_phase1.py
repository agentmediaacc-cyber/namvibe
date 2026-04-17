from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import AccountProfile, Follow
from communities.models import Community, CommunityMembership


class Command(BaseCommand):
    help = "Seed Phase 1 demo users, follows, and communities."

    @transaction.atomic
    def handle(self, *args, **options):
        demo_users = [
            {
                "username": "nam_creator",
                "email": "creator@namvibe.test",
                "full_name": "Tangi Shikongo",
                "location": "Windhoek",
                "bio": "Creator sharing fashion, music, and city moments.",
                "is_creator": True,
            },
            {
                "username": "coast_vibes",
                "email": "coast@namvibe.test",
                "full_name": "Lina Nghipandulwa",
                "location": "Swakopmund",
                "bio": "Coastal events, food spots, and sunset reels.",
                "is_creator": True,
            },
            {
                "username": "north_pulse",
                "email": "north@namvibe.test",
                "full_name": "Penda Amutenya",
                "location": "Oshakati",
                "bio": "Community stories from northern Namibia.",
                "is_creator": False,
            },
        ]

        users = {}
        for item in demo_users:
            user, _ = User.objects.get_or_create(
                username=item["username"],
                defaults={"email": item["email"], "first_name": item["full_name"]},
            )
            user.email = item["email"]
            user.first_name = item["full_name"]
            user.set_password("NamvibeDemo1")
            user.save()
            AccountProfile.objects.get_or_create(
                user=user,
                defaults={
                    "full_name": item["full_name"],
                    "email": item["email"],
                    "cellphone_number": f"+26481{user.id:06d}",
                    "residential_address": "Demo address, Namibia",
                    "country_of_origin": "Namibia",
                    "current_country": "Namibia",
                    "profile_completed": True,
                },
            )
            profile = user.profile
            profile.display_name = item["full_name"]
            profile.username = item["username"]
            profile.location = item["location"]
            profile.bio = item["bio"]
            profile.is_creator = item["is_creator"]
            profile.save()
            users[item["username"]] = user

        Follow.objects.get_or_create(follower=users["north_pulse"], following=users["nam_creator"])
        Follow.objects.get_or_create(follower=users["coast_vibes"], following=users["nam_creator"])
        Follow.objects.get_or_create(follower=users["nam_creator"], following=users["coast_vibes"])

        communities = [
            ("Windhoek Creators", "windhoek-creators", "A home for creators, photographers, hosts, and small brands in Windhoek.", users["nam_creator"]),
            ("Coastal Events", "coastal-events", "Swakopmund and Walvis Bay happenings, flyers, and weekend plans.", users["coast_vibes"]),
            ("Northern Voices", "northern-voices", "Stories, businesses, and community updates from northern Namibia.", users["north_pulse"]),
        ]
        for name, slug, description, owner in communities:
            community, _ = Community.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": description,
                    "owner": owner,
                },
            )
            community.name = name
            community.description = description
            community.owner = owner
            community.save()
            CommunityMembership.objects.get_or_create(
                community=community,
                user=owner,
                defaults={"role": CommunityMembership.Role.OWNER, "status": CommunityMembership.Status.ACTIVE},
            )
            community.member_count = CommunityMembership.objects.filter(
                community=community,
                status=CommunityMembership.Status.ACTIVE,
            ).count()
            community.save(update_fields=["member_count"])

        self.stdout.write(self.style.SUCCESS("Seeded Phase 1 demo data. Demo password: NamvibeDemo1"))
