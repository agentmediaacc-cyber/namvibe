from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from posts.models import Post
from wallet.models import GiftCatalog, GiftEvent, MembershipPlan, WalletTransaction
from wallet.services import active_membership_for, ensure_wallet


def feature_page(request, key, title, subtitle, actions=None):
    context = {
        "feature_key": key,
        "title": title,
        "subtitle": subtitle,
        "actions": actions or [],
    }

    if key in {"flyers", "image_tools"}:
        context["recent_flyers"] = Post.objects.visible_to(request.user).filter(post_type=Post.PostType.FLYER).published()[:8]
    if key in {"channels", "gaming"}:
        context["recent_posts"] = Post.objects.visible_to(request.user).published()[:8]
    if key in {"gifting", "coins"} and request.user.is_authenticated:
        wallet = ensure_wallet(request.user)
        context["wallet"] = wallet
        context["gift_catalog"] = GiftCatalog.objects.filter(is_active=True).order_by("coin_cost", "name")
        context["gift_events"] = GiftEvent.objects.filter(sender=request.user).select_related("recipient", "gift")[:8]
    if key == "notifications" and request.user.is_authenticated:
        context["notifications"] = []
        context["message"] = "Notifications will appear here when someone follows, messages, reacts, gifts, or matches with you."
    if key == "support":
        context["message"] = "Support requests can be routed here without breaking navigation."

    return render(request, "core/product_page.html", context)


def notifications_view(request):
    return feature_page(
        request,
        "notifications",
        "Notifications",
        "Profile, message, match, wallet, and live alerts in one place.",
        [{"label": "Open messages", "url_name": "user_dashboard", "query": "?section=messages"}],
    )


def channels_view(request):
    return feature_page(request, "channels", "Channels", "Follow creator channels, communities, and topic streams.")


def gaming_view(request):
    return feature_page(request, "gaming", "Gaming", "Live gaming rooms, clips, creator posts, and community challenges.")


def photo_selling_view(request):
    return feature_page(request, "photo_selling", "Photo Selling", "Creator storefront hooks for paid galleries and private photo offers.")


def flyer_tools_view(request):
    return feature_page(
        request,
        "flyers",
        "Flyer Studio",
        "Create and publish flyers through Creator Studio using structured flyer metadata.",
        [{"label": "Create flyer", "url_name": "studio", "query": "?type=flyer"}],
    )


def image_tools_view(request):
    return feature_page(
        request,
        "image_tools",
        "Image Tools",
        "Crop, caption, style, and publish image posts through the media composer.",
        [{"label": "Open Studio", "url_name": "studio", "query": "?type=photo"}],
    )


@login_required(login_url="login")
def gifting_view(request):
    return feature_page(request, "gifting", "Gifting", "Send and track real gifts from your wallet history.")


@login_required(login_url="login")
def coins_view(request):
    return feature_page(request, "coins", "Coins", "Wallet balance, coin activity, and creator earning transactions.")


def support_view(request):
    return feature_page(request, "support", "Support", "Help, safety, reporting, and account support.")


@login_required(login_url="login")
def premium_tier_view(request, tier):
    wallet = ensure_wallet(request.user)
    plans = MembershipPlan.objects.filter(is_active=True).order_by("price", "name")
    spend_total = (
        WalletTransaction.objects.filter(wallet=wallet, transaction_type=WalletTransaction.Type.PREMIUM_MEMBERSHIP_PURCHASE)
        .aggregate(total=Sum("amount"))
        .get("total")
        or 0
    )
    return render(
        request,
        "core/premium_tier.html",
        {
            "tier": tier.title(),
            "wallet": wallet,
            "plans": plans,
            "active_membership": active_membership_for(request.user),
            "spend_total": spend_total,
        },
    )
