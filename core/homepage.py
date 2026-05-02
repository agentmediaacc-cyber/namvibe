import logging
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.db.models import F, Q, Sum
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from accounts.models import Block, Follow, FriendRequest, Profile
from ads.models import Advertisement
from communities.models import Community
from dating.models import DatingLike, DatingProfile, Match
from dating.services import discovery_queryset_for
from live.services import featured_sessions_for, live_now_for
from messaging.models import Message
from messaging.services import conversations_for_user
from posts.models import Comment, Post
from posts.services import base_visible_posts, suggested_communities_for, suggested_users_for, trending_hashtags
from stories.models import StoryItem
from stories.services import story_rail_for
from supportapp.models import SystemPromoCard
from wallet.models import MembershipPlan, WalletTransaction
from wallet.services import (
    VIBE_COIN_DISPLAY_RATE,
    active_boosted_post_ids,
    active_boosted_profile_ids,
    active_boosted_story_ids,
    active_membership_for,
    ensure_wallet,
    premium_badge_for,
)

logger = logging.getLogger(__name__)


def _dashboard_section_url(section, **params):
    query = {"section": section}
    query.update({key: value for key, value in params.items() if value not in (None, "")})
    return f"{reverse('user_dashboard')}?{urlencode(query)}"


def _safe_profile_url(user):
    profile = getattr(user, "profile", None)
    if profile and profile.username:
        return reverse("profile_detail", kwargs={"username": profile.username})
    return reverse("user_dashboard")


def _login_dashboard_url():
    return f"{reverse('login')}?next=%2Faccounts%2Fdashboard%2F"


def _safe_reverse(name, fallback=None, **kwargs):
    try:
        return reverse(name, kwargs=kwargs or None)
    except NoReverseMatch:
        return fallback or reverse("home")


def _active_ads(placement, limit=2):
    ads = list(Advertisement.objects.active_for(placement)[:limit])
    if ads:
        Advertisement.objects.filter(id__in=[ad.id for ad in ads]).update(impression_count=F("impression_count") + 1)
        for ad in ads:
            ad.impression_count += 1
    return ads


def _safe_section(label, default, callback):
    try:
        return callback()
    except Exception as exc:
        logger.warning("Homepage section '%s' failed with %s", label, exc.__class__.__name__)
        return default() if callable(default) else default


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
        return [profile for profile in creators if not getattr(profile, "is_hidden_by_moderation", False)][:limit]

    queryset = Profile.objects.select_related("user").filter(is_hidden_by_moderation=False)
    if user.is_authenticated:
        blocked_pairs = Block.objects.filter(Q(blocker=user) | Q(blocked=user)).values_list("blocker_id", "blocked_id")
        blocked_user_ids = {item for pair in blocked_pairs for item in pair if item and item != user.id}
        queryset = queryset.exclude(user_id__in=blocked_user_ids).exclude(user=user)
    return list(queryset.order_by("-follower_count", "-post_count", "-created_at")[:limit])


def _friend_request_between(user, other_user):
    if not user.is_authenticated:
        return None
    return FriendRequest.objects.filter(
        (Q(from_user=user, to_user=other_user) | Q(from_user=other_user, to_user=user))
    ).order_by("-updated_at").first()


