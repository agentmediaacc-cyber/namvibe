import logging

from django.shortcuts import render

from .homepage import fallback_homepage_context, homepage_context

logger = logging.getLogger(__name__)


def _safe_homepage_payload(request):
    try:
        return homepage_context(request)
    except Exception as exc:
        logger.exception("Homepage context failed with %s", exc.__class__.__name__)
        return fallback_homepage_context(request, str(exc))


def index(request):
    context = _safe_homepage_payload(request)
    return render(request, "core/home_production.html", context)


def feed_view(request):
    return render(request, "core/feed.html", {"feed_tab": "for_you"})


def feed_following_view(request):
    return render(request, "core/feed.html", {"feed_tab": "following"})


def feed_friends_view(request):
    return render(request, "core/feed.html", {"feed_tab": "friends"})


def feed_trending_view(request):
    return render(request, "core/feed.html", {"feed_tab": "trending"})


def feed_nearby_view(request):
    return render(request, "core/feed.html", {"feed_tab": "nearby"})


def feed_videos_view(request):
    return render(request, "core/feed.html", {"feed_tab": "videos"})


def feed_live_view(request):
    return render(request, "core/feed.html", {"feed_tab": "live"})


def feed_sponsored_view(request):
    return render(request, "core/feed.html", {"feed_tab": "sponsored"})


def discover_view(request):
    q = request.GET.get("q", "").strip()
    return render(request, "core/discover.html", {"query": q})


def discover_search_view(request):
    q = request.GET.get("q", "").strip()
    return render(request, "core/discover.html", {"query": q})


def studio_view(request):
    return render(request, "core/studio.html")


def dating_view(request):
    return render(request, "core/dating.html")


def live_home_view(request):
    return render(request, "core/live_home.html")


def pink_friday_view(request):
    context = _safe_homepage_payload(request)
    return render(request, "core/pink_friday.html", context)


def games_view(request):
    context = _safe_homepage_payload(request)
    return render(request, "core/games_home.html", context)


def live_shows_view(request):
    context = _safe_homepage_payload(request)
    return render(request, "core/live_shows.html", context)


def dating_live_match_view(request):
    context = _safe_homepage_payload(request)
    return render(request, "core/dating_live_match.html", context)
