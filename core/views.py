from django.shortcuts import render
from posts.supabase_posts import get_public_posts

def index(request):
    posts = get_public_posts(limit=6)
    if not isinstance(posts, list):
        posts = []

    return render(request, "core/home_production.html", {
        "posts": posts
    })
