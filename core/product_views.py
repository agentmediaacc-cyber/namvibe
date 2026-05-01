from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from accounts.models import Follow, FriendRequest
from communities.models import Community
from dating.models import DatingLike
from live.models import LiveSession
from messaging.models import Message
from posts.models import Post
from posts.models import Comment
from posts.services import trending_hashtags
from supportapp.models import SystemPromoCard
from wallet.models import GiftCatalog, GiftEvent, MembershipPlan, WalletTransaction
from wallet.services import active_membership_for, ensure_wallet


def _feature_page_context(request, key):
    published_posts = Post.objects.visible_to(request.user).published().select_related("author", "author__profile", "community")
    recent_posts = list(published_posts[:8])
    recent_reels = list(
        published_posts.filter(post_type__in=[Post.PostType.REEL, Post.PostType.VIDEO]).prefetch_related("media")[:6]
    )
    public_communities = list(
        Community.objects.filter(privacy=Community.Privacy.PUBLIC).select_related("owner").order_by("-member_count", "-created_at")[:6]
    )
    featured_live = list(
        LiveSession.objects.exclude(status=LiveSession.Status.ENDED).select_related("host", "host__profile").order_by("-viewer_count", "-created_at")[:4]
    )
    promo_cards = list(SystemPromoCard.objects.filter(is_active=True).order_by("-priority", "-created_at")[:4])
    context = {
        "feature_metrics": [],
        "feature_shortcuts": [],
        "feature_sections": [],
        "feature_note": "",
        "feature_promos": promo_cards,
    }

    if key in {"channels", "gaming"}:
        context["feature_metrics"] = [
            {"label": "Live rooms", "value": len(featured_live)},
            {"label": "Fresh posts", "value": len(recent_posts)},
            {"label": "Trending tags", "value": len(trending_hashtags(6))},
        ]
        context["feature_shortcuts"] = [
            {"label": "Open feed", "url": "/feed/"},
            {"label": "Reels feed", "url": "/reels/"},
            {"label": "Live now", "url": "/live/"},
            {"label": "Creator Studio", "url": "/studio/"},
        ]
        context["feature_sections"] = [
            {"title": "Trending creators", "cards": recent_posts, "kind": "post"},
            {"title": "Communities to watch", "cards": public_communities, "kind": "community"},
            {"title": "Featured live sessions", "cards": featured_live, "kind": "live"},
        ]
        context["feature_note"] = "These routes are starter hubs backed by real posts, communities, and live sessions so they stay useful while deeper creator-specific tooling expands."

    elif key == "photo_selling":
        photo_posts = list(
            published_posts.filter(post_type__in=[Post.PostType.PHOTO, Post.PostType.PREMIUM]).prefetch_related("media")[:8]
        )
        context["feature_metrics"] = [
            {"label": "Sell-ready posts", "value": len(photo_posts)},
            {"label": "Creator tools", "value": 4},
            {"label": "Communities", "value": len(public_communities)},
        ]
        context["feature_shortcuts"] = [
            {"label": "Upload premium photo", "url": "/studio/?type=photo"},
            {"label": "Open creator studio", "url": "/studio/"},
            {"label": "Wallet earnings", "url": "/wallet/creator/earnings/"},
        ]
        context["feature_sections"] = [
            {"title": "Recent creator galleries", "cards": photo_posts, "kind": "post"},
            {"title": "Live creator promos", "cards": featured_live, "kind": "live"},
        ]
        context["feature_note"] = "Photo selling stays connected to the post, wallet, and creator studio systems instead of branching into a disconnected tool."

    elif key in {"flyers", "image_tools"}:
        flyer_posts = list(published_posts.filter(post_type=Post.PostType.FLYER).prefetch_related("media")[:8])
        context["feature_metrics"] = [
            {"label": "Published flyers", "value": len(flyer_posts)},
            {"label": "Recent posts", "value": len(recent_posts)},
            {"label": "Promos ready", "value": len(promo_cards)},
        ]
        context["feature_shortcuts"] = [
            {"label": "Create flyer", "url": "/studio/?type=flyer"},
            {"label": "Create photo", "url": "/studio/?type=photo"},
            {"label": "Promote business", "url": "/ads/promotions/"},
        ]
        context["feature_sections"] = [
            {"title": "Recent flyers", "cards": flyer_posts, "kind": "post"},
            {"title": "Community promotion ideas", "cards": public_communities, "kind": "community"},
        ]
        context["feature_note"] = "These tools route directly back into the studio and ads flow so design work can turn into posts, promos, and community campaigns without dead ends."

    elif key in {"gifting", "coins"} and request.user.is_authenticated:
        wallet = ensure_wallet(request.user)
        gift_catalog = list(GiftCatalog.objects.filter(is_active=True).order_by("coin_cost", "name")[:8])
        gift_events = list(GiftEvent.objects.filter(sender=request.user).select_related("recipient", "gift").order_by("-created_at")[:8])
        context["feature_metrics"] = [
            {"label": "Wallet balance", "value": f"N${wallet.available_balance}"},
            {"label": "Active gifts", "value": len(gift_catalog)},
            {"label": "Sent events", "value": len(gift_events)},
        ]
        context["feature_shortcuts"] = [
            {"label": "Wallet home", "url": "/wallet/"},
            {"label": "Gift history", "url": "/wallet/gifts/"},
            {"label": "Premium plans", "url": "/wallet/membership/plans/"},
        ]
        context["feature_sections"] = [
            {"title": "Gift catalog", "cards": gift_catalog, "kind": "gift"},
            {"title": "Recent sent gifts", "cards": gift_events, "kind": "gift_event"},
        ]
        context["feature_note"] = "Gifts, coins, and premium spend all flow through the same wallet so monetization stays understandable on mobile."
    else:
        context["feature_metrics"] = [
            {"label": "Live routes", "value": len(featured_live)},
            {"label": "Posts", "value": len(recent_posts)},
            {"label": "Communities", "value": len(public_communities)},
        ]
        context["feature_shortcuts"] = [
            {"label": "Open home", "url": "/"},
            {"label": "Open feed", "url": "/feed/"},
            {"label": "Open studio", "url": "/studio/"},
        ]
        context["feature_sections"] = [{"title": "Recent activity", "cards": recent_posts, "kind": "post"}]
        context["feature_note"] = "This page is already wired to working routes and real content sources. It can deepen without forcing users into a broken branch."

    return context


