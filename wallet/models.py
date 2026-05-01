import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.media import validate_image_file


class WalletAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet")
    available_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pending_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    lifetime_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    lifetime_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet for {self.user}"


class WalletTransaction(models.Model):
    class Type(models.TextChoices):
        DEPOSIT = "deposit", "Deposit"
        WITHDRAWAL = "withdrawal", "Withdrawal"
        GIFT_SENT = "gift_sent", "Gift sent"
        GIFT_RECEIVED = "gift_received", "Gift received"
        BOOST_PURCHASE = "boost_purchase", "Boost purchase"
        PREMIUM_MEMBERSHIP_PURCHASE = "premium_membership_purchase", "Premium membership purchase"
        LIVE_ACCESS_PURCHASE = "live_access_purchase", "Live access purchase"
        CREATOR_PAYOUT_CREDIT = "creator_payout_credit", "Creator payout credit"
        CREATOR_PAYOUT_DEBIT = "creator_payout_debit", "Creator payout debit"
        REFUND = "refund", "Refund"
        ADJUSTMENT = "adjustment", "Adjustment"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    wallet = models.ForeignKey(WalletAccount, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=40, choices=Type.choices, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default="NAD")
    reference = models.CharField(max_length=160, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["wallet", "created_at"]),
            models.Index(fields=["transaction_type", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} {self.amount} {self.currency}"


class MembershipPlan(models.Model):
    class BillingPeriod(models.TextChoices):
        ONE_TIME = "one_time", "One time"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    billing_period = models.CharField(max_length=20, choices=BillingPeriod.choices, default=BillingPeriod.MONTHLY)
    is_active = models.BooleanField(default=True, db_index=True)
    feature_flags = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price", "name"]

    def __str__(self):
        return self.name

    def duration_delta(self):
        if self.billing_period == self.BillingPeriod.YEARLY:
            return timedelta(days=365)
        if self.billing_period == self.BillingPeriod.MONTHLY:
            return timedelta(days=30)
        return None


class UserMembership(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELED = "canceled", "Canceled"
        PENDING = "pending", "Pending"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name="memberships")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True, db_index=True)
    auto_renew = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at"]
        indexes = [
            models.Index(fields=["user", "status", "ends_at"]),
            models.Index(fields=["plan", "status"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.plan} ({self.status})"

    @property
    def is_current(self):
        return self.status == self.Status.ACTIVE and (self.ends_at is None or self.ends_at > timezone.now())


class GiftCatalog(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    icon = models.ImageField(upload_to="wallet/gifts/", blank=True, validators=[validate_image_file])
    coin_cost = models.DecimalField(max_digits=10, decimal_places=2)
    value_to_creator = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["coin_cost", "name"]

    def __str__(self):
        return self.name


class GiftEvent(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gifts_sent")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gifts_received")
    live_session = models.ForeignKey("live.LiveSession", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_gifts")
    gift = models.ForeignKey(GiftCatalog, on_delete=models.PROTECT, related_name="events")
    quantity = models.PositiveIntegerField(default=1)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)
    creator_value = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sender", "created_at"]),
            models.Index(fields=["recipient", "created_at"]),
            models.Index(fields=["live_session", "created_at"]),
        ]

    def __str__(self):
        return f"{self.sender} sent {self.quantity}x {self.gift} to {self.recipient}"


class CreatorEntitlement(models.Model):
    class EntitlementType(models.TextChoices):
        LIVE_ROOM = "live_room", "Live room"
        PREMIUM_PROFILE = "premium_profile", "Premium profile"
        PREMIUM_POST = "premium_post", "Premium post"
        REPLAY = "replay", "Replay"

    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="creator_entitlements")
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="creator_access_entitlements")
    live_session = models.ForeignKey("live.LiveSession", on_delete=models.CASCADE, null=True, blank=True, related_name="wallet_entitlements")
    entitlement_type = models.CharField(max_length=24, choices=EntitlementType.choices, db_index=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True, db_index=True)
    source_transaction = models.ForeignKey(WalletTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name="entitlements")
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["buyer", "entitlement_type", "active"]),
            models.Index(fields=["creator", "entitlement_type", "active"]),
            models.Index(fields=["live_session", "active"]),
        ]

    def __str__(self):
        return f"{self.buyer} access to {self.creator} ({self.entitlement_type})"

    @property
    def is_current(self):
        return self.active and self.starts_at <= timezone.now() and (self.ends_at is None or self.ends_at > timezone.now())


class BoostCampaign(models.Model):
    class TargetType(models.TextChoices):
        POST = "post", "Post"
        PROFILE = "profile", "Profile"
        STORY = "story", "Story"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="boost_campaigns")
    target_type = models.CharField(max_length=16, choices=TargetType.choices, db_index=True)
    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE, null=True, blank=True, related_name="boost_campaigns")
    profile = models.ForeignKey("accounts.Profile", on_delete=models.CASCADE, null=True, blank=True, related_name="boost_campaigns")
    story = models.ForeignKey("stories.StoryItem", on_delete=models.CASCADE, null=True, blank=True, related_name="boost_campaigns")
    coin_cost = models.DecimalField(max_digits=10, decimal_places=2)
    starts_at = models.DateTimeField(default=timezone.now, db_index=True)
    ends_at = models.DateTimeField(db_index=True)
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ends_at", "-created_at"]
        indexes = [
            models.Index(fields=["target_type", "active", "ends_at"]),
            models.Index(fields=["owner", "active", "ends_at"]),
            models.Index(fields=["post", "active"]),
            models.Index(fields=["profile", "active"]),
            models.Index(fields=["story", "active"]),
        ]

    def clean(self):
        targets = [bool(self.post_id), bool(self.profile_id), bool(self.story_id)]
        if sum(targets) != 1:
            raise ValidationError("Boost campaigns require exactly one target.")

    @property
    def is_current(self):
        return self.active and self.starts_at <= timezone.now() and self.ends_at > timezone.now()

    def __str__(self):
        return f"{self.owner} boost ({self.target_type}) until {self.ends_at:%Y-%m-%d %H:%M}"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_wallet_for_user(sender, instance, created, **kwargs):
    WalletAccount.objects.get_or_create(user=instance)