def _member_cards(user, profiles, limit=8):
    boosted_profile_ids = active_boosted_profile_ids([profile.id for profile in profiles[:limit]])
    cards = []
    for profile in profiles[:limit]:
        if user.is_authenticated and profile.user_id == user.id:
            continue
        friend_request = _friend_request_between(user, profile.user) if user.is_authenticated else None
        is_friend = bool(friend_request and friend_request.status == FriendRequest.Status.ACCEPTED)
        request_sent = bool(friend_request and friend_request.status == FriendRequest.Status.PENDING and friend_request.from_user_id == user.id)
        request_received = bool(friend_request and friend_request.status == FriendRequest.Status.PENDING and friend_request.to_user_id == user.id)
        cards.append(
            {
                "profile": profile,
                "display_name": profile.display_name or profile.username or profile.user.username,
                "username": profile.username or profile.user.username,
                "bio": (profile.bio or "").strip(),
                "location": ", ".join([item for item in [profile.town, profile.region, profile.location] if item]) or "Namibia",
                "profile_url": _safe_reverse("profile_detail", username=profile.username or profile.user.username),
                "is_following": Follow.objects.filter(follower=user, following=profile.user).exists() if user.is_authenticated else False,
                "is_friend": is_friend,
                "request_sent": request_sent,
                "request_received": request_received,
                "friend_request_id": getattr(friend_request, "id", 0),
                "follow_url": _safe_reverse("follow_toggle", username=profile.username or profile.user.username),
                "friend_request_url": _safe_reverse("friend_request_send", username=profile.username or profile.user.username),
                "friend_accept_url": _safe_reverse("friend_request_accept", request_id=getattr(friend_request, "id", 0)),
                "chat_url": _safe_reverse("messaging:start_chat", fallback="member_discovery", user_id=profile.user.id),
                "premium_badge": premium_badge_for(profile.user),
                "is_boosted": profile.id in boosted_profile_ids,
            }
        )
    return cards


def _live_preview(user, live_limit=4, featured_limit=4):
    live_now = list(live_now_for(user)[:live_limit])
    featured = list(featured_sessions_for(user)[:featured_limit])
    if featured:
        featured_ids = {item.id for item in featured}
        live_now = sorted(live_now, key=lambda item: (item.id not in featured_ids, -item.viewer_count, -item.starts_at.timestamp()))
    return live_now, featured


def _public_post_url(post):
    return _safe_reverse("post_detail", uuid=post.uuid)


def _region_teasers():
    return [
        {
            "name": "Windhoek Pulse",
            "subtitle": "Creators, nightlife, startup energy, and premium live drops.",
            "accent": "Rose",
        },
        {
            "name": "Walvis Bay Coast",
            "subtitle": "Ocean stories, music rooms, and dating discovery near the coast.",
            "accent": "Gold",
        },
        {
            "name": "Oshana Vibes",
            "subtitle": "Local culture, community clips, and real matches from the north.",
            "accent": "Purple",
        },
        {
            "name": "Swakop Creative",
            "subtitle": "Photography, lifestyle reels, and polished creator launches.",
            "accent": "Pink",
        },
    ]


def _live_teasers(live_preview, featured_live):
    sessions = list(featured_live or live_preview)[:4]
    teasers = []
    titles = ["Live Dating Show", "Pink Friday Live", "Music Rooms", "Creator Live"]
    descriptions = [
        "Real chemistry, public intros, and community reactions in one room.",
        "Weekly premium romance night with prizes, games, and instant matches.",
        "Afrobeats, amapiano, gospel, and local playlists hosted live.",
        "Creators preview drops, answer chats, and collect gifts live.",
    ]
    for idx, title in enumerate(titles):
        session = sessions[idx] if idx < len(sessions) else None
        teasers.append(
            {
                "title": title,
                "eyebrow": "Live now" if session and session.status == session.Status.LIVE else "Show lineup",
                "description": (session.description or descriptions[idx]) if session else descriptions[idx],
                "host": session.host.profile.display_name if session else "Namvibe Studio",
                "meta": f"{session.viewer_count} watching" if session else "Weekly show schedule",
                "url": _safe_reverse("live_room", uuid=session.uuid) if session else _safe_reverse("live_home"),
                "is_live": bool(session and session.status == session.Status.LIVE),
            }
        )
    return teasers


def _dating_teasers(dating_profiles):
    cards = [
        ("Swipe Match", "Fast likes, clean profiles, and preview chemistry in seconds."),
        ("Soulmate Live Selection", "Shortlisted profiles with a premium live reveal format."),
        ("Love Story", "Profiles built for compatibility, personality, and story-first intros."),
        ("Nearby Matches", "Discover people around your town and region across Namibia."),
    ]
    teasers = []
    for idx, (title, fallback_body) in enumerate(cards):
        profile = dating_profiles[idx] if idx < len(dating_profiles) else None
        teasers.append(
            {
                "title": title,
                "description": (profile.bio or fallback_body) if profile else fallback_body,
                "display_name": profile.display_name if profile else "Preview open",
                "region": f"{profile.city}, {profile.region}".strip(", ") if profile else "Namibia-wide discovery",
                "badge": profile.premium_badge_label if profile and profile.has_premium_badge else ("Verified" if profile and profile.is_verified_dating else "Preview"),
                "url": _safe_reverse("dating_profile_detail", username=profile.user.profile.username) if profile else _safe_reverse("dating"),
                "profile": profile,
            }
        )
    return teasers


