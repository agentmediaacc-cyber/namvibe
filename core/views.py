from django.shortcuts import render
from posts.supabase_posts import get_public_posts

def index(request):
    posts = []
    try:
        resp = get_public_posts(limit=12)
        if resp.ok:
            posts = resp.json()
    except Exception as e:
        print("PUBLIC FEED ERROR:", e)

    return render(request, "core/index.html", {"public_posts": posts})
