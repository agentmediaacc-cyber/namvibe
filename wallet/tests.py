from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Notification
from live.models import LiveAccessPurchase, LiveSession
from live.services import can_access_session
from posts.models import Post
from stories.models import StoryItem

from .models import BoostCampaign, CreatorEntitlement, GiftCatalog, GiftEvent, MembershipPlan, UserMembership, WalletAccount, WalletTransaction
from .services import (
    DAILY_CHECKIN_REFERENCE_PREFIX,
    InsufficientFunds,
    WalletError,
    active_boosts_qs,
    assign_membership_by_staff,
    claim_daily_checkin,
    create_boost,
    credit_wallet,
    daily_checkin_status,
    debit_wallet,
    premium_badge_for,
    purchase_membership,
    send_gift,
)


class WalletPhaseFiveTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username="creator5", password="Pass12345")
        self.viewer = User.objects.create_user(username="viewer5", password="Pass12345")
        self.staff = User.objects.create_user(username="staffwallet", password="Pass12345", is_staff=True)
        self.plan = MembershipPlan.objects.create(
            name="Premium",
            slug="premium",
            price=Decimal("50.00"),
            billing_period=MembershipPlan.BillingPeriod.MONTHLY,
            feature_flags={"premium_badge": True, "premium_live_access": True},
        )
        self.gift = GiftCatalog.objects.create(name="Spark", slug="spark", coin_cost=Decimal("10.00"), value_to_creator=Decimal("8.00"))

    def test_wallet_auto_created_for_user(self):
        self.assertTrue(WalletAccount.objects.filter(user=self.creator).exists())

    def test_debit_fails_on_insufficient_funds(self):
        with self.assertRaises(InsufficientFunds):
            debit_wallet(self.viewer, Decimal("1.00"))

    def test_membership_purchase_creates_membership_and_transaction(self):
        credit_wallet(self.viewer, Decimal("75.00"), WalletTransaction.Type.DEPOSIT)
        membership, transaction = purchase_membership(self.viewer, self.plan)
        self.viewer.wallet.refresh_from_db()
        self.assertEqual(membership.status, UserMembership.Status.ACTIVE)
        self.assertEqual(transaction.transaction_type, WalletTransaction.Type.PREMIUM_MEMBERSHIP_PURCHASE)
        self.assertEqual(self.viewer.wallet.available_balance, Decimal("25.00"))

    def test_premium_live_access_denied_without_entitlement(self):
        session = LiveSession.objects.create(host=self.creator, title="Premium Room", status=LiveSession.Status.LIVE, access_type=LiveSession.AccessType.PREMIUM)
        self.assertFalse(can_access_session(self.viewer, session))

    def test_premium_live_access_granted_after_purchase_endpoint(self):
        session = LiveSession.objects.create(host=self.creator, title="Premium Room", status=LiveSession.Status.LIVE, access_type=LiveSession.AccessType.PREMIUM)
        credit_wallet(self.viewer, Decimal("40.00"), WalletTransaction.Type.DEPOSIT)
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("live_purchase_access", kwargs={"uuid": session.uuid}))
        self.assertRedirects(response, reverse("live_room", kwargs={"uuid": session.uuid}), fetch_redirect_response=False)
        self.assertTrue(CreatorEntitlement.objects.filter(buyer=self.viewer, live_session=session, active=True).exists())
        self.assertTrue(LiveAccessPurchase.objects.filter(user=self.viewer, session=session, is_active=True).exists())
        self.assertTrue(can_access_session(self.viewer, session))

    def test_gift_sending_debits_sender_and_credits_creator(self):
        credit_wallet(self.viewer, Decimal("30.00"), WalletTransaction.Type.DEPOSIT)
        event, _ = send_gift(self.viewer, self.creator, self.gift, 2)
        self.viewer.wallet.refresh_from_db()
        self.creator.wallet.refresh_from_db()
        self.assertEqual(event.total_cost, Decimal("20.00"))
        self.assertEqual(event.creator_value, Decimal("16.00"))
        self.assertEqual(self.viewer.wallet.available_balance, Decimal("10.00"))
        self.assertEqual(self.creator.wallet.pending_balance, Decimal("16.00"))

    def test_gift_creates_notification_for_recipient(self):
        credit_wallet(self.viewer, Decimal("20.00"), WalletTransaction.Type.DEPOSIT)

        send_gift(self.viewer, self.creator, self.gift, 1)

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.creator,
                sender=self.viewer,
                message__icontains="sent you",
            ).exists()
        )

    def test_cannot_gift_self(self):
        credit_wallet(self.creator, Decimal("20.00"), WalletTransaction.Type.DEPOSIT)

        with self.assertRaises(WalletError):
            send_gift(self.creator, self.creator, self.gift, 1)

    def test_live_gift_endpoint_records_event(self):
        session = LiveSession.objects.create(host=self.creator, title="Gift Room", status=LiveSession.Status.LIVE)
        credit_wallet(self.viewer, Decimal("20.00"), WalletTransaction.Type.DEPOSIT)
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("live_gift", kwargs={"uuid": session.uuid}), {"gift": self.gift.slug, "quantity": 1})
        self.assertRedirects(response, reverse("live_room", kwargs={"uuid": session.uuid}), fetch_redirect_response=False)
        self.assertTrue(GiftEvent.objects.filter(sender=self.viewer, recipient=self.creator, live_session=session).exists())

    def test_wallet_history_page_loads(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("wallet_transactions"))
        self.assertEqual(response.status_code, 200)

    def test_creator_earnings_page_loads_for_creator(self):
        self.client.force_login(self.creator)
        response = self.client.get(reverse("wallet_creator_earnings"))
        self.assertEqual(response.status_code, 200)

    def test_boost_purchase_creates_campaign_and_expires(self):
        post = Post.objects.create(
            author=self.creator,
            title="Boost me",
            audience=Post.Audience.PUBLIC,
            status=Post.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        credit_wallet(self.creator, Decimal("50.00"), WalletTransaction.Type.DEPOSIT)

        campaign = create_boost(self.creator, post=post)

        self.creator.wallet.refresh_from_db()
        self.assertTrue(campaign.is_current)
        self.assertEqual(campaign.target_type, BoostCampaign.TargetType.POST)
        self.assertEqual(self.creator.wallet.available_balance, Decimal("35.00"))
        campaign.ends_at = timezone.now() - timezone.timedelta(minutes=1)
        campaign.save(update_fields=["ends_at"])
        self.assertFalse(BoostCampaign.objects.get(pk=campaign.pk).is_current)
        self.assertFalse(active_boosts_qs().filter(pk=campaign.pk).exists())

    def test_story_boost_route_requires_owner(self):
        story = StoryItem.objects.create(
            author=self.creator,
            media_type=StoryItem.MediaType.TEXT,
            text_content="Boost this story",
            audience=StoryItem.Audience.PUBLIC,
            expires_at=timezone.now() + timezone.timedelta(hours=2),
        )
        credit_wallet(self.viewer, Decimal("50.00"), WalletTransaction.Type.DEPOSIT)
        self.client.force_login(self.viewer)

        response = self.client.post(reverse("wallet_boost_story", kwargs={"id": story.id}))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(BoostCampaign.objects.filter(story=story).exists())

    def test_only_staff_can_open_wallet_control(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("wallet_staff_control"))

        self.assertEqual(response.status_code, 302)

    def test_staff_can_top_up_user_coins(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("wallet_staff_control"),
            {
                "coins-submit": "1",
                "coins-user": self.viewer.id,
                "coins-mode": "topup",
                "coins-amount": "12.00",
                "coins-reference": "manual-topup",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.viewer.wallet.refresh_from_db()
        self.assertEqual(self.viewer.wallet.available_balance, Decimal("12.00"))

    def test_premium_badge_renders_safely_on_profile(self):
        silver = MembershipPlan.objects.create(
            name="Silver",
            slug="silver",
            price=Decimal("20.00"),
            billing_period=MembershipPlan.BillingPeriod.MONTHLY,
        )
        assign_membership_by_staff(self.creator, silver, reference="staff-test")

        response = self.client.get(reverse("profile_detail", kwargs={"username": self.creator.profile.username}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Silver")
        self.assertEqual(premium_badge_for(self.creator)["label"], "Silver")

    def test_transaction_recording_is_consistent(self):
        credit_wallet(self.viewer, Decimal("30.00"), WalletTransaction.Type.DEPOSIT, reference="test")
        debit_wallet(self.viewer, Decimal("5.00"), WalletTransaction.Type.ADJUSTMENT, reference="test-debit")
        self.viewer.wallet.refresh_from_db()
        self.assertEqual(self.viewer.wallet.available_balance, Decimal("25.00"))
        self.assertEqual(self.viewer.wallet.transactions.count(), 2)

    def test_daily_checkin_claim_creates_single_adjustment(self):
        status, created = claim_daily_checkin(self.viewer)

        self.assertTrue(created)
        self.assertTrue(status["claimed_today"])
        self.assertEqual(
            WalletTransaction.objects.filter(
                wallet=self.viewer.wallet,
                reference__startswith=DAILY_CHECKIN_REFERENCE_PREFIX,
            ).count(),
            1,
        )

        second_status, second_created = claim_daily_checkin(self.viewer)
        self.assertFalse(second_created)
        self.assertTrue(second_status["claimed_today"])

    def test_wallet_home_shows_daily_checkin_status(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("wallet_home"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("daily_checkin", response.context)
        self.assertEqual(response.context["daily_checkin"]["streak"], daily_checkin_status(self.viewer)["streak"])
