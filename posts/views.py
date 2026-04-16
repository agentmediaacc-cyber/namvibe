from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from .supabase_posts import get_public_posts, create_post


def _session_user(request):
    user_id = request.session.get("eharo_user_id", "")
    if not user_id:
        return None

    return {
        "user_id": user_id,
        "full_name": request.session.get("eharo_full_name", "Namvibe User"),
        "username": request.session.get("eharo_username", "user"),
        "email": request.session.get("eharo_email", ""),
    }


@require_http_methods(["GET"])
def feed_view(request):
    posts = get_public_posts(limit=50)
    if not isinstance(posts, list):
        posts = []
    return render(request, "posts/feed.html", {"posts": posts})


@require_http_methods(["POST"])
def create_post_view(request):
    user = _session_user(request)
    if not user:
        messages.error(request, "Login required to create a post.")
        return redirect("login")

    content = request.POST.get("content", "").strip()
    media_file = request.FILES.get("media") or request.FILES.get("media_file")

    if content or media_file:
        create_post(
            user_id=user["user_id"],
            full_name=user["full_name"],
            username=user["username"],
            email=user["email"],
            title=content[:120],
            caption=content,
            media_file=media_file,
        )

    return redirect("feed")


@require_http_methods(["POST"])
def save_post_view(request):
    user = _session_user(request)
    if not user:
        messages.error(request, "Login required to create a post.")
        return redirect("login")

    title = request.POST.get("title", "").strip()
    caption = request.POST.get("caption", "").strip()
    media_file = request.FILES.get("media_file") or request.FILES.get("media") or request.FILES.get("flyer_image")

    if title or caption or media_file or request.POST.get("flyer_title", "").strip() or request.POST.get("poll_question", "").strip():
        create_post(
            user_id=user["user_id"],
            full_name=user["full_name"],
            username=user["username"],
            email=user["email"],
            post_type=request.POST.get("post_type", request.POST.get("media_type", "text")),
            title=title,
            caption=caption,
            hashtags=request.POST.get("hashtags", ""),
            tagged_users=request.POST.get("tagged_users", ""),
            audience=request.POST.get("audience", "Public"),
            share_to=request.POST.get("share_to", "Main Feed"),
            group_name=request.POST.get("group_name", ""),
            single_user=request.POST.get("single_user", ""),
            specific_user=request.POST.get("specific_user", ""),
            community_name=request.POST.get("community_name", ""),
            background_theme=request.POST.get("background_theme", "theme-purple"),
            font_theme=request.POST.get("font_theme", "font-modern"),
            crop_style=request.POST.get("crop_style", "cover"),
            image_effect=request.POST.get("image_effect", "none"),
            video_mode=request.POST.get("video_mode", "normal"),
            display_mode=request.POST.get("display_mode", "cover"),
            overlay_text=request.POST.get("overlay_text", ""),
            flyer_background=request.POST.get("flyer_background", "gradient-violet"),
            flyer_text_color=request.POST.get("flyer_text_color", "#ffffff"),
            flyer_layout=request.POST.get("flyer_layout", "centered"),
            flyer_title=request.POST.get("flyer_title", ""),
            flyer_body=request.POST.get("flyer_body", ""),
            flyer_cta=request.POST.get("flyer_cta", ""),
            music_track=request.POST.get("music_track", ""),
            motion_effect=request.POST.get("motion_effect", "none"),
            poll_question=request.POST.get("poll_question", ""),
            poll_options=request.POST.get("poll_options", ""),
            media_type=request.POST.get("media_type", "text"),
            allow_comments="allow_comments" in request.POST,
            allow_share="allow_share" in request.POST,
            save_story="save_story" in request.POST,
            premium_badge="premium_badge" in request.POST,
            save_draft="save_draft" in request.POST,
            media_file=media_file,
        )

    return redirect(f"{reverse('user_dashboard')}?section=posts")
