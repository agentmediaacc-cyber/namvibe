from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Block
from .models import DatingCoinBalance, DatingLike, DatingPass, DatingPreference, DatingProfile, Match
from .services import (
    BOOST_COST_COINS,
    SUPER_LIKE_COST_COINS,
    coin_balance_for,
    discovery_queryset_for,
    like_user,
    likes_used_today,
    pass_user,
)


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
            reverse("dating"),
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
        self.assertRedirects(response, reverse("dating"), fetch_redirect_response=False)
        self.assertTrue(profile.is_visible)
        self.assertEqual(profile.interests, ["travel", "food"])

    def test_dating_home_loads_for_anonymous_user(self):
        response = self.client.get(reverse("dating"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dating on Namvibe")

    def test_dating_profile_alias_loads_for_authenticated_user(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("dating_profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Namvibe Dating")

    def test_new_users_get_zero_coin_balance(self):
        balance = DatingCoinBalance.objects.get(user=self.viewer)
        self.assertEqual(balance.balance, 0)

    def test_coin_balance_is_recreated_when_missing(self):
        DatingCoinBalance.objects.filter(user=self.viewer).delete()

        balance = coin_balance_for(self.viewer)

        self.assertEqual(balance.balance, 0)
        self.assertTrue(DatingCoinBalance.objects.filter(user=self.viewer).exists())

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
        self.assertContains(response, self.alex.profile.display_name)

    def test_message_match_without_username_redirects_to_matches(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("dating_message_match"))

        self.assertRedirects(response, reverse("dating_matches"), fetch_redirect_response=False)

    def test_message_match_redirects_to_dashboard_conversation_for_match(self):
        like_user(self.viewer, self.alex)
        like_user(self.alex, self.viewer)
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("dating_message_match", kwargs={"username": self.alex.profile.username}))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("user_dashboard"), response["Location"])

    def test_send_message_creates_message_for_match(self):
        like_user(self.viewer, self.alex)
        like_user(self.alex, self.viewer)
        self.client.force_login(self.viewer)

        response = self.client.post(
            reverse("dating_send_message", kwargs={"username": self.alex.profile.username}),
            {"text": "Hello there"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.viewer.sent_messages.filter(text="Hello there").exists())

    def test_free_tier_has_daily_like_limit(self):
        self.viewer_profile.premium_tier = DatingProfile.PremiumTier.FREE
        self.viewer_profile.save(update_fields=["premium_tier"])
        extra_users = []
        for idx in range(25):
            user = User.objects.create_user(username=f"free_like_{idx}", password="Pass12345")
            extra_users.append(user)
            self._profile(user, f"Free {idx}", "woman", visible=True)
            like, _match = like_user(self.viewer, user)
            self.assertIsNotNone(like)

        blocked_user = User.objects.create_user(username="free_like_blocked", password="Pass12345")
        self._profile(blocked_user, "Blocked", "woman", visible=True)
        like, _match = like_user(self.viewer, blocked_user)
        self.assertIsNone(like)

    def test_daily_like_limit_resets_on_new_local_day(self):
        self.viewer_profile.premium_tier = DatingProfile.PremiumTier.FREE
        self.viewer_profile.save(update_fields=["premium_tier"])

        yesterday = timezone.now() - timedelta(days=1)
        for idx in range(25):
            user = User.objects.create_user(username=f"yesterday_like_{idx}", password="Pass12345")
            self._profile(user, f"Yesterday {idx}", "woman", visible=True)
            like, _match = like_user(self.viewer, user)
            self.assertIsNotNone(like)
            DatingLike.objects.filter(pk=like.pk).update(created_at=yesterday)

        self.assertEqual(likes_used_today(self.viewer), 0)

        today_user = User.objects.create_user(username="today_like_reset", password="Pass12345")
        self._profile(today_user, "Today Reset", "woman", visible=True)
        like, _match = like_user(self.viewer, today_user)
        self.assertIsNotNone(like)

    def test_gold_tier_has_unlimited_likes(self):
        self.viewer_profile.premium_tier = DatingProfile.PremiumTier.GOLD
        self.viewer_profile.save(update_fields=["premium_tier"])
        for idx in range(30):
            user = User.objects.create_user(username=f"gold_like_{idx}", password="Pass12345")
            self._profile(user, f"Gold {idx}", "woman", visible=True)
            like, _match = like_user(self.viewer, user)
            self.assertIsNotNone(like)

    def test_silver_tier_has_higher_daily_like_limit(self):
        self.viewer_profile.premium_tier = DatingProfile.PremiumTier.SILVER
        self.viewer_profile.save(update_fields=["premium_tier"])
        for idx in range(100):
            user = User.objects.create_user(username=f"silver_like_{idx}", password="Pass12345")
            self._profile(user, f"Silver {idx}", "woman", visible=True)
            like, _match = like_user(self.viewer, user)
            self.assertIsNotNone(like)

        blocked_user = User.objects.create_user(username="silver_like_blocked", password="Pass12345")
        self._profile(blocked_user, "Blocked Silver", "woman", visible=True)
        like, _match = like_user(self.viewer, blocked_user)
        self.assertIsNone(like)

    def test_vip_tier_has_unlimited_likes(self):
        self.viewer_profile.premium_tier = DatingProfile.PremiumTier.VIP
        self.viewer_profile.save(update_fields=["premium_tier"])
        for idx in range(40):
            user = User.objects.create_user(username=f"vip_like_{idx}", password="Pass12345")
            self._profile(user, f"VIP {idx}", "woman", visible=True)
            like, _match = like_user(self.viewer, user)
            self.assertIsNotNone(like)

    def test_boost_costs_coins_and_sets_boosted_at(self):
        self.client.force_login(self.viewer)
        balance = DatingCoinBalance.objects.get(user=self.viewer)
        balance.balance = BOOST_COST_COINS
        balance.save(update_fields=["balance"])

        response = self.client.post(reverse("dating_boost"))

        self.assertRedirects(response, reverse("dating"), fetch_redirect_response=False)
        self.viewer_profile.refresh_from_db()
        balance.refresh_from_db()
        self.assertIsNotNone(self.viewer_profile.boosted_at)
        self.assertEqual(balance.balance, 0)

    def test_boost_respects_existing_cooldown_without_deducting(self):
        self.client.force_login(self.viewer)
        self.viewer_profile.boosted_at = timezone.now()
        self.viewer_profile.save(update_fields=["boosted_at"])
        balance = DatingCoinBalance.objects.get(user=self.viewer)
        balance.balance = BOOST_COST_COINS
        balance.save(update_fields=["balance"])

        self.client.post(reverse("dating_boost"))

        balance.refresh_from_db()
        self.assertEqual(balance.balance, BOOST_COST_COINS)

    def test_super_like_costs_coins_and_marks_like(self):
        self.client.force_login(self.viewer)
        balance = DatingCoinBalance.objects.get(user=self.viewer)
        balance.balance = SUPER_LIKE_COST_COINS
        balance.save(update_fields=["balance"])

        response = self.client.post(reverse("dating_super_like", kwargs={"username": self.alex.profile.username}))

        self.assertRedirects(response, reverse("dating_discover"), fetch_redirect_response=False)
        like = DatingLike.objects.get(from_user=self.viewer, to_user=self.alex)
        balance.refresh_from_db()
        self.assertTrue(like.is_super_like)
        self.assertEqual(balance.balance, 0)

    def test_super_like_ajax_rejects_duplicate_charge(self):
        self.client.force_login(self.viewer)
        balance = DatingCoinBalance.objects.get(user=self.viewer)
        balance.balance = SUPER_LIKE_COST_COINS * 2
        balance.save(update_fields=["balance"])
        DatingLike.objects.create(from_user=self.viewer, to_user=self.alex, is_super_like=True)

        response = self.client.post(
            reverse("dating_super_like", kwargs={"username": self.alex.profile.username}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        balance.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(balance.balance, SUPER_LIKE_COST_COINS * 2)

    def test_duplicate_super_like_does_not_require_new_balance_or_charge_again(self):
        self.client.force_login(self.viewer)
        DatingLike.objects.create(from_user=self.viewer, to_user=self.alex, is_super_like=True)
        balance = DatingCoinBalance.objects.get(user=self.viewer)
        balance.balance = 0
        balance.save(update_fields=["balance"])

        response = self.client.post(reverse("dating_super_like", kwargs={"username": self.alex.profile.username}))

        balance.refresh_from_db()
        self.assertRedirects(response, reverse("dating_discover"), fetch_redirect_response=False)
        self.assertEqual(balance.balance, 0)

    def test_ajax_like_returns_json_when_limit_is_reached(self):
        self.client.force_login(self.viewer)
        self.viewer_profile.premium_tier = DatingProfile.PremiumTier.FREE
        self.viewer_profile.save(update_fields=["premium_tier"])

        for idx in range(25):
            user = User.objects.create_user(username=f"ajax_like_limit_{idx}", password="Pass12345")
            self._profile(user, f"Ajax Limit {idx}", "woman", visible=True)
            like, _match = like_user(self.viewer, user)
            self.assertIsNotNone(like)

        blocked_user = User.objects.create_user(username="ajax_like_limit_blocked", password="Pass12345")
        self._profile(blocked_user, "Ajax Blocked", "woman", visible=True)

        response = self.client.post(
            reverse("dating_like", kwargs={"username": blocked_user.profile.username}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"ok": False, "error": "Daily like limit reached for your current tier."})

    def test_ajax_pass_returns_json_successfully(self):
        self.client.force_login(self.viewer)

        response = self.client.post(
            reverse("dating_pass", kwargs={"username": self.alex.profile.username}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"ok": True})

    def test_ajax_super_like_returns_json_when_insufficient_coins(self):
        self.client.force_login(self.viewer)
        balance = DatingCoinBalance.objects.get(user=self.viewer)
        balance.balance = 0
        balance.save(update_fields=["balance"])

        response = self.client.post(
            reverse("dating_super_like", kwargs={"username": self.alex.profile.username}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content,
            {"ok": False, "error": f"You need {SUPER_LIKE_COST_COINS} coins to send a Super Like."},
        )
