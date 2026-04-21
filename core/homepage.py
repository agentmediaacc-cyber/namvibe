from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.db.models import F, Q, Sum
from django.urls import reverse
from django.utils import timezone

from accounts.models import Follow, FriendRequest, Profile
from ads.models import Advertisement
from communities.models import Community
from dating.models import DatingLike, DatingProfile, Match
from dating.services import discovery_queryset_for
from live.services import featured_sessions_for, live_now_for
from messaging.models import Message
from messaging.services import conversations_for_user
from posts.models import Comment, Post
from posts.services import FeedRankingService, suggested_communities_for, suggested_users_for, trending_hashtags
from stories.models import StoryItem
from stories.services import story_rail_for
from supportapp.models import SystemPromoCard
from wallet.models import MembershipPlan, WalletTransaction
from wallet.services import active_membership_for, ensure_wallet


def _dashboard_section_url(section, **params):
    query = {"section": section}
    query.update({key: value for key, value in params.items() if value not in (None, "")})
    return f"{reverse('user_dashboard')}?{urlencode(query)}"


def _safe_profile_url(user):
    profile = getattr(user, "profile", None)
    if profile and profile.username:
        return reverse("profile_detail", kwargs={"username": profile.username})
    return reverse("user_dashboard")


def _active_ads(placement, limit=2):
    ads = list(Advertisement.objects.active_for(placement)[:limit])
    if ads:
        Advertisement.objects.filter(id__in=[ad.id for ad in ads]).update(impression_count=F("impression_count") + 1)
        for ad in ads:
            ad.impression_count += 1
    return ads


def _header_counts(user):
    if not user.is_authenticated:
        return {"messages": 0, "notifications": 0}

    unread_messages = Message.objects.filter(conversation__participants=user, read_at__isnull=True).exclude(sender=user).count()
    pending_friends = FriendRequest.objects.filter(to_user=user, status=FriendRequest.Status.PENDING).count()
    received_dating_likes = DatingLike.objects.filter(to_user=user).count()
    post_activity = Comment.objects.filter(post__author=user).exclude(author=user).count()
    return {
        "messages": unread_messages,
        "notifications": unread_messages + pending_friends + received_dating_likes + post_activity,
    }


def _wallet_snapshot(user):
    if not user.is_authenticated:
        return None

    wallet = ensure_wallet(user)
    latest_transactions = list(wallet.transactions.select_related("wallet")[:3])
    monthly_spend = (
        WalletTransaction.objects.filter(
            wallet=wallet,
            status=WalletTransaction.Status.COMPLETED,
            created_at__gte=timezone.now() - timezone.timedelta(days=30),
        )
        .aggregate(total=Sum("amount"))
        .get("total")
        or 0
    )
    return {
        "account": wallet,
        "active_membership": active_membership_for(user),
        "latest_transactions": latest_transactions,
        "monthly_spend": monthly_spend,
    }


def _dating_suggestions(user, limit=6):
    if user.is_authenticated and hasattr(user, "dating_profile"):
        return list(discovery_queryset_for(user)[:limit])

    return list(
        DatingProfile.objects.filter(is_visible=True)
        .select_related("user", "user__profile")
        .prefetch_related("photos")
        .order_by("-is_verified_dating", "-created_at")[:limit]
    )


def _community_suggestions(user, limit=6):
    communities = list(suggested_communities_for(user, limit=limit))
    if communities:
        return communities
    return list(
        Community.objects.filter(privacy=Community.Privacy.PUBLIC)
        .select_related("owner")
        .order_by("-member_count", "-created_at")[:limit]
    )


def _people_suggestions(user, limit=6):
    creators = list(suggested_users_for(user, limit=limit))
    if creators:
        return creators
    return list(Profile.objects.select_related("user").order_by("-follower_count", "-post_count", "-created_at")[:limit])


def _live_preview(user, live_limit=4, featured_limit=4):
    live_now = list(live_now_for(user)[:live_limit])
    featured = list(featured_sessions_for(user)[:featured_limit])
    if featured:
        featured_ids = {item.id for item in featured}
        live_now = sorted(live_now, key=lambda item: (item.id not in featured_ids, -item.viewer_count, -item.starts_at.timestamp()))
    return live_now, featured


def _feed_tabs():
    return [
        {"key": "for_you", "label": "For You", "url": reverse("home"), "state": "live"},
        {"key": "following", "label": "Following", "url": reverse("feed_following"), "state": "native"},
        {"key": "friends", "label": "Friends", "url": reverse("feed_friends"), "state": "native"},
        {"key": "trending", "label": "Trending", "url": reverse("feed_trending"), "state": "native"},
        {"key": "nearby", "label": "Nearby", "url": reverse("feed_nearby"), "state": "native"},
        {"key": "videos", "label": "Videos", "url": reverse("reels_feed"), "state": "native"},
        {"key": "live", "label": "Live", "url": reverse("live_home"), "state": "native"},
    ]


