from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from live.models import LiveAccessPurchase, LiveSession
from live.services import can_access_session
from .models import CreatorEntitlement, GiftCatalog, GiftEvent, MembershipPlan, UserMembership, WalletAccount, WalletTransaction
from .services import InsufficientFunds, credit_wallet, debit_wallet, purchase_membership, send_gift


class WalletPhaseFiveTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username="creator5", password="Pass12345")
        self.viewer = User.objects.create_user(username="viewer5", password="Pass12345")
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

    def test_transaction_recording_is_consistent(self):
        credit_wallet(self.viewer, Decimal("30.00"), WalletTransaction.Type.DEPOSIT, reference="test")
        debit_wallet(self.viewer, Decimal("5.00"), WalletTransaction.Type.ADJUSTMENT, reference="test-debit")
        self.viewer.wallet.refresh_from_db()
        self.assertEqual(self.viewer.wallet.available_balance, Decimal("25.00"))
        self.assertEqual(self.viewer.wallet.transactions.count(), 2)
