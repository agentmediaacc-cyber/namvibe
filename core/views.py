from django.shortcuts import render
from django.contrib.auth.models import User
from django.db.models import Count
from django.apps import apps


def _safe_count(model_label):
    try:
        app_label, model_name = model_label.split(".")
        model = apps.get_model(app_label, model_name)
        return model.objects.count()
    except Exception:
        return 0


def _safe_recent(model_label, limit=8, order_fields=None):
    try:
        app_label, model_name = model_label.split(".")
        model = apps.get_model(app_label, model_name)
        qs = model.objects.all()

        if order_fields:
            for field in order_fields:
                try:
                    qs = qs.order_by(field)
                    return list(qs[:limit])
                except Exception:
                    continue

        return list(qs[:limit])
    except Exception:
        return []


def _pick_attr(obj, names, default=""):
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if callable(value):
                try:
                    value = value()
                except Exception:
                    continue
            if value not in [None, ""]:
                return value
    return default


def index(request):
    total_members = User.objects.count()

    total_posts = (
        _safe_count("posts.Post")
        or _safe_count("posts.Posts")
        or _safe_count("core.Post")
    )

    total_live = (
        _safe_count("live.LiveSession")
        or _safe_count("livestream.LiveStream")
        or _safe_count("livestream.Stream")
        or _safe_count("live.Stream")
    )

    total_stories = (
        _safe_count("posts.Story")
        or _safe_count("core.Story")
    )

    recent_posts = (
        _safe_recent("posts.Post", limit=8, order_fields=["-created_at", "-id"])
        or _safe_recent("posts.Posts", limit=8, order_fields=["-created_at", "-id"])
        or []
    )

    live_preview = (
        _safe_recent("livestream.LiveStream", limit=6, order_fields=["-created_at", "-id"])
        or _safe_recent("live.LiveSession", limit=6, order_fields=["-created_at", "-id"])
        or []
    )

    stories = (
        _safe_recent("posts.Story", limit=10, order_fields=["-created_at", "-id"])
        or []
    )

    context = {
        "total_members": total_members,
        "total_posts": total_posts,
        "total_live": total_live,
        "total_stories": total_stories,
        "recent_posts": recent_posts,
        "live_preview": live_preview,
        "stories": stories,
    }
    return render(request, "core/home_production.html", context)