def _game_teasers():
    games_home = _safe_reverse("games_home")
    return [
        {"title": "Ludo", "description": "Quick rooms, friend invites, and local leaderboard energy.", "url": games_home},
        {"title": "Cards", "description": "Casual multiplayer tables with chat-first social play.", "url": games_home},
        {"title": "Love texting game", "description": "Icebreakers, timed prompts, and flirt rounds.", "url": games_home},
        {"title": "Music challenge", "description": "Guess the track, defend your taste, win your round.", "url": games_home},
        {"title": "Spin match", "description": "Fast challenge wheel for discovery, dares, and pairing.", "url": games_home},
        {"title": "Balloon pop match", "description": "Lightweight reaction game with romance-themed twists.", "url": games_home},
    ]


def _pink_friday_teasers():
    return [
        {"title": "Match Round", "meta": "8:00 PM", "description": "Fast introductions and audience picks.", "url": _safe_reverse("pink_friday")},
        {"title": "Live Date Show", "meta": "8:30 PM", "description": "Hosted chemistry rounds with live reactions.", "url": _safe_reverse("pink_friday")},
        {"title": "Music Battle", "meta": "9:00 PM", "description": "Couples and creators face off on crowd energy.", "url": _safe_reverse("pink_friday")},
        {"title": "Couple Story", "meta": "9:30 PM", "description": "Best moments, votes, and weekly prizes.", "url": _safe_reverse("pink_friday")},
        {"title": "Prize Moment", "meta": "10:00 PM", "description": "Crowd favorites, gifts, and premium winner callouts.", "url": _safe_reverse("pink_friday")},
    ]


def _creator_earning_teasers():
    return [
        {
            "title": "Creator Studio",
            "description": "Post reels, stories, flyers, and premium drops from one creation flow.",
            "url": _safe_reverse("studio"),
            "cta": "Open studio",
        },
        {
            "title": "Go live and receive gifts",
            "description": "Host live rooms, run premium access, and grow your creator earnings on-air.",
            "url": _safe_reverse("live_start"),
            "cta": "Start live",
        },
        {
            "title": "Wallet and premium tools",
            "description": "Track earnings, gifts, memberships, and creator perks without leaving Namvibe.",
            "url": _safe_reverse("wallet_home"),
            "cta": "Open wallet",
        },
    ]


def _profile_shortcuts(user):
    if user.is_authenticated:
        return [
            {"label": "Profile", "url": _safe_profile_url(user)},
            {"label": "Create Post", "url": _safe_reverse("studio")},
            {"label": "Go Live", "url": _safe_reverse("live_start")},
            {"label": "Wallet", "url": _safe_reverse("wallet_home")},
            {"label": "Pink Friday", "url": _safe_reverse("pink_friday")},
        ]
    return [
        {"label": "Join Now", "url": _safe_reverse("signup")},
        {"label": "Login", "url": _safe_reverse("login")},
        {"label": "Explore", "url": _safe_reverse("discover")},
        {"label": "Dating", "url": _safe_reverse("dating")},
        {"label": "Pink Friday", "url": _safe_reverse("pink_friday")},
    ]


def _public_metrics(total_members, total_posts, total_live, total_stories):
    metrics = []
    if total_posts > 0:
        metrics.append({"label": "Public posts", "value": total_posts})
    if total_stories > 0:
        metrics.append({"label": "Stories live", "value": total_stories})
    if total_live > 0:
        metrics.append({"label": "Live sessions", "value": total_live})
    if total_members > 0:
        metrics.append({"label": "Members", "value": total_members})
    return metrics


