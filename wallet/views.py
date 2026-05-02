from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import Profile
from posts.models import Post
from stories.models import StoryItem

from .forms import GiftSendForm, StaffCoinAdjustmentForm, StaffPremiumTierForm
from .models import BoostCampaign, GiftEvent, MembershipPlan, UserMembership, WalletTransaction
from .services import (
    BOOST_DURATION_HOURS,
    InsufficientFunds,
    VIBE_COIN_DISPLAY_RATE,
    active_boost_for_post,
    active_boost_for_profile,
    active_boost_for_story,
    claim_daily_checkin,
    daily_checkin_status,
    active_gifts,
    active_membership_for,
    active_plans,
    assign_membership_by_staff,
    coins_for_amount,
    create_boost,
    creator_earnings_snapshot,
    credit_wallet,
    debit_wallet,
    ensure_wallet,
    premium_badge_for,
    purchase_membership,
    send_gift,
)


@login_required(login_url="login")
def wallet_home_view(request):
    wallet = ensure_wallet(request.user)
    transactions = wallet.transactions.all()[:8]
    gift_form = GiftSendForm()
    earnings = creator_earnings_snapshot(request.user)
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
            "gift_catalog": active_gifts()[:6],
            "gift_form": gift_form,
            "premium_badge": premium_badge_for(request.user),
            "earnings_snapshot": earnings,
            "active_boost_count": BoostCampaign.objects.filter(owner=request.user, active=True).count(),
            "daily_checkin": daily_checkin_status(request.user),
        },
    )


@login_required(login_url="login")
def wallet_coins_view(request):
    wallet = ensure_wallet(request.user)
    transactions = wallet.transactions.filter(
        transaction_type__in=[
            WalletTransaction.Type.DEPOSIT,
            WalletTransaction.Type.GIFT_SENT,
            WalletTransaction.Type.GIFT_RECEIVED,
            WalletTransaction.Type.BOOST_PURCHASE,
            WalletTransaction.Type.ADJUSTMENT,
        ]
    )[:30]
    return render(
        request,
        "wallet/coins.html",
        {
            "wallet": wallet,
            "coin_balance": coins_for_amount(wallet.available_balance),
            "pending_coins": coins_for_amount(wallet.pending_balance),
            "transactions": transactions,
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
@require_POST
def daily_checkin_claim_view(request):
    try:
        status, created = claim_daily_checkin(request.user)
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        if created:
            messages.success(
                request,
                f"Daily check-in claimed. {status['reward_coins']} coins have been added to your wallet.",
            )
        else:
            messages.info(request, "You already claimed your daily check-in today.")
    return redirect(request.POST.get("next") or reverse("user_dashboard"))


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
    snapshot = creator_earnings_snapshot(request.user)
    wallet = snapshot["wallet"]
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
            "earnings_snapshot": snapshot,
        },
    )


@login_required(login_url="login")
@require_POST
def send_gift_to_user_view(request, username):
    recipient_profile = get_object_or_404(Profile.objects.select_related("user"), username__iexact=username)
    form = GiftSendForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a gift and quantity first.")
        return redirect(request.POST.get("next") or reverse("profile_detail", kwargs={"username": recipient_profile.username}))
    try:
        send_gift(request.user, recipient_profile.user, form.cleaned_data["gift"], form.cleaned_data["quantity"])
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Gift sent to @{recipient_profile.username}.")
    return redirect(form.cleaned_data.get("next") or reverse("profile_detail", kwargs={"username": recipient_profile.username}))


@login_required(login_url="login")
@require_POST
def send_gift_to_post_view(request, uuid):
    post = get_object_or_404(Post.objects.select_related("author", "author__profile"), uuid=uuid)
    form = GiftSendForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a gift and quantity first.")
        return redirect(request.POST.get("next") or reverse("post_detail", kwargs={"uuid": post.uuid}))
    try:
        send_gift(request.user, post.author, form.cleaned_data["gift"], form.cleaned_data["quantity"])
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        recipient_label = getattr(getattr(post.author, "profile", None), "username", "") or post.author.username
        messages.success(request, f"Gift sent to @{recipient_label}.")
    return redirect(form.cleaned_data.get("next") or reverse("post_detail", kwargs={"uuid": post.uuid}))


