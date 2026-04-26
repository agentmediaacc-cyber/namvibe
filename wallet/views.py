from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import GiftEvent, MembershipPlan, UserMembership, WalletTransaction
from .services import VIBE_COIN_DISPLAY_RATE, InsufficientFunds, active_membership_for, active_plans, ensure_wallet, purchase_membership


@login_required(login_url="login")
def wallet_home_view(request):
    wallet = ensure_wallet(request.user)
    transactions = wallet.transactions.all()[:8]
    return render(
        request,
        "wallet/home.html",
        {
            "wallet": wallet,
            "transactions": transactions,
            "active_membership": active_membership_for(request.user),
            "sent_gifts_count": GiftEvent.objects.filter(sender=request.user).count(),
            "received_gifts_count": GiftEvent.objects.filter(recipient=request.user).count(),
            "coin_display_rate": VIBE_COIN_DISPLAY_RATE,
        },
    )


@login_required(login_url="login")
def wallet_transactions_view(request):
    wallet = ensure_wallet(request.user)
    paginator = Paginator(wallet.transactions.all(), 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "wallet/transactions.html", {"wallet": wallet, "page_obj": page_obj})


@login_required(login_url="login")
def wallet_gifts_view(request):
    sent = GiftEvent.objects.filter(sender=request.user).select_related("recipient", "gift", "live_session")[:50]
    received = GiftEvent.objects.filter(recipient=request.user).select_related("sender", "gift", "live_session")[:50]
    return render(request, "wallet/gifts.html", {"sent_gifts": sent, "received_gifts": received})


@login_required(login_url="login")
def membership_overview_view(request):
    wallet = ensure_wallet(request.user)
    memberships = UserMembership.objects.filter(user=request.user).select_related("plan")[:20]
    return render(
        request,
        "wallet/membership.html",
        {
            "wallet": wallet,
            "active_membership": active_membership_for(request.user),
            "plans": active_plans(),
            "memberships": memberships,
            "coin_display_rate": VIBE_COIN_DISPLAY_RATE,
        },
    )


@login_required(login_url="login")
def membership_plans_view(request):
    return render(
        request,
        "wallet/membership_plans.html",
        {"plans": active_plans(), "wallet": ensure_wallet(request.user), "coin_display_rate": VIBE_COIN_DISPLAY_RATE},
    )


@login_required(login_url="login")
def membership_history_view(request):
    memberships = UserMembership.objects.filter(user=request.user).select_related("plan")[:50]
    transactions = WalletTransaction.objects.filter(
        wallet=ensure_wallet(request.user),
        transaction_type=WalletTransaction.Type.PREMIUM_MEMBERSHIP_PURCHASE,
    )[:50]
    return render(
        request,
        "wallet/membership_history.html",
        {"memberships": memberships, "transactions": transactions, "coin_display_rate": VIBE_COIN_DISPLAY_RATE},
    )


@login_required(login_url="login")
@require_POST
def membership_purchase_view(request, slug):
    plan = get_object_or_404(MembershipPlan, slug=slug, is_active=True)
    try:
        membership, _ = purchase_membership(request.user, plan)
    except InsufficientFunds:
        messages.error(request, "Your wallet balance is not enough for this membership.")
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"{membership.plan.name} is now active.")
    return redirect("wallet_membership")


@login_required(login_url="login")
def creator_earnings_view(request):
    wallet = ensure_wallet(request.user)
    received_gifts = GiftEvent.objects.filter(recipient=request.user).select_related("sender", "gift", "live_session")[:30]
    earning_transactions = WalletTransaction.objects.filter(
        wallet=wallet,
        transaction_type__in=[
            WalletTransaction.Type.GIFT_RECEIVED,
            WalletTransaction.Type.CREATOR_PAYOUT_CREDIT,
            WalletTransaction.Type.LIVE_ACCESS_PURCHASE,
        ],
    )[:50]
    return render(
        request,
        "wallet/creator_earnings.html",
        {
            "wallet": wallet,
            "received_gifts": received_gifts,
            "earning_transactions": earning_transactions,
            "coin_display_rate": VIBE_COIN_DISPLAY_RATE,
        },
    )
