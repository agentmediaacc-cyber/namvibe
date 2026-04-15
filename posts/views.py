from django.shortcuts import redirect
from django.contrib import messages
from .forms import PostForm
from .supabase_posts import create_post, save_media_locally

def save_post_view(request):
    if not request.session.get("eharo_user_id"):
        return redirect("login")

    if request.method != "POST":
        return redirect("user_dashboard")

    form = PostForm(request.POST, request.FILES)

    if not form.is_valid():
        messages.error(request, "Post form is invalid.")
        return redirect("user_dashboard")

    media_file = form.cleaned_data.get("media_file")
    media_type = form.cleaned_data.get("media_type") or "text"

    media_url = ""
    if media_file:
        folder = "posts"
        if str(media_type).lower() == "video":
            folder = "videos"
        elif str(media_type).lower() == "photo":
            folder = "photos"
        media_url = save_media_locally(media_file, folder=folder)

    payload = {
        "user_id": request.session.get("eharo_user_id"),
        "full_name": request.session.get("eharo_full_name", ""),
        "username": request.session.get("eharo_username", ""),
        "email": request.session.get("eharo_email", ""),
        "title": form.cleaned_data.get("title", ""),
        "caption": form.cleaned_data.get("caption", ""),
        "audience": form.cleaned_data.get("audience", "Public"),
        "share_to": form.cleaned_data.get("share_to", "Main Feed"),
        "group_name": form.cleaned_data.get("group_name", ""),
        "single_user": form.cleaned_data.get("single_user", ""),
        "background_theme": form.cleaned_data.get("background_theme", "theme-purple"),
        "font_theme": form.cleaned_data.get("font_theme", "font-modern"),
        "crop_style": form.cleaned_data.get("crop_style", "cover"),
        "image_effect": form.cleaned_data.get("image_effect", "none"),
        "video_mode": form.cleaned_data.get("video_mode", "normal"),
        "media_type": media_type,
        "media_url": media_url,
        "allow_comments": bool(form.cleaned_data.get("allow_comments")),
        "allow_share": bool(form.cleaned_data.get("allow_share")),
        "save_story": bool(form.cleaned_data.get("save_story")),
        "premium_badge": bool(form.cleaned_data.get("premium_badge")),
        "status": "published",
    }

    resp = create_post(payload)

    if not resp.ok:
        print("POST SAVE ERROR:", resp.status_code, resp.text)
        messages.error(request, f"Post save failed: {resp.text}")
    else:
        messages.success(request, "Post published successfully.")

    return redirect("user_dashboard")