def feature_page(request, key, title, subtitle, actions=None):
    context = {
        "feature_key": key,
        "title": title,
        "subtitle": subtitle,
        "actions": actions or [],
        "safe_mode_message": "",
        "feature_metrics": [],
        "feature_shortcuts": [],
        "feature_sections": [],
        "feature_note": "",
        "feature_promos": [],
    }
    try:
        context.update(_feature_page_context(request, key))

        if key in {"flyers", "image_tools"}:
            context["recent_flyers"] = list(
                Post.objects.visible_to(request.user).filter(post_type=Post.PostType.FLYER).published()[:8]
            )
        if key in {"channels", "gaming"}:
            context["recent_posts"] = list(Post.objects.visible_to(request.user).published()[:8])
        if key in {"gifting", "coins"} and request.user.is_authenticated:
            wallet = ensure_wallet(request.user)
            context["wallet"] = wallet
            context["gift_catalog"] = list(GiftCatalog.objects.filter(is_active=True).order_by("coin_cost", "name"))
            context["gift_events"] = list(GiftEvent.objects.filter(sender=request.user).select_related("recipient", "gift")[:8])
        if key == "notifications" and request.user.is_authenticated:
            context["notifications"] = []
            context["message"] = "Notifications will appear here when someone follows, messages, reacts, gifts, or matches with you."
        if key == "support":
            context["message"] = "Support requests can be routed here without breaking navigation."
    except Exception as exc:
        context["safe_mode_message"] = str(exc)
        context["feature_note"] = "This route is staying online in safe mode while the database connection recovers."
        context["message"] = "Core content is temporarily unavailable, but navigation and product entry points remain online."

    return render(request, "core/product_page.html", context)


