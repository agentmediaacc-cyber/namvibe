from django.apps import apps
from django.contrib.auth.models import User
from django.db.models import Count, F
from django.utils import timezone

from ads.models import Advertisement
from communities.models import Community
from posts.models import Post
from posts.services import FeedRankingService, suggested_users_for, trending_hashtags
from stories.models import StoryItem
from stories.services import story_rail_for


def _live_preview(limit=4):
    try:
        LiveSession = apps.get_model("live", "LiveSession")
        sessions = list(LiveSession.objects.exclude(status="ended").select_related("host", "host__profile").order_by("-is_featured", "-viewer_count", "-starts_at")[:limit])
        if sessions:
            return sessions
    except Exception:
        pass
    try:
        LiveRoom = apps.get_model("livestream", "LiveRoom")
        return list(LiveRoom.objects.exclude(status="ended").select_related("host").order_by("status", "-created_at")[:limit])
    except Exception:
        return []


def _active_ads(placement, limit=2):
    ads = list(Advertisement.objects.active_for(placement)[:limit])
    if ads:
        Advertisement.objects.filter(id__in=[ad.id for ad in ads]).update(impression_count=F("impression_count") + 1)
        for ad in ads:
            ad.impression_count += 1
    return ads


def homepage_context(request):
    user = request.user
    public_posts = (
        Post.objects.filter(status=Post.Status.PUBLISHED, audience=Post.Audience.PUBLIC, published_at__isnull=False)
        .select_related("author", "author__profile", "community")
        .prefetch_related("media", "poll__options", "comments__author__profile")
    )
    ranked_posts = FeedRankingService(user).rank(public_posts, limit=60)
    reels = [post for post in ranked_posts if post.post_type in {Post.PostType.REEL, Post.PostType.VIDEO}][:8]
    active_stories = StoryItem.objects.visible_to(user)
    communities = Community.objects.filter(privacy=Community.Privacy.PUBLIC).select_related("owner").order_by("-member_count", "-created_at")[:6]
    creators = suggested_users_for(user, limit=6)
    lives = _live_preview()

    return {
        "story_rail": story_rail_for(user),
        "feed_posts": ranked_posts[:15],
        "top_ads": _active_ads(Advertisement.Placement.HOMEPAGE_TOP, 1),
        "mid_ads": _active_ads(Advertisement.Placement.HOMEPAGE_MID, 2),
        "sidebar_ads": _active_ads(Advertisement.Placement.HOMEPAGE_SIDEBAR, 1),
        "live_preview": lives,
        "communities": communities,
        "creators": creators,
        "trending_tags": trending_hashtags(12),
        "reel_preview": reels,
        "total_members": User.objects.count(),
        "total_posts": Post.objects.filter(status=Post.Status.PUBLISHED, audience=Post.Audience.PUBLIC).count(),
        "total_live": len(lives),
        "total_stories": active_stories.count(),
        "now": timezone.now(),
    }
