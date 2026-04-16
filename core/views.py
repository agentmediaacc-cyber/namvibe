from django.shortcuts import render

def get_public_posts(*args, **kwargs):
    try:
        from posts.supabase_posts import get_public_posts as real_func
        result = real_func(*args, **kwargs)
        if isinstance(result, list):
            return result
        return []
    except Exception:
        return []

def index(request):
    posts = []
    try:
        posts = get_public_posts(limit=12)
        if not isinstance(posts, list):
            posts = []
    except Exception as e:
        print("PUBLIC FEED ERROR:", e)
        posts = []

    return render(request, "core/index.html", {"public_posts": posts})
