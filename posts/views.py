from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from .supabase_posts import get_public_posts, create_post

@require_http_methods(["GET"])
def feed_view(request):
    posts = get_public_posts(limit=50)
    if not isinstance(posts, list):
        posts = []
    return render(request, "posts/feed.html", {"posts": posts})

@require_http_methods(["POST"])
def create_post_view(request):
    content = request.POST.get("content", "").strip()
    media_file = request.FILES.get("media")

    author_name = "Namvibe User"
    author_email = "guest@namvibe.local"

    if hasattr(request, "user") and getattr(request.user, "is_authenticated", False):
        author_name = request.user.get_full_name() or request.user.username or "Namvibe User"
        author_email = getattr(request.user, "email", "") or "guest@namvibe.local"

    if content or media_file:
        create_post(
            author_email=author_email,
            author_name=author_name,
            content=content,
            media_file=media_file,
        )

    return redirect("/feed/")
