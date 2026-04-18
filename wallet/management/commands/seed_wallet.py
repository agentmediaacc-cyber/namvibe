from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from live.models import LiveSession
from wallet.models import GiftCatalog, MembershipPlan, UserMembership, WalletTransaction
from wallet.services import credit_wallet, ensure_wallet, send_gift


class Command(BaseCommand):
    help = "Seed Namvibe wallet plans, gift catalog, demo balances, and sample gift events."

    def handle(self, *args, **options):
        silver, _ = MembershipPlan.objects.update_or_create(
            slug="silver",
            defaults={
                "name": "Silver",
                "description": "Starter premium access for profile polish, discovery, and member-only areas.",
                "price": Decimal("75.00"),
                "billing_period": MembershipPlan.BillingPeriod.MONTHLY,
                "is_active": True,
                "feature_flags": {"premium_badge": True, "profile_polish": True},
            },
        )
        premium, _ = MembershipPlan.objects.update_or_create(
            slug="vip",
            defaults={
                "name": "VIP",
                "description": "VIP hooks for live rooms, profile status, creator discovery, and priority experiences.",
                "price": Decimal("150.00"),
                "billing_period": MembershipPlan.BillingPeriod.MONTHLY,
                "is_active": True,
                "feature_flags": {"premium_badge": True, "premium_live_access": True, "vip_badge": True},
            },
        )
        MembershipPlan.objects.update_or_create(
            slug="platinum",
            defaults={
                "name": "Platinum",
                "description": "Creator-focused premium hooks for boosts, gifting, paid access, and earning tools.",
                "price": Decimal("250.00"),
                "billing_period": MembershipPlan.BillingPeriod.MONTHLY,
                "is_active": True,
                "feature_flags": {"premium_badge": True, "premium_live_access": True, "vip_badge": True, "creator_boosts": True},
            },
        )
        gifts = [
            ("spark", "Spark", "10.00", "8.00"),
            ("desert-rose", "Desert Rose", "25.00", "20.00"),
            ("diamond-vibe", "Diamond Vibe", "50.00", "42.00"),
        ]
        gift_objects = []
        for slug, name, cost, creator_value in gifts:
            gift, _ = GiftCatalog.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "coin_cost": Decimal(cost), "value_to_creator": Decimal(creator_value), "is_active": True},
            )
            gift_objects.append(gift)

        users = list(User.objects.all()[:6])
        for user in users:
            wallet = ensure_wallet(user)
            if wallet.available_balance == 0:
                credit_wallet(user, Decimal("250.00"), WalletTransaction.Type.DEPOSIT, reference="seed:demo_balance")

        if users:
            UserMembership.objects.get_or_create(
                user=users[0],
                plan=premium,
                status=UserMembership.Status.ACTIVE,
                defaults={"starts_at": timezone.now(), "ends_at": timezone.now() + premium.duration_delta()},
            )

        live_session = LiveSession.objects.filter(status=LiveSession.Status.LIVE).select_related("host").first()
        if live_session and len(users) > 1 and gift_objects:
            sender = next((user for user in users if user != live_session.host), users[0])
            if sender != live_session.host:
                send_gift(sender, live_session.host, gift_objects[0], 1, live_session=live_session)

        self.stdout.write(self.style.SUCCESS("Seeded wallet plans, gifts, balances, memberships, and sample gifts."))
