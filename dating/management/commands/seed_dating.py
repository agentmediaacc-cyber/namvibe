from datetime import date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from dating.models import DatingLike, DatingPass, DatingPreference, DatingProfile, Match
from dating.services import like_user, normalize_pair


class Command(BaseCommand):
    help = "Seed demo dating profiles, likes, passes, and matches."

    @transaction.atomic
    def handle(self, *args, **options):
        rows = [
            ("dating_anna", "Anna Iita", "woman", "Windhoek", "Khomas", ["music", "coffee", "reels"]),
            ("dating_josef", "Josef Tjombe", "man", "Swakopmund", "Erongo", ["fitness", "travel", "live music"]),
            ("dating_lina", "Lina Amadhila", "woman", "Oshakati", "Oshana", ["food", "community", "fashion"]),
            ("dating_tangi", "Tangi Kavari", "man", "Rundu", "Kavango East", ["football", "creator events", "photography"]),
        ]
        users = []
        for username, display_name, gender, city, region, interests in rows:
            user, _ = User.objects.get_or_create(username=username, defaults={"email": f"{username}@namvibe.test", "first_name": display_name})
            user.set_password("NamvibeDemo1")
            user.save()
            user.profile.display_name = display_name
            user.profile.location = city
            user.profile.save()
            profile, _ = DatingProfile.objects.update_or_create(
                user=user,
                defaults={
                    "display_name": display_name,
                    "birth_date": date(1997, 5, 12),
                    "gender": gender,
                    "looking_for": ["woman", "man"],
                    "bio": f"{display_name} is meeting new people on Namvibe.",
                    "city": city,
                    "region": region,
                    "interests": interests,
                    "relationship_goal": DatingProfile.RelationshipGoal.DATING,
                    "is_visible": True,
                },
            )
            DatingPreference.objects.get_or_create(dating_profile=profile, defaults={"age_min": 21, "age_max": 40, "preferred_genders": ["woman", "man"]})
            users.append(user)

        like_user(users[0], users[1])
        like_user(users[1], users[0])
        DatingPass.objects.get_or_create(from_user=users[0], to_user=users[2])
        like_user(users[2], users[3])

        self.stdout.write(self.style.SUCCESS("Seeded dating demo data. Demo password: NamvibeDemo1"))