def _quick_actions(user):
    dashboard_posts = reverse("dashboard_posts")
    return [
        {"label": "Post", "icon": "✎", "url": f"{reverse('studio')}?type=text"},
        {"label": "Reel", "icon": "▶", "url": f"{reverse('studio')}?type=reel"},
        {"label": "Story", "icon": "◎", "url": reverse("story_create")},
        {"label": "Go Live", "icon": "⬤", "url": reverse("live_start")},
        {"label": "Dating", "icon": "♡", "url": reverse("dating")},
        {"label": "Communities", "icon": "◫", "url": reverse("community_list")},
        {"label": "Wallet", "icon": "¤", "url": reverse("wallet_home")},
        {"label": "Premium", "icon": "★", "url": reverse("wallet_membership")},
        {"label": "Studio", "icon": "◌", "url": reverse("studio")},
        {"label": "Sell", "icon": "▣", "url": reverse("photo_selling")},
        {"label": "Jobs", "icon": "↗", "url": dashboard_posts},
        {"label": "Support", "icon": "?", "url": reverse("support_help")},
    ]


def _composer_actions(user):
    return [
        {"label": "Photo", "url": f"{reverse('studio')}?type=photo"},
        {"label": "Video", "url": f"{reverse('studio')}?type=video"},
        {"label": "Reel", "url": f"{reverse('studio')}?type=reel"},
        {"label": "Story", "url": reverse("story_create")},
        {"label": "Live", "url": reverse("live_start")},
        {"label": "Flyer", "url": f"{reverse('studio')}?type=flyer"},
    ]


def _system_promos(user, wallet_snapshot, limit=4):
    stored = list(SystemPromoCard.objects.filter(is_active=True, placement=SystemPromoCard.Placement.HOMEPAGE_FEED)[:limit])
    if stored:
        return [
            {
                "title": item.title,
                "body": item.body,
                "icon": item.icon or "★",
                "cta_label": item.cta_label,
                "url": item.cta_url or reverse("support_help"),
                "dismissible": item.dismissible,
            }
            for item in stored
        ]

    prompts = []
    if not user.is_authenticated:
        prompts.append({
            "title": "Create your Namvibe account",
            "body": "Set up your profile, drop your first story, and join live rooms in minutes.",
            "icon": "◎",
            "cta_label": "Sign up",
            "url": reverse("signup"),
            "dismissible": True,
        })
    if user.is_authenticated and not hasattr(user, "dating_profile"):
        prompts.append({
            "title": "Create your dating profile and meet your match",
            "body": "Appear in discovery with privacy-safe public details and start matching.",
            "icon": "♡",
            "cta_label": "Set up dating",
            "url": reverse("dating_profile_edit"),
            "dismissible": True,
        })
    prompts.append({
        "title": "Did you know you can earn money with Namvibe Studio?",
        "body": "Publish reels, flyers, premium content, and creator promos from one studio flow.",
        "icon": "◌",
        "cta_label": "Open studio",
        "url": reverse("studio"),
        "dismissible": True,
    })
    prompts.append({
        "title": "Go live and receive gifts",
        "body": "Host public or premium live rooms and grow your creator earnings through gifts and access sales.",
        "icon": "⬤",
        "cta_label": "Start live",
        "url": reverse("live_start"),
        "dismissible": True,
    })
    if wallet_snapshot and not wallet_snapshot["active_membership"]:
        prompts.append({
            "title": "Upgrade to Premium to unlock more reach",
            "body": "Premium unlocks stronger creator access, trust signals, and call/video shortcuts.",
            "icon": "★",
            "cta_label": "See plans",
            "url": reverse("wallet_membership_plans"),
            "dismissible": True,
        })
    prompts.append({
        "title": "Run an ad and promote your business",
        "body": "Launch promotions, sponsor feed placements, and show up across Namvibe discovery surfaces.",
        "icon": "↗",
        "cta_label": "Open promotions",
        "url": reverse("ads_starter"),
        "dismissible": True,
    })
    return prompts[:limit]


def _mixed_feed(posts, reels, live_sessions, communities, dating_profiles, wallet_snapshot, ads, promos):
    modules = []
    reels_by_id = {post.id: post for post in reels}
    post_bucket = list(posts)
    lead_candidates = []
    if post_bucket:
        first_post = post_bucket.pop(0)
        lead_candidates.append({"kind": "reel" if first_post.id in reels_by_id else "post", "post": first_post})
    if live_sessions:
        lead_candidates.append({"kind": "live", "session": live_sessions[0]})
    if promos:
        lead_candidates.append({"kind": "promo", "promo": promos[0]})
    if communities:
        lead_candidates.append({"kind": "community", "community": communities[0]})
    if dating_profiles:
        lead_candidates.append({"kind": "dating", "profile": dating_profiles[0]})
    if wallet_snapshot:
        lead_candidates.append({"kind": "wallet", "wallet": wallet_snapshot})
    if ads:
        lead_candidates.append({"kind": "ad", "ad": ads[0]})
    modules.extend(lead_candidates[:4])

    cycle = []
    for post in post_bucket:
        cycle.append({"kind": "reel" if post.id in reels_by_id else "post", "post": post})
    cycle.extend({"kind": "live", "session": session} for session in live_sessions[1:3])
    cycle.extend({"kind": "community", "community": community} for community in communities[1:3])
    cycle.extend({"kind": "dating", "profile": profile} for profile in dating_profiles[1:3])
    cycle.extend({"kind": "promo", "promo": promo} for promo in promos[1:3])
    cycle.extend({"kind": "ad", "ad": ad} for ad in ads[1:3])

    inserts = [1, 3, 5, 7]
    for idx, item in enumerate(cycle):
        insert_at = inserts[idx] if idx < len(inserts) else len(modules)
        modules.insert(min(insert_at, len(modules)), item)

    if not modules:
        return [
            {
                "kind": "promo",
                "promo": {
                    "title": "Namvibe is ready for your first update",
                    "body": "Add a story, post a reel, or explore creators and communities from the menu to bring the feed to life.",
                    "cta_label": "Open Studio",
                    "url": reverse("studio"),
                    "dismissible": False,
                },
            }
        ]
    return modules[:18]


