from django.shortcuts import render
from .homepage import fallback_homepage_context, homepage_context

def index(request):
    try:
        context = homepage_context(request)
    except Exception as exc:
        context = fallback_homepage_context(request, str(exc))
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
