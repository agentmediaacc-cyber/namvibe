from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from dating.models import DatingCoinBalance

from .models import AccountProfile, AccountRole, Follow, Profile
from .services import master_admin_dashboard_url


class AccountAuthFlowTests(TestCase):
    def _signup_payload(self, **overrides):
        payload = {
            "full_name": "Mina Amunyela",
            "country_code": "+264",
            "cellphone_number": "811234567",
            "username": "mina_test",
            "email": "mina@example.com",
            "password": "StrongPass1",
            "confirm_password": "StrongPass1",
        }
        payload.update(overrides)
        return payload

    def test_signup_creates_user_profile_and_redirects(self):
        response = self.client.post(reverse("signup"), self._signup_payload())

        self.assertRedirects(response, reverse("user_dashboard"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username="mina_test", email="mina@example.com").exists())
        self.assertTrue(AccountProfile.objects.filter(cellphone_number="+264811234567").exists())
        self.assertTrue(DatingCoinBalance.objects.filter(user__username="mina_test").exists())
        self.assertEqual(self.client.session["eharo_username"], "mina_test")

    @patch("accounts.views.send_verification_email", side_effect=RuntimeError("smtp down"))
    def test_signup_survives_verification_email_failure(self, _send_verification):
        response = self.client.post(reverse("signup"), self._signup_payload(username="mina_mail", email="mina_mail@example.com"))

        self.assertRedirects(response, reverse("user_dashboard"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username="mina_mail").exists())

    def test_signup_rejects_duplicate_email_username_and_cellphone(self):
        self.client.post(reverse("signup"), self._signup_payload())
        self.client.logout()

        response = self.client.post(reverse("signup"), self._signup_payload())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This username is already taken.")
        self.assertContains(response, "An account with this email already exists.")
        self.assertContains(response, "An account with this cellphone number already exists.")

    def test_login_accepts_username_or_email(self):
        self.client.post(reverse("signup"), self._signup_payload())
        self.client.logout()

        username_response = self.client.post(reverse("login"), {
            "identifier": "mina_test",
            "password": "StrongPass1",
        })
        self.assertRedirects(username_response, reverse("user_dashboard"), fetch_redirect_response=False)

        self.client.logout()
        email_response = self.client.post(reverse("login"), {
            "identifier": "mina@example.com",
            "password": "StrongPass1",
        })
        self.assertRedirects(email_response, reverse("user_dashboard"), fetch_redirect_response=False)

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(reverse("login"), {
            "identifier": "missing@example.com",
            "password": "WrongPass1",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Account not recognized.")

    def test_login_rejects_wrong_password(self):
        self.client.post(reverse("signup"), self._signup_payload())
        self.client.logout()

        response = self.client.post(reverse("login"), {
            "identifier": "mina@example.com",
            "password": "WrongPass1",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Incorrect password.")

    def test_login_redirects_authenticated_user_to_dashboard(self):
        self.client.post(reverse("signup"), self._signup_payload())

        response = self.client.get(reverse("login"))

        self.assertRedirects(response, reverse("user_dashboard"), fetch_redirect_response=False)

    def test_signup_redirects_authenticated_user_to_dashboard(self):
        self.client.post(reverse("signup"), self._signup_payload())

        response = self.client.get(reverse("signup"))

        self.assertRedirects(response, reverse("user_dashboard"), fetch_redirect_response=False)

    def test_profile_link_for_logged_out_user_points_to_login_with_dashboard_next(self):
        response = self.client.get(reverse("home"))

        expected_url = f"{reverse('login')}?next=%2Faccounts%2Fdashboard%2F"
        self.assertContains(response, f'href="{expected_url}"')
        self.assertNotContains(response, "data-dashboard-section")

    def test_profile_link_for_logged_in_user_points_to_dashboard(self):
        self.client.post(reverse("signup"), self._signup_payload())

        response = self.client.get(reverse("home"))

        self.assertContains(response, f'href="{reverse("profile_detail", kwargs={"username": "mina_test"})}"')
        self.assertContains(response, f'href="{reverse("logout")}"')
        self.assertNotContains(response, f'href="{reverse("login")}" class="action-btn auth-action"')
        self.assertNotContains(response, f'href="{reverse("signup")}" class="action-btn action-primary"')

    @patch("accounts.views.get_posts_by_user", return_value=[])
    def test_dashboard_menu_uses_dashboard_sections_only(self, _posts):
        self.client.post(reverse("signup"), self._signup_payload())

        response = self.client.get(reverse("user_dashboard"))

        self.assertContains(response, "Profile Overview")
        self.assertContains(response, "Gallery")
        self.assertContains(response, "Messages")
        self.assertContains(response, "Settings")
        self.assertNotContains(response, 'data-section="anonymous"')

    def test_login_next_redirects_to_dashboard_after_profile_click(self):
        self.client.post(reverse("signup"), self._signup_payload())
        self.client.logout()

        response = self.client.post(
            f"{reverse('login')}?next={reverse('user_dashboard')}",
            {
                "identifier": "mina_test",
                "password": "StrongPass1",
            },
        )

        self.assertRedirects(response, reverse("user_dashboard"), fetch_redirect_response=False)

    def test_login_repairs_missing_account_profile_and_coin_balance(self):
        user = User.objects.create_user(username="legacymina", email="legacy@example.com", password="StrongPass1")
        DatingCoinBalance.objects.filter(user=user).delete()
        AccountProfile.objects.filter(user=user).delete()
        self.assertFalse(AccountProfile.objects.filter(user=user).exists())
        self.assertFalse(DatingCoinBalance.objects.filter(user=user).exists())

        response = self.client.post(
            reverse("login"),
            {"identifier": "legacymina", "password": "StrongPass1"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(AccountProfile.objects.filter(user=user).exists())
        self.assertTrue(DatingCoinBalance.objects.filter(user=user).exists())

    def test_dashboard_redirects_logged_out_user_to_login_with_next(self):
        response = self.client.get(reverse("user_dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next=%2Faccounts%2Fdashboard%2F",
            fetch_redirect_response=False,
        )

    def test_logout_clears_session_and_returns_to_login(self):
        self.client.post(reverse("signup"), self._signup_payload())

        response = self.client.get(reverse("logout"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("eharo_user_id", self.client.session)

    def test_public_profile_does_not_expose_private_identity_fields(self):
        self.client.post(reverse("signup"), self._signup_payload())
        response = self.client.get(reverse("profile_detail", kwargs={"username": "mina_test"}))

        self.assertContains(response, "@mina_test")
        self.assertNotContains(response, "mina@example.com")
        self.assertNotContains(response, "+264811234567")


class SocialGraphTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mina", password="StrongPass1")
        self.creator = User.objects.create_user(username="tangi", password="StrongPass1")

    def test_user_creation_creates_creator_profile_shell(self):
        self.assertTrue(Profile.objects.filter(user=self.user, username="mina").exists())

    def test_follow_toggle_creates_and_removes_follow_with_counts(self):
        self.client.force_login(self.user)

        first_response = self.client.post(reverse("follow_toggle", kwargs={"username": self.creator.profile.username}))
        self.user.profile.refresh_from_db()
        self.creator.profile.refresh_from_db()

        self.assertRedirects(first_response, reverse("profile_detail", kwargs={"username": "tangi"}), fetch_redirect_response=False)
        self.assertTrue(Follow.objects.filter(follower=self.user, following=self.creator).exists())
        self.assertEqual(self.user.profile.following_count, 1)
        self.assertEqual(self.creator.profile.follower_count, 1)

        second_response = self.client.post(reverse("follow_toggle", kwargs={"username": self.creator.profile.username}))
        self.user.profile.refresh_from_db()
        self.creator.profile.refresh_from_db()

        self.assertRedirects(second_response, reverse("profile_detail", kwargs={"username": "tangi"}), fetch_redirect_response=False)
        self.assertFalse(Follow.objects.filter(follower=self.user, following=self.creator).exists())
        self.assertEqual(self.user.profile.following_count, 0)
        self.assertEqual(self.creator.profile.follower_count, 0)


class MasterAdminFlowTests(TestCase):
    def setUp(self):
        self.master_user = User.objects.create_user(
            username="kasera",
            email="kasera@namvibe.com",
            password="StrongPass1",
        )
        AccountProfile.objects.create(
            user=self.master_user,
            full_name="Kasera Namvibe",
            email="kasera@namvibe.com",
            phone_country_code="+264",
            cellphone_number="+264811111111",
            residential_address="",
            country_of_origin="Namibia",
            current_country="Namibia",
        )

    def test_master_admin_login_redirects_to_control_center(self):
        response = self.client.post(
            reverse("login"),
            {"identifier": "kasera@namvibe.com", "password": "StrongPass1"},
        )

        self.assertRedirects(response, master_admin_dashboard_url(), fetch_redirect_response=False)
        self.master_user.refresh_from_db()
        self.assertEqual(self.master_user.account_role.role, AccountRole.Role.MASTER_ADMIN)

    def test_master_admin_dashboard_route_redirects_to_control_center(self):
        self.client.force_login(self.master_user)

        response = self.client.get(reverse("user_dashboard"))

        self.assertRedirects(response, master_admin_dashboard_url(), fetch_redirect_response=False)

    def test_master_admin_signup_route_redirects_to_control_center_when_authenticated(self):
        self.client.force_login(self.master_user)

        response = self.client.get(reverse("signup"))

        self.assertRedirects(response, master_admin_dashboard_url(), fetch_redirect_response=False)

    def test_diagnose_master_admin_command_reports_resolution(self):
        self.master_user.account_role.supabase_uid = "2319f827-fc3c-46ce-9239-b350312a0d6f"
        self.master_user.account_role.save(update_fields=["supabase_uid", "updated_at"])
        stream = StringIO()

        call_command("diagnose_master_admin", stdout=stream)

        output = stream.getvalue()
        self.assertIn("Configured master admin", output)
        self.assertIn("kasera@namvibe.com", output)
        self.assertIn("canonical local target", output.lower())
        self.assertIn("Repair needed", output)