def homepage_context(request):
    user = request.user
    public_posts = (
        Post.objects.filter(status=Post.Status.PUBLISHED, audience=Post.Audience.PUBLIC, published_at__isnull=False)
        .select_related("author", "author__profile", "community")
        .prefetch_related("media", "poll__options")
    )
    ranked_posts = FeedRankingService(user).rank(public_posts, limit=80)
    primary_posts = ranked_posts[:10]
    reel_preview = [post for post in ranked_posts if post.post_type in {Post.PostType.REEL, Post.PostType.VIDEO}][:6]
    active_stories = StoryItem.objects.visible_to(user)
    live_now, featured_live = _live_preview(user)
    story_rail = story_rail_for(user, limit=18)
    live_author_ids = {session.host_id for session in live_now}
    for item in story_rail:
        item["is_live"] = item["author"].id in live_author_ids
    communities = _community_suggestions(user)
    creators = _people_suggestions(user)
    dating_profiles = _dating_suggestions(user)
    wallet_snapshot = _wallet_snapshot(user)
    header_counts = _header_counts(user)
    top_ads = _active_ads(Advertisement.Placement.HOMEPAGE_TOP, 1)
    mid_ads = _active_ads(Advertisement.Placement.HOMEPAGE_MID, 3)
    sidebar_ads = _active_ads(Advertisement.Placement.HOMEPAGE_SIDEBAR, 2)
    promos = _system_promos(user, wallet_snapshot)
    membership_plans = list(MembershipPlan.objects.filter(is_active=True).order_by("price", "name")[:3])

    current_profile = getattr(user, "profile", None) if user.is_authenticated else None
    following_count = Follow.objects.filter(follower=user).count() if user.is_authenticated else 0
    friend_count = Match.objects.filter(Q(user_one=user) | Q(user_two=user), is_active=True).count() if user.is_authenticated else 0
    conversations = list(conversations_for_user(user)[:5]) if user.is_authenticated else []
    top_conversation = conversations[0] if conversations else None
    messages_url = (
        _dashboard_section_url("messages", conversation=top_conversation.pk)
        if top_conversation
        else _dashboard_section_url("messages")
    )

    return {
        "story_rail": story_rail,
        "quick_actions": _quick_actions(user),
        "composer_actions": _composer_actions(user),
        "feed_tabs": _feed_tabs(),
        "mixed_feed": _mixed_feed(primary_posts, reel_preview, live_now, communities, dating_profiles, wallet_snapshot, mid_ads, promos),
        "floating_promos": [promo for promo in promos if promo.get("dismissible")][:2],
        "featured_live": featured_live,
        "live_preview": live_now,
        "communities": communities,
        "creators": creators,
        "dating_suggestions": dating_profiles,
        "wallet_snapshot": wallet_snapshot,
        "top_ads": top_ads,
        "sidebar_ads": sidebar_ads,
        "trending_tags": trending_hashtags(10),
        "reel_preview": reel_preview,
        "membership_plans": membership_plans,
        "current_profile": current_profile,
        "following_count": following_count,
        "friend_count": friend_count,
        "total_members": User.objects.count(),
        "total_posts": Post.objects.filter(status=Post.Status.PUBLISHED, audience=Post.Audience.PUBLIC).count(),
        "total_live": len(live_now),
        "total_stories": active_stories.count(),
        "nav_notification_count": header_counts["notifications"],
        "nav_message_count": header_counts["messages"],
        "nav_messages_url": messages_url,
        "nav_wallet_url": reverse("wallet_home"),
        "nav_profile_url": _safe_profile_url(user) if user.is_authenticated else reverse("login"),
        "nav_profile_label": (current_profile.display_name or current_profile.username) if current_profile else "Guest",
        "nav_search_placeholder": "Search people, communities, creators, and live rooms",
        "profile_url": _safe_profile_url(user) if user.is_authenticated else reverse("login"),
        "messages_url": messages_url,
        "notifications_url": reverse("notifications"),
        "wallet_url": reverse("wallet_home"),
        "premium_url": reverse("wallet_membership"),
        "jobs_url": reverse("dashboard_posts"),
        "discover_url": reverse("discover"),
        "nearby_url": reverse("feed_nearby"),
        "now": timezone.now(),
    }
