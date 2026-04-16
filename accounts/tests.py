from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from .models import AccountProfile


class AccountAuthFlowTests(TestCase):
    def _signup_payload(self, **overrides):
        payload = {
            "full_name": "Mina Amunyela",
            "username": "mina_test",
            "email": "mina@example.com",
            "cellphone_number": "+264811234567",
            "residential_address": "12 Independence Avenue, Windhoek",
            "country_of_origin": "Namibia",
            "current_country": "Namibia",
            "password": "StrongPass1",
            "confirm_password": "StrongPass1",
        }
        payload.update(overrides)
        return payload

    def test_signup_creates_user_profile_and_redirects(self):
        response = self.client.post(reverse("signup"), self._signup_payload())

        self.assertRedirects(response, reverse("profile_completion"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username="mina_test", email="mina@example.com").exists())
        self.assertTrue(AccountProfile.objects.filter(cellphone_number="+264811234567").exists())
        self.assertEqual(self.client.session["eharo_username"], "mina_test")

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
        self.assertContains(response, "Invalid email, username, or password.")

    def test_login_redirects_authenticated_user_to_dashboard(self):
        self.client.post(reverse("signup"), self._signup_payload())

        response = self.client.get(reverse("login"))

        self.assertRedirects(response, reverse("user_dashboard"), fetch_redirect_response=False)

    def test_signup_redirects_authenticated_user_to_dashboard(self):
        self.client.post(reverse("signup"), self._signup_payload())

        response = self.client.get(reverse("signup"))

        self.assertRedirects(response, reverse("user_dashboard"), fetch_redirect_response=False)

    @patch("core.views.count_public_posts", return_value=0)
    @patch("core.views.get_public_posts", return_value=[])
    def test_profile_link_for_logged_out_user_points_to_login_with_dashboard_next(self, _posts, _count):
        response = self.client.get(reverse("home"))

        expected_url = f"{reverse('login')}?next=%2Faccounts%2Fdashboard%2F"
        self.assertContains(response, f'href="{expected_url}"')
        self.assertContains(response, 'data-section="gallery"')
        self.assertContains(response, '<aside class="rightbar contextual-extra" id="rightbar" hidden>')
        self.assertNotContains(response, "data-dashboard-section")

    @patch("core.views.count_public_posts", return_value=0)
    @patch("core.views.get_public_posts", return_value=[])
    def test_profile_link_for_logged_in_user_points_to_dashboard(self, _posts, _count):
        self.client.post(reverse("signup"), self._signup_payload())

        response = self.client.get(reverse("home"))

        self.assertContains(response, f'href="{reverse("user_dashboard")}"')
        self.assertContains(response, f'href="{reverse("logout")}"')
        self.assertNotContains(response, f'href="{reverse("login")}" class="action-btn auth-action"')
        self.assertNotContains(response, f'href="{reverse("signup")}" class="action-btn action-primary"')

    @patch("accounts.views.get_posts_by_user", return_value=[])
    def test_dashboard_menu_uses_dashboard_sections_only(self, _posts):
        self.client.post(reverse("signup"), self._signup_payload())

        response = self.client.get(reverse("user_dashboard"))

        self.assertContains(response, 'data-dashboard-section="profile"')
        self.assertContains(response, 'data-dashboard-section="posts"')
        self.assertContains(response, 'data-dashboard-section="settings"')
        self.assertNotContains(response, 'data-section="gallery"')
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
