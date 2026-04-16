from django.shortcuts import render
try:
    from posts.supabase_posts import get_public_posts
except Exception:
    def get_public_posts(*args, **kwargs):
        return []

def index(request):
    posts = []
    try:
        resp = get_public_posts(limit=12)
        if resp.ok:
            posts = resp.json()
    except Exception as e:
        print("PUBLIC FEED ERROR:", e)

    return render(request, "core/index.html", {"public_posts": posts})
