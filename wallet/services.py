from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from live.models import LiveAccessPurchase, LiveGift, LiveSession
from .models import CreatorEntitlement, GiftCatalog, GiftEvent, MembershipPlan, UserMembership, WalletAccount, WalletTransaction


class WalletError(Exception):
    pass


class InsufficientFunds(WalletError):
    pass


def ensure_wallet(user):
    wallet, _ = WalletAccount.objects.get_or_create(user=user)
    return wallet


def record_transaction(wallet, transaction_type, amount, status=WalletTransaction.Status.COMPLETED, reference="", metadata=None):
    completed_at = timezone.now() if status == WalletTransaction.Status.COMPLETED else None
    return WalletTransaction.objects.create(
        wallet=wallet,
        transaction_type=transaction_type,
        status=status,
        amount=Decimal(amount),
        reference=reference,
        metadata=metadata or {},
        completed_at=completed_at,
    )


@transaction.atomic
def credit_wallet(user, amount, transaction_type=WalletTransaction.Type.ADJUSTMENT, reference="", metadata=None, pending=False):
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError("Credit amount must be positive.")
    wallet = WalletAccount.objects.select_for_update().get(pk=ensure_wallet(user).pk)
    if pending:
        wallet.pending_balance += amount
    else:
        wallet.available_balance += amount
    wallet.lifetime_earned += amount
    wallet.save(update_fields=["available_balance", "pending_balance", "lifetime_earned", "updated_at"])
    txn = record_transaction(wallet, transaction_type, amount, reference=reference, metadata=metadata)
    return wallet, txn


@transaction.atomic
def debit_wallet(user, amount, transaction_type=WalletTransaction.Type.ADJUSTMENT, reference="", metadata=None):
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError("Debit amount must be positive.")
    wallet = WalletAccount.objects.select_for_update().get(pk=ensure_wallet(user).pk)
    if not wallet.is_active or wallet.available_balance < amount:
        raise InsufficientFunds("Insufficient wallet balance.")
    wallet.available_balance -= amount
    wallet.lifetime_spent += amount
    wallet.save(update_fields=["available_balance", "lifetime_spent", "updated_at"])
    txn = record_transaction(wallet, transaction_type, amount, reference=reference, metadata=metadata)
    return wallet, txn


def active_membership_for(user):
    if not user.is_authenticated:
        return None
    now = timezone.now()
    return (
        UserMembership.objects.select_related("plan")
        .filter(user=user, status=UserMembership.Status.ACTIVE)
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .order_by("-starts_at")
        .first()
    )


def user_has_feature(user, flag):
    membership = active_membership_for(user)
    if not membership:
        return False
    return bool((membership.plan.feature_flags or {}).get(flag))


@transaction.atomic
def purchase_membership(user, plan):
    if not plan.is_active:
        raise WalletError("This membership plan is not available.")
    _, txn = debit_wallet(
        user,
        plan.price,
        WalletTransaction.Type.PREMIUM_MEMBERSHIP_PURCHASE,
        reference=f"membership:{plan.slug}",
        metadata={"plan": plan.slug},
    )
    now = timezone.now()
    duration = plan.duration_delta()
    membership = UserMembership.objects.create(
        user=user,
        plan=plan,
        status=UserMembership.Status.ACTIVE,
        starts_at=now,
        ends_at=now + duration if duration else None,
    )
    return membership, txn


def has_creator_entitlement(user, creator=None, session=None, entitlement_type=CreatorEntitlement.EntitlementType.LIVE_ROOM):
    if not user.is_authenticated:
        return False
    now = timezone.now()
    queryset = CreatorEntitlement.objects.filter(
        buyer=user,
        entitlement_type=entitlement_type,
        active=True,
        starts_at__lte=now,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
    if session is not None:
        queryset = queryset.filter(Q(live_session=session) | Q(live_session__isnull=True, creator=session.host))
    elif creator is not None:
        queryset = queryset.filter(creator=creator)
    return queryset.exists()


def user_has_live_access(user, session):
    if not user.is_authenticated:
        return False
    if session.host_id == user.id:
        return True
    if has_creator_entitlement(user, session=session):
        return True
    if user_has_feature(user, "premium_live_access"):
        return True
    return LiveAccessPurchase.objects.filter(session=session, user=user, is_active=True).exists()


@transaction.atomic
def purchase_live_access(user, session, amount=None):
    if session.access_type != LiveSession.AccessType.PREMIUM:
        raise WalletError("This room does not require premium access.")
    amount = Decimal(amount if amount is not None else "25.00")
    _, debit_txn = debit_wallet(
        user,
        amount,
        WalletTransaction.Type.LIVE_ACCESS_PURCHASE,
        reference=f"live_access:{session.uuid}",
        metadata={"session": str(session.uuid), "creator": session.host.username},
    )
    entitlement = CreatorEntitlement.objects.create(
        buyer=user,
        creator=session.host,
        live_session=session,
        entitlement_type=CreatorEntitlement.EntitlementType.LIVE_ROOM,
        source_transaction=debit_txn,
        active=True,
    )
    LiveAccessPurchase.objects.update_or_create(
        session=session,
        user=user,
        defaults={"amount": amount, "is_active": True},
    )
    credit_wallet(
        session.host,
        amount,
        WalletTransaction.Type.CREATOR_PAYOUT_CREDIT,
        reference=f"live_access:{session.uuid}",
        metadata={"buyer": user.username, "session": str(session.uuid)},
        pending=True,
    )
    return entitlement, debit_txn


@transaction.atomic
def send_gift(sender, recipient, gift, quantity=1, live_session=None):
    if sender == recipient:
        raise WalletError("You cannot send a gift to yourself.")
    if not gift.is_active:
        raise WalletError("This gift is not available.")
    quantity = int(quantity or 1)
    if quantity < 1:
        raise ValidationError("Gift quantity must be at least one.")
    total_cost = gift.coin_cost * quantity
    creator_value = gift.value_to_creator * quantity
    _, sent_txn = debit_wallet(
        sender,
        total_cost,
        WalletTransaction.Type.GIFT_SENT,
        reference=f"gift:{gift.slug}",
        metadata={"gift": gift.slug, "quantity": quantity, "recipient": recipient.username},
    )
    credit_wallet(
        recipient,
        creator_value,
        WalletTransaction.Type.GIFT_RECEIVED,
        reference=f"gift:{gift.slug}",
        metadata={"gift": gift.slug, "quantity": quantity, "sender": sender.username},
        pending=True,
    )
    event = GiftEvent.objects.create(
        sender=sender,
        recipient=recipient,
        live_session=live_session,
        gift=gift,
        quantity=quantity,
        total_cost=total_cost,
        creator_value=creator_value,
    )
    if live_session:
        LiveGift.objects.create(session=live_session, sender=sender, gift_name=gift.name, token_amount=int(total_cost))
    return event, sent_txn


def default_live_access_price(session):
    return Decimal("25.00")


def active_plans():
    return MembershipPlan.objects.filter(is_active=True).order_by("price", "name")


def active_gifts():
    return GiftCatalog.objects.filter(is_active=True).order_by("coin_cost", "name")
