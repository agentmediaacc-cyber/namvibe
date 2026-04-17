from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Block
from .models import DatingLike, DatingPass, DatingPreference, DatingProfile, Match
from .services import discovery_queryset_for, like_user, pass_user


class DatingSystemTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(username="viewer_date", password="Pass12345", first_name="Viewer")
        self.alex = User.objects.create_user(username="alex_date", password="Pass12345", first_name="Alex")
        self.mina = User.objects.create_user(username="mina_date", password="Pass12345", first_name="Mina")
        self.hidden = User.objects.create_user(username="hidden_date", password="Pass12345", first_name="Hidden")
        self.viewer_profile = self._profile(self.viewer, "Viewer", "man", visible=True)
        self.alex_profile = self._profile(self.alex, "Alex", "woman", visible=True)
        self.mina_profile = self._profile(self.mina, "Mina", "woman", visible=True)
        self.hidden_profile = self._profile(self.hidden, "Hidden", "woman", visible=False)

    def _profile(self, user, name, gender, visible=True, birth_date=date(1998, 1, 1)):
        profile = DatingProfile.objects.create(
            user=user,
            display_name=name,
            birth_date=birth_date,
            gender=gender,
            looking_for=["woman", "man"],
            bio=f"{name} bio",
            city="Windhoek",
            region="Khomas",
            interests=["music", "coffee"],
            relationship_goal=DatingProfile.RelationshipGoal.DATING,
            is_visible=visible,
        )
        DatingPreference.objects.create(dating_profile=profile, age_min=18, age_max=45, preferred_genders=["woman", "man"])
        return profile

    def test_create_dating_profile(self):
        new_user = User.objects.create_user(username="new_date", password="Pass12345")
        self.client.force_login(new_user)

        response = self.client.post(
            reverse("dating_profile_edit"),
            {
                "display_name": "New Date",
                "birth_date": "1999-02-02",
                "gender": DatingProfile.Gender.WOMAN,
                "looking_for_text": "man,woman",
                "bio": "Ready to meet people",
                "city": "Walvis Bay",
                "region": "Erongo",
                "country": "Namibia",
                "relationship_goal": DatingProfile.RelationshipGoal.SERIOUS,
                "is_visible": "on",
                "show_age": "on",
                "show_distance": "on",
                "interests_text": "travel, food",
                "pref-age_min": "21",
                "pref-age_max": "38",
                "pref-preferred_genders_text": "man",
                "pref-preferred_region": "Erongo",
                "pref-preferred_city": "Walvis Bay",
            },
        )

        profile = DatingProfile.objects.get(user=new_user)
        self.assertRedirects(response, reverse("dating_profile_detail", kwargs={"username": new_user.profile.username}), fetch_redirect_response=False)
        self.assertTrue(profile.is_visible)
        self.assertEqual(profile.interests, ["travel", "food"])

    def test_under_18_profile_blocked_from_visibility(self):
        teen = User.objects.create_user(username="teen_date", password="Pass12345")
        profile = DatingProfile.objects.create(
            user=teen,
            birth_date=date.today().replace(year=date.today().year - 17),
            gender=DatingProfile.Gender.WOMAN,
            is_visible=True,
        )

        profile.refresh_from_db()
        self.assertFalse(profile.is_visible)

    def test_like_creates_match_on_mutual_action(self):
        like_user(self.viewer, self.alex)
        _, match = like_user(self.alex, self.viewer)

        self.assertIsNotNone(match)
        self.assertTrue(Match.objects.filter(user_one=self.viewer, user_two=self.alex, is_active=True).exists())

    def test_pass_removes_person_from_discovery(self):
        pass_user(self.viewer, self.alex)

        profiles = discovery_queryset_for(self.viewer)

        self.assertNotIn(self.alex_profile, profiles)
        self.assertTrue(DatingPass.objects.filter(from_user=self.viewer, to_user=self.alex).exists())

    def test_invisible_profiles_excluded(self):
        profiles = discovery_queryset_for(self.viewer)

        self.assertNotIn(self.hidden_profile, profiles)

    def test_blocked_users_excluded(self):
        Block.objects.create(blocker=self.viewer, blocked=self.alex)

        profiles = discovery_queryset_for(self.viewer)

        self.assertNotIn(self.alex_profile, profiles)

    def test_discovery_page_loads_for_authenticated_user(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("dating_discover"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alex")

    def test_matches_page_shows_mutual_matches(self):
        like_user(self.viewer, self.alex)
        like_user(self.alex, self.viewer)
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("dating_matches"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alex")