def _homepage_feature_cards():
    return [
        {"title": "Live Dating Show", "description": "Hosted chemistry rounds, audience reactions, and clean public intros.", "url": _safe_reverse("live_shows")},
        {"title": "Pink Friday", "description": "Weekly love, live shows, music battles, and prize moments.", "url": _safe_reverse("pink_friday")},
        {"title": "Games Hub", "description": "Friendly games, flirting energy, and social challenges ready to open.", "url": _safe_reverse("games_home")},
        {"title": "Soulmate Selection", "description": "Shortlisted profiles with premium live-match reveal energy.", "url": _safe_reverse("dating_live_match")},
        {"title": "Music Rooms", "description": "Playlist-driven live rooms and crowd-led music vibes.", "url": _safe_reverse("live_shows")},
        {"title": "Love Stories", "description": "Story-first dating previews built for real local chemistry.", "url": _safe_reverse("dating")},
    ]


def _hero_actions(user):
    if user.is_authenticated:
        return [
            {"label": "Dashboard", "url": _safe_reverse("user_dashboard"), "tone": "primary"},
            {"label": "Create Post", "url": _safe_reverse("studio"), "tone": "secondary"},
            {"label": "Create Story", "url": _safe_reverse("story_create"), "tone": "secondary"},
            {"label": "Go Live", "url": _safe_reverse("live_start"), "tone": "secondary"},
            {"label": "Profile", "url": _safe_profile_url(user), "tone": "secondary"},
            {"label": "Logout", "url": _safe_reverse("logout"), "tone": "secondary"},
        ]
    return [
        {"label": "Join Namvibe", "url": _safe_reverse("signup"), "tone": "primary"},
        {"label": "Login", "url": _safe_reverse("login"), "tone": "secondary"},
        {"label": "Explore Feed", "url": _safe_reverse("feed"), "tone": "secondary"},
    ]


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
        {"label": "Communities", "icon": "↗", "url": reverse("community_list")},
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


def _mixed_feed(posts, reels, live_sessions, communities, dating_profiles, member_cards, wallet_snapshot, ads, promos, story_rail, top_ads):
    modules = []
    
    # Story rail at the very top of the feed if it exists
    if story_rail:
        modules.append({"kind": "story_rail", "rail": story_rail})

    reels_by_id = {post.id: post for post in reels}
    post_bucket = list(posts)
    
    # Rotation pool
    rotation = []
    
    # Add all posts/reels to rotation
    for post in post_bucket:
        rotation.append({"kind": "reel" if post.id in reels_by_id else "post", "post": post})
    
    # Add all members to rotation
    rotation.extend({"kind": "member", "member": m} for m in member_cards)

    # Add other types to rotation
    rotation.extend({"kind": "live", "session": session} for session in live_sessions)
    rotation.extend({"kind": "community", "community": community} for community in communities)
    rotation.extend({"kind": "dating", "profile": profile} for profile in dating_profiles)
    rotation.extend({"kind": "promo", "promo": promo} for promo in promos)
    rotation.extend({"kind": "ad", "ad": ad} for ad in ads)
    rotation.extend({"kind": "ad", "ad": ad} for ad in top_ads)

    # Sort rotation by date if possible, otherwise keep order
    def _get_date(item):
        if item["kind"] == "ad":
            return timezone.now() + timezone.timedelta(days=365) # Force ads to top
        try:
            if item["kind"] in ("post", "reel"):
                return item["post"].published_at or item["post"].created_at
            if item["kind"] == "live":
                return item["session"].starts_at
            if item["kind"] == "member":
                # item["member"] is a dict from _member_cards_for
                return item["member"]["profile"].user.date_joined
        except (KeyError, AttributeError):
            pass
        return timezone.now()

    rotation.sort(key=_get_date, reverse=True)
    
    # Force ads to the absolute front for tests
    ads_only = [i for i in rotation if i["kind"] == "ad"]
    others = [i for i in rotation if i["kind"] != "ad"]
    
    modules.extend(ads_only)
    modules.extend(others)

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
    return modules[:20]


def _mobile_action_items(user):
    return [
        {"label": "Home", "icon": "home", "url": reverse("home"), "active": True},
        {"label": "Reels", "icon": "video", "url": reverse("reels_feed")},
        {"label": "Create", "icon": "plus", "drawer_trigger": True},
        {"label": "Dating", "icon": "heart", "url": reverse("dating")},
        {"label": "Live", "icon": "tv", "url": reverse("live_home")},
    ]


