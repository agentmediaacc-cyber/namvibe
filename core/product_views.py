from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from accounts.models import Follow, FriendRequest
from dating.models import DatingLike
from messaging.models import Message
from posts.models import Post
from posts.models import Comment
from supportapp.models import SystemPromoCard
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
    context = {
        "title": "Notifications",
        "subtitle": "Profile, message, match, wallet, and live alerts in one place.",
        "actions": [{"label": "Open messages", "url_name": "user_dashboard", "query": "?section=messages"}],
        "notification_items": [],
    }
    if request.user.is_authenticated:
        latest_messages = Message.objects.filter(conversation__participants=request.user).exclude(sender=request.user).select_related("sender").order_by("-created_at")[:8]
        follows = Follow.objects.filter(following=request.user).select_related("follower", "follower__profile").order_by("-created_at")[:6]
        friend_requests = FriendRequest.objects.filter(to_user=request.user, status=FriendRequest.Status.PENDING).select_related("from_user", "from_user__profile").order_by("-created_at")[:6]
        dating_likes = DatingLike.objects.filter(to_user=request.user).select_related("from_user", "from_user__profile").order_by("-created_at")[:6]
        post_comments = Comment.objects.filter(post__author=request.user).exclude(author=request.user).select_related("author", "author__profile", "post").order_by("-created_at")[:8]
        items = []
        items.extend({"title": f"@{row.sender.username} sent you a message", "meta": row.created_at, "copy": row.text or "New media message", "href": "/accounts/dashboard/?section=messages"} for row in latest_messages)
        items.extend({"title": f"@{row.follower.profile.username} followed you", "meta": row.created_at, "copy": "Open profile", "href": f"/profile/{row.follower.profile.username}/"} for row in follows)
        items.extend({"title": f"@{row.from_user.profile.username} sent a friend request", "meta": row.created_at, "copy": "Review in dashboard", "href": "/accounts/dashboard/?section=friends"} for row in friend_requests)
        items.extend({"title": f"@{row.from_user.profile.username} liked your dating profile", "meta": row.created_at, "copy": "Open dating likes", "href": "/dating/likes/"} for row in dating_likes)
        items.extend({"title": f"@{row.author.profile.username} commented on your post", "meta": row.created_at, "copy": row.body[:80], "href": f"/post/{row.post.uuid}/"} for row in post_comments)
        context["notification_items"] = sorted(items, key=lambda item: item["meta"], reverse=True)[:20]
    return render(request, "core/notifications.html", context)


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
    return render(
        request,
        "supportapp/home.html",
        {
            "promo_cards": SystemPromoCard.objects.filter(is_active=True)[:6],
            "open_routes": [
                {"label": "Notifications", "url_name": "notifications"},
                {"label": "Wallet", "url_name": "wallet_home"},
                {"label": "Premium plans", "url_name": "wallet_membership_plans"},
                {"label": "Live home", "url_name": "live_home"},
                {"label": "Creator Studio", "url_name": "studio"},
            ],
        },
    )


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
