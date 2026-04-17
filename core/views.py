from django.shortcuts import redirect, render
from django.urls import reverse

from .homepage import homepage_context
from posts.supabase_posts import count_public_posts, get_public_posts  # compatibility for older tests/imports


def index(request):
    return render(request, "core/home_production.html", homepage_context(request))


def dating_entry_view(request):
    return redirect("discover_people")


def settings_entry_view(request):
    if request.user.is_authenticated:
        return redirect("profile_edit")
    return redirect(f"{reverse('login')}?next={reverse('settings')}")