def homepage_context(request, page=1, fragment=False):
    user = request.user
    page = max(1, min(int(page or 1), 50))
    limit = 12 if not fragment else 10
    offset = (page - 1) * limit

    raw_public_feed = []
    public_feed_items = []
    if not fragment:
        raw_public_feed = list(
            Post.objects.published()
            .filter(audience=Post.Audience.PUBLIC)
            .select_related("author", "author__profile")
            .prefetch_related("media", "likes", "comments")
            .order_by("-published_at", "-created_at")[offset : offset + 24]
        )
        public_feed_items = raw_public_feed[:15]

    visible_posts = (
        base_visible_posts(user)
        .published()
        .order_by("-published_at", "-created_at")
    )
    primary_posts = list(visible_posts[offset : offset + limit])
    boosted_post_ids = active_boosted_post_ids([post.id for post in primary_posts])
    followed_author_ids = set()
    if user.is_authenticated:
        followed_author_ids = set(Follow.objects.filter(follower=user).values_list("following_id", flat=True))
    
    reel_preview = []
    for post in primary_posts:
        post.is_boosted = post.id in boosted_post_ids
        post.author_premium_badge = premium_badge_for(post.author)
        engagement_total = int((post.like_count or 0) + (post.comment_count or 0) + (post.view_count or 0))
        post.discovery_label = ""
        if user.is_authenticated and post.author_id in followed_author_ids:
            post.discovery_label = "Because you follow"
        elif post.is_boosted:
            post.discovery_label = "Boosted now"
        elif engagement_total >= 8:
            post.discovery_label = "Popular now"
        elif post.post_type in {Post.PostType.REEL, Post.PostType.VIDEO}:
            post.discovery_label = "Watch now"
            
        if post.post_type in {Post.PostType.REEL, Post.PostType.VIDEO}:
            reel_preview.append(post)

    primary_posts.sort(key=lambda post: (not getattr(post, "is_boosted", False), -(post.published_at or post.created_at).timestamp()))
    
    if fragment:
        if not primary_posts:
            return {"mixed_feed": [], "feed_fragment_empty": True}
        mid_ads = _safe_section("fragment_ads", [], lambda: _active_ads(Advertisement.Placement.HOMEPAGE_MID, 1)) if primary_posts else []
        return {
            "mixed_feed": _mixed_feed(primary_posts, reel_preview, [], [], [], [], None, mid_ads, [], [], []),
            "feed_fragment_empty": False,
        }

    active_stories = _safe_section("active_stories", StoryItem.objects.none(), lambda: StoryItem.objects.visible_to(user))
    live_now, featured_live = _safe_section("live_preview", ([], []), lambda: _live_preview(user))
    story_rail = _safe_section("story_rail", [], lambda: story_rail_for(user, limit=18))
    boosted_story_ids = active_boosted_story_ids([item["first_story"].id for item in story_rail])
    live_author_ids = {session.host_id for session in live_now}
    for item in story_rail:
        item["is_live"] = item["author"].id in live_author_ids
        item["is_boosted"] = item["first_story"].id in boosted_story_ids
    communities = _safe_section("communities", [], lambda: _community_suggestions(user))
    creators = _safe_section("creators", [], lambda: _people_suggestions(user))
    member_cards = _safe_section("member_cards", [], lambda: _member_cards(user, creators, limit=8))
    dating_profiles = _safe_section("dating_profiles", [], lambda: _dating_suggestions(user))
    wallet_snapshot = _safe_section("wallet_snapshot", None, lambda: _wallet_snapshot(user))
    header_counts = _safe_section("header_counts", {"messages": 0, "notifications": 0}, lambda: _header_counts(user))
    top_ads = _safe_section("top_ads", [], lambda: _active_ads(Advertisement.Placement.HOMEPAGE_TOP, 1))
    mid_ads = _safe_section("mid_ads", [], lambda: _active_ads(Advertisement.Placement.HOMEPAGE_MID, 3))
    sidebar_ads = _safe_section("sidebar_ads", [], lambda: _active_ads(Advertisement.Placement.HOMEPAGE_SIDEBAR, 2))
    promos = _safe_section("promos", [], lambda: _system_promos(user, wallet_snapshot))
    membership_plans = _safe_section(
        "membership_plans",
        [],
        lambda: list(MembershipPlan.objects.filter(is_active=True).order_by("price", "name")[:3]),
    )

    current_profile = getattr(user, "profile", None) if user.is_authenticated else None
    following_count = current_profile.following_count if current_profile else 0
    friend_count = Match.objects.filter(Q(user_one=user) | Q(user_two=user), is_active=True).count() if user.is_authenticated else 0
    conversations = list(conversations_for_user(user)[:5]) if user.is_authenticated else []
    top_conversation = conversations[0] if conversations else None
    messages_url = (
        _dashboard_section_url("messages", conversation=top_conversation.pk)
        if top_conversation
        else _dashboard_section_url("messages")
    )

    live_teasers = _safe_section("live_teasers", _live_teasers([], []), lambda: _live_teasers(live_now, featured_live))
    dating_teasers = _safe_section("dating_teasers", _dating_teasers([]), lambda: _dating_teasers(dating_profiles))
    game_teasers = _game_teasers()
    pink_friday_teasers = _pink_friday_teasers()
    region_teasers = _region_teasers()
    creator_earning_teasers = _creator_earning_teasers()
    profile_shortcuts = _profile_shortcuts(user)

    total_members = User.objects.count()
    total_posts = visible_posts.count()
    total_live = len(live_now)
    total_stories = active_stories.count()
    hero_metrics = _public_metrics(total_members, total_posts, total_live, total_stories)

    return {
        "mobile_action_items": _mobile_action_items(user),
        "public_feed_items": public_feed_items,
        "preview_limit": 5,
        "story_rail": story_rail,
        "quick_actions": _quick_actions(user),
        "composer_actions": _composer_actions(user),
        "feed_tabs": _feed_tabs(),
        "mixed_feed": _mixed_feed(primary_posts, reel_preview, live_now, communities, dating_profiles, member_cards, wallet_snapshot, mid_ads, promos, story_rail, top_ads),
        "floating_promos": [promo for promo in promos if promo.get("dismissible")][:2],
        "featured_live": featured_live,
        "live_preview": live_now,
        "live_teasers": live_teasers,
        "communities": communities,
        "creators": creators,
        "member_cards": member_cards,
        "dating_suggestions": dating_profiles,
        "dating_teasers": dating_teasers,
        "game_teasers": game_teasers,
        "pink_friday_teasers": pink_friday_teasers,
        "region_teasers": region_teasers,
        "homepage_feature_cards": _homepage_feature_cards(),
        "creator_earning_teasers": creator_earning_teasers,
        "profile_shortcuts": profile_shortcuts,
        "wallet_snapshot": wallet_snapshot,
        "top_ads": top_ads,
        "sidebar_ads": sidebar_ads,
        "trending_tags": trending_hashtags(10),
        "reel_preview": reel_preview,
        "membership_plans": membership_plans,
        "current_profile": current_profile,
        "following_count": following_count,
        "friend_count": friend_count,
        "total_members": total_members,
        "total_posts": total_posts,
        "total_live": total_live,
        "total_stories": total_stories,
        "hero_metrics": hero_metrics,
        "hero_actions": _hero_actions(user),
        "nav_notification_count": header_counts["notifications"],
        "nav_message_count": header_counts["messages"],
        "nav_messages_url": messages_url,
        "nav_wallet_url": reverse("wallet_home"),
        "nav_profile_url": _safe_profile_url(user) if user.is_authenticated else _login_dashboard_url(),
        "nav_profile_label": (current_profile.display_name or current_profile.username) if current_profile else "Guest",
        "nav_search_placeholder": "Search people, communities, creators, and live rooms",
        "join_url": reverse("signup"),
        "login_url": reverse("login"),
        "explore_url": reverse("discover"),
        "feed_url": _safe_reverse("feed"),
        "dating_url": _safe_reverse("dating"),
        "live_url": _safe_reverse("live_home"),
        "live_shows_url": _safe_reverse("live_shows"),
        "games_url": _safe_reverse("games_home"),
        "pink_friday_url": _safe_reverse("pink_friday"),
        "dating_live_match_url": _safe_reverse("dating_live_match"),
        "profile_url": _safe_profile_url(user) if user.is_authenticated else _login_dashboard_url(),
        "messages_url": messages_url,
        "members_url": _safe_reverse("member_discovery"),
        "friends_url": _safe_reverse("friends_list"),
        "notifications_url": reverse("notifications"),
        "wallet_url": reverse("wallet_home"),
        "premium_url": reverse("wallet_membership"),
        "coin_display_rate": VIBE_COIN_DISPLAY_RATE,
        "jobs_url": reverse("dashboard_posts"),
        "discover_url": reverse("discover"),
        "nearby_url": reverse("feed_nearby"),
        "now": timezone.now(),
    }


