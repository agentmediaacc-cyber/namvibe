from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from dating.models import DatingCoinBalance

from .forms import ProfileForm
from .models import AccountProfile, AccountRole, Follow, Notification, Profile
from .services import account_rank_for_value, is_valid_uuid, master_admin_dashboard_url


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
        self.assertNotContains(response, "© 2026 Namvibe")

    @patch("accounts.views.get_posts_by_user", return_value=[])
    @patch("accounts.views.get_supabase_profile", return_value=None)
    @patch("accounts.views._safe_sync_supabase_profile", return_value=None)
    def test_dashboard_skips_invalid_session_uuid_for_supabase_posts(self, _sync, _profile, get_posts_mock):
        self.client.post(reverse("signup"), self._signup_payload(username="uuidcheck", email="uuidcheck@example.com"))
        session = self.client.session
        session["eharo_user_id"] = "15"
        session.save()

        response = self.client.get(reverse("user_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(get_posts_mock.call_count, 1)
        requested_ids = [call.args[0] for call in get_posts_mock.call_args_list if call.args]
        self.assertNotIn("15", requested_ids)
        self.assertTrue(all(is_valid_uuid(value) for value in requested_ids))

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

    def test_rank_helper_defaults_to_namvibe(self):
        rank = account_rank_for_value(0)

        self.assertEqual(rank["label"], "Namvibe")
        self.assertEqual(rank["tone"], "namvibe")

    def test_profile_settings_route_renders(self):
        self.client.post(reverse("signup"), self._signup_payload(username="settings_user", email="settings@example.com"))

        response = self.client.get(reverse("account_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profile Settings")
        self.assertContains(response, "Choose from gallery")
        self.assertNotContains(response, "Take photo")
        self.assertNotContains(response, "Keep this page short on mobile")
        self.assertNotContains(response, 'capture="user"')

    def test_model_application_route_renders(self):
        self.client.post(reverse("signup"), self._signup_payload(username="model_user", email="model@example.com"))

        response = self.client.get(reverse("account_model_application"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Model / Streamer Application")

    def test_gallery_route_renders(self):
        self.client.post(reverse("signup"), self._signup_payload(username="gallery_user", email="gallery@example.com"))

        response = self.client.get(reverse("profile_gallery"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gallery / Album")

    def test_root_dashboard_alias_redirects_to_account_dashboard(self):
        self.client.post(reverse("signup"), self._signup_payload(username="alias_user", email="alias@example.com"))

        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(response, reverse("user_dashboard"), fetch_redirect_response=False)

    def test_root_profile_alias_redirects_to_account_dashboard(self):
        self.client.post(reverse("signup"), self._signup_payload(username="profile_alias", email="profile_alias@example.com"))

        response = self.client.get(reverse("profile_root"))

        self.assertRedirects(response, reverse("user_dashboard"), fetch_redirect_response=False)

    def test_root_profile_upload_photo_alias_redirects_to_picture_tab(self):
        self.client.post(reverse("signup"), self._signup_payload(username="picture_alias", email="picture_alias@example.com"))

        response = self.client.get(reverse("profile_upload_photo"))

        self.assertRedirects(response, f"{reverse('profile_edit')}?tab=picture", fetch_redirect_response=False)

    def test_messages_home_route_renders(self):
        self.client.post(reverse("signup"), self._signup_payload(username="messages_user", email="messages@example.com"))

        response = self.client.get(reverse("messages_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Messages")

    def test_stories_home_route_renders(self):
        self.client.post(reverse("signup"), self._signup_payload(username="stories_user", email="stories@example.com"))

        response = self.client.get(reverse("stories_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stories")

    def test_member_discovery_route_renders(self):
        self.client.post(reverse("signup"), self._signup_payload(username="members_user", email="members@example.com"))

        response = self.client.get(reverse("member_discovery"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Members to discover")

    def test_friend_request_send_and_accept_flow(self):
        self.client.post(
            reverse("signup"),
            self._signup_payload(username="sender_user", email="sender@example.com", cellphone_number="811234568"),
        )
        self.client.logout()
        self.client.post(
            reverse("signup"),
            self._signup_payload(username="receiver_user", email="receiver@example.com", cellphone_number="811234569"),
        )
        receiver = User.objects.get(username="receiver_user")
        self.client.logout()
        self.client.post(reverse("login"), {"identifier": "sender_user", "password": "StrongPass1"})

        send_response = self.client.post(reverse("friend_request_send", kwargs={"username": receiver.profile.username}))

        self.assertEqual(send_response.status_code, 302)
        request_obj = receiver.received_friend_requests.get(from_user__username="sender_user")
        self.assertEqual(request_obj.status, "pending")

        self.client.logout()
        self.client.post(reverse("login"), {"identifier": "receiver_user", "password": "StrongPass1"})
        accept_response = self.client.post(reverse("friend_request_accept", kwargs={"request_id": request_obj.id}))
        request_obj.refresh_from_db()

        self.assertEqual(accept_response.status_code, 302)
        self.assertEqual(request_obj.status, "accepted")

    def test_profile_form_rejects_large_avatar_upload(self):
        user = User.objects.create_user(username="uploadcheck", email="uploadcheck@example.com", password="StrongPass1")
        profile = user.profile
        form = ProfileForm(instance=profile)
        form.cleaned_data = {
            "avatar": SimpleNamespace(
                name="avatar.jpg",
                size=ProfileForm.AVATAR_MAX_BYTES + 1,
                content_type="image/jpeg",
            )
        }

        with self.assertRaisesMessage(ValidationError, "Image is too large. Keep it under 5MB."):
            form.clean_avatar()

    def test_profile_form_rejects_invalid_cover_type(self):
        user = User.objects.create_user(username="covercheck", email="covercheck@example.com", password="StrongPass1")
        profile = user.profile
        form = ProfileForm(instance=profile)
        form.cleaned_data = {
            "cover_image": SimpleNamespace(
                name="cover.gif",
                size=1024,
                content_type="image/gif",
            )
        }

        with self.assertRaisesMessage(ValidationError, "Use a JPG, PNG, or WEBP image."):
            form.clean_cover_image()


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

    def test_follow_toggle_creates_notification_for_followed_user(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("follow_toggle", kwargs={"username": self.creator.profile.username}))

        self.assertEqual(response.status_code, 302)
        notification = Notification.objects.filter(recipient=self.creator, sender=self.user).latest("created_at")
        self.assertEqual(notification.notification_type, Notification.Type.FOLLOW)


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