@login_required(login_url="login")
@require_POST
def send_gift_to_story_view(request, id):
    story = get_object_or_404(StoryItem.objects.select_related("author", "author__profile"), pk=id)
    form = GiftSendForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a gift and quantity first.")
        return redirect(request.POST.get("next") or reverse("story_detail", kwargs={"id": story.id}))
    try:
        send_gift(request.user, story.author, form.cleaned_data["gift"], form.cleaned_data["quantity"])
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        recipient_label = getattr(getattr(story.author, "profile", None), "username", "") or story.author.username
        messages.success(request, f"Gift sent to @{recipient_label}.")
    return redirect(form.cleaned_data.get("next") or reverse("story_detail", kwargs={"id": story.id}))


@login_required(login_url="login")
@require_POST
def boost_post_view(request, uuid):
    post = get_object_or_404(Post.objects.select_related("author", "author__profile"), uuid=uuid)
    try:
        create_boost(request.user, post=post)
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Post boosted for {BOOST_DURATION_HOURS} hours.")
    return redirect(request.POST.get("next") or reverse("post_detail", kwargs={"uuid": post.uuid}))


@login_required(login_url="login")
@require_POST
def boost_profile_view(request, username):
    profile = get_object_or_404(Profile.objects.select_related("user"), username__iexact=username)
    try:
        create_boost(request.user, profile=profile)
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Profile boosted for {BOOST_DURATION_HOURS} hours.")
    return redirect(request.POST.get("next") or reverse("profile_detail", kwargs={"username": profile.username}))


@login_required(login_url="login")
@require_POST
def boost_story_view(request, id):
    story = get_object_or_404(StoryItem.objects.select_related("author", "author__profile"), pk=id)
    try:
        create_boost(request.user, story=story)
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Story boosted for {BOOST_DURATION_HOURS} hours.")
    return redirect(request.POST.get("next") or reverse("story_detail", kwargs={"id": story.id}))


@staff_member_required(login_url="login")
def staff_wallet_control_view(request):
    topup_form = StaffCoinAdjustmentForm(prefix="coins", data=request.POST or None)
    premium_form = StaffPremiumTierForm(prefix="premium", data=request.POST or None)

    if request.method == "POST":
        if "coins-submit" in request.POST and topup_form.is_valid():
            user = topup_form.cleaned_data["user"]
            amount = topup_form.cleaned_data["amount"]
            reference = topup_form.cleaned_data["reference"] or "staff-adjustment"
            try:
                if topup_form.cleaned_data["mode"] == StaffCoinAdjustmentForm.MODE_TOPUP:
                    credit_wallet(user, amount, WalletTransaction.Type.DEPOSIT, reference=reference, metadata={"source": "staff"})
                    messages.success(request, f"Added coins to @{user.username}.")
                else:
                    debit_wallet(user, amount, WalletTransaction.Type.ADJUSTMENT, reference=reference, metadata={"source": "staff"})
                    messages.success(request, f"Debited coins from @{user.username}.")
            except Exception as exc:
                messages.error(request, str(exc))
            return redirect("wallet_staff_control")

        if "premium-submit" in request.POST and premium_form.is_valid():
            membership = assign_membership_by_staff(
                premium_form.cleaned_data["user"],
                premium_form.cleaned_data["plan"],
                reference=premium_form.cleaned_data["reference"] or "staff-upgrade",
            )
            messages.success(request, f"{membership.plan.name} is now active for @{membership.user.username}.")
            return redirect("wallet_staff_control")

    recent_transactions = WalletTransaction.objects.select_related("wallet", "wallet__user").order_by("-created_at")[:20]
    creator_rows = (
        GiftEvent.objects.values("recipient__username")
        .annotate(total_gifts=Sum("creator_value"))
        .order_by("-total_gifts")[:12]
    )
    return render(
        request,
        "wallet/staff_control.html",
        {
            "topup_form": topup_form,
            "premium_form": premium_form,
            "recent_transactions": recent_transactions,
            "creator_rows": creator_rows,
        },
    )