def notifications_view(request):
    context = {
        "title": "Notifications",
        "subtitle": "Profile, message, match, wallet, and live alerts in one place.",
        "actions": [{"label": "Open messages", "url_name": "user_dashboard", "query": "?section=messages"}],
        "notification_items": [],
        "notification_groups": [],
        "safe_mode_message": "",
    }
    if request.user.is_authenticated:
        try:
            def _safe_target(url, fallback):
                return url or fallback

            latest_messages = list(Message.objects.filter(conversation__participants=request.user).exclude(sender=request.user).select_related("sender").order_by("-created_at")[:8])
            follows = list(Follow.objects.filter(following=request.user).select_related("follower", "follower__profile").order_by("-created_at")[:6])
            friend_requests = list(FriendRequest.objects.filter(to_user=request.user, status=FriendRequest.Status.PENDING).select_related("from_user", "from_user__profile").order_by("-created_at")[:6])
            accepted_friends = list(
                FriendRequest.objects.filter(from_user=request.user, status=FriendRequest.Status.ACCEPTED)
                .select_related("to_user", "to_user__profile")
                .order_by("-updated_at")[:6]
            )
            dating_likes = list(DatingLike.objects.filter(to_user=request.user).select_related("from_user", "from_user__profile").order_by("-created_at")[:6])
            post_comments = list(Comment.objects.filter(post__author=request.user).exclude(author=request.user).select_related("author", "author__profile", "post").order_by("-created_at")[:8])
            comment_replies = list(
                Comment.objects.filter(parent__author=request.user)
                .exclude(author=request.user)
                .select_related("author", "author__profile", "post", "parent")[:8]
            )
            items = []
            
            # New centralized notifications
            from accounts.models import Notification
            new_notifications = Notification.objects.filter(recipient=request.user).select_related("sender", "sender__profile")[:20]
            for n in new_notifications:
                group_title = {
                    Notification.Type.FOLLOW: "Follows",
                    Notification.Type.LIKE: "Likes",
                    Notification.Type.COMMENT: "Comments",
                    Notification.Type.FRIEND_REQUEST: "Friends",
                    Notification.Type.SYSTEM: "System",
                }.get(n.notification_type, "System")
                items.append({
                    "group": group_title,
                    "title": n.message or f"New {n.notification_type}",
                    "meta": n.created_at,
                    "copy": "Open update",
                    "href": _safe_target(n.target_url, "/notifications/"),
                    "is_new": not n.is_read,
                    "notification_id": n.id,
                })
            
            # centralize others
            items.extend({"group": "Messages", "title": f"@{row.sender.username} sent you a message", "meta": row.created_at, "copy": row.text or "New media message", "href": "/accounts/dashboard/?section=messages", "is_new": True} for row in latest_messages)
            items.extend({"group": "Friends", "title": f"@{row.from_user.profile.username} sent a friend request", "meta": row.created_at, "copy": "Review and accept from your account hub.", "href": "/friends/", "is_new": True} for row in friend_requests)
            items.extend({"group": "Friends", "title": f"@{row.to_user.profile.username} accepted your friend request", "meta": row.updated_at, "copy": "Chat is now open between both of you.", "href": "/friends/", "is_new": True} for row in accepted_friends)
            items.extend({"group": "Dating", "title": f"@{row.from_user.profile.username} liked your dating profile", "meta": row.created_at, "copy": "Open dating likes.", "href": "/dating/likes/", "is_new": True} for row in dating_likes)
            items.extend({"group": "Comments", "title": f"@{row.author.profile.username} commented on your post", "meta": row.created_at, "copy": row.body[:90], "href": f"/post/{row.post.uuid}/", "is_new": True} for row in post_comments)
            items.extend({"group": "Comments", "title": f"@{row.author.profile.username} replied to your comment", "meta": row.created_at, "copy": row.body[:90], "href": f"/post/{row.post.uuid}/", "is_new": True} for row in comment_replies)
            
            ordered_items = sorted(items, key=lambda item: item["meta"], reverse=True)[:20]
            context["notification_items"] = ordered_items
            groups = []
            for group_name in ["Messages", "Follows", "Likes", "Comments", "Friends", "Dating", "System"]:
                grouped = [item for item in ordered_items if item["group"] == group_name]
                if grouped:
                    groups.append({"title": group_name, "items": grouped[:6]})
            context["notification_groups"] = groups
        except Exception as exc:
            context["safe_mode_message"] = str(exc)
    return render(request, "core/notifications.html", context)


@login_required(login_url="login")
@require_POST
def notification_mark_read_view(request, notification_id):
    from accounts.models import Notification

    notification = get_object_or_404(Notification, recipient=request.user, pk=notification_id)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return redirect(request.POST.get("next") or notification.target_url or "notifications")


@login_required(login_url="login")
@require_POST
def notifications_mark_all_read_view(request):
    from accounts.models import Notification

    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return redirect(request.POST.get("next") or "notifications")


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
    safe_mode_message = ""
    try:
        promo_cards = list(SystemPromoCard.objects.filter(is_active=True)[:6])
    except Exception as exc:
        promo_cards = []
        safe_mode_message = str(exc)
    return render(
        request,
        "supportapp/home.html",
        {
            "promo_cards": promo_cards,
            "open_routes": [
                {"label": "Notifications", "url_name": "notifications"},
                {"label": "Wallet", "url_name": "wallet_home"},
                {"label": "Premium plans", "url_name": "wallet_membership_plans"},
                {"label": "Live home", "url_name": "live_home"},
                {"label": "Creator Studio", "url_name": "studio"},
            ],
            "safe_mode_message": safe_mode_message,
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