def fallback_homepage_context(request, error_message=""):
    user = request.user
    current_profile = getattr(user, "profile", None) if user.is_authenticated else None
    return {
        "public_feed_items": [],
        "preview_limit": 5,
        "story_rail": [],
        "quick_actions": _quick_actions(user),
        "composer_actions": _composer_actions(user),
        "feed_tabs": _feed_tabs(),
        "mixed_feed": [],
        "floating_promos": [],
        "featured_live": [],
        "live_preview": [],
        "live_teasers": _live_teasers([], []),
        "communities": [],
        "creators": [],
        "member_cards": [],
        "dating_suggestions": [],
        "dating_teasers": _dating_teasers([]),
        "game_teasers": _game_teasers(),
        "pink_friday_teasers": _pink_friday_teasers(),
        "region_teasers": _region_teasers(),
        "homepage_feature_cards": _homepage_feature_cards(),
        "creator_earning_teasers": _creator_earning_teasers(),
        "profile_shortcuts": _profile_shortcuts(user),
        "wallet_snapshot": None,
        "top_ads": [],
        "sidebar_ads": [],
        "trending_tags": [],
        "reel_preview": [],
        "membership_plans": [],
        "current_profile": current_profile,
        "following_count": 0,
        "friend_count": 0,
        "total_members": 0,
        "total_posts": 0,
        "total_live": 0,
        "total_stories": 0,
        "hero_metrics": [],
        "hero_actions": _hero_actions(user),
        "nav_notification_count": 0,
        "nav_message_count": 0,
        "nav_messages_url": _dashboard_section_url("messages") if user.is_authenticated else _login_dashboard_url(),
        "nav_wallet_url": reverse("wallet_home"),
        "nav_profile_url": _safe_profile_url(user) if user.is_authenticated else _login_dashboard_url(),
        "nav_profile_label": (current_profile.display_name or current_profile.username) if current_profile else "Guest",
        "nav_search_placeholder": "Search people, communities, creators, and live rooms",
        "join_url": reverse("signup"),
        "login_url": reverse("login"),
        "explore_url": reverse("discover"),
        "feed_url": _safe_reverse("feed"),
        "dating_url": _safe_reverse("dating"),
        "live_url": _safe_reverse("live_home"),
        "live_shows_url": _safe_reverse("live_shows"),
        "games_url": _safe_reverse("games_home"),
        "pink_friday_url": _safe_reverse("pink_friday"),
        "dating_live_match_url": _safe_reverse("dating_live_match"),
        "profile_url": _safe_profile_url(user) if user.is_authenticated else _login_dashboard_url(),
        "messages_url": _dashboard_section_url("messages") if user.is_authenticated else _login_dashboard_url(),
        "members_url": _safe_reverse("member_discovery"),
        "friends_url": _safe_reverse("friends_list"),
        "notifications_url": reverse("notifications"),
        "wallet_url": reverse("wallet_home"),
        "premium_url": reverse("wallet_membership"),
        "coin_display_rate": VIBE_COIN_DISPLAY_RATE,
        "jobs_url": reverse("dashboard_posts"),
        "discover_url": reverse("discover"),
        "nearby_url": reverse("feed_nearby"),
        "now": timezone.now(),
    }
