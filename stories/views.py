from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import StoryCreateForm
from .models import StoryItem, StoryReaction
from .services import add_story_comment, can_view_story, mark_story_viewed, share_story, story_rail_for, toggle_story_like, visible_stories_for
from wallet.services import active_boost_for_story, active_gifts, premium_badge_for
from posts.services import create_story_report


@login_required(login_url="login")
def stories_home_view(request):
    from accounts.views import _account_shell_context

    profile = request.user.profile
    account_profile = getattr(request.user, "account_profile", None)
    story_groups = story_rail_for(request.user, limit=18)
    recent_stories = list(visible_stories_for(request.user).order_by("-created_at")[:18])
    context = {
        **_account_shell_context(request, profile, account_profile),
        "story_groups": story_groups,
        "recent_stories": recent_stories,
        "account_shell_title": "Stories",
        "account_shell_subtitle": "Short moments, reels, and story updates",
    }
    return render(request, "stories/home.html", context)


@login_required(login_url="login")
def create_story_view(request):
    form_data = request.POST.copy() if request.method == "POST" else None
    files_data = request.FILES.copy() if request.method == "POST" else None

    if form_data is not None:
        if form_data.get("story_kind") and not form_data.get("media_type"):
            form_data["media_type"] = form_data.get("story_kind")
        if form_data.get("content") and not form_data.get("text_content"):
            form_data["text_content"] = form_data.get("content")
        if form_data.get("duration") and not form_data.get("duration_hours"):
            form_data["duration_hours"] = form_data.get("duration")

    if files_data is not None and files_data.get("media") and not files_data.get("file"):
        files_data["file"] = files_data.get("media")

    form = StoryCreateForm(form_data or None, files_data or None)
    if request.method == "POST" and form.is_valid():
        story = form.save(commit=False)
        story.author = request.user
        story.save()
        messages.success(request, "Story published.")
        return redirect("story_detail", id=story.id)
    return render(
        request,
        "stories/create.html",
        {
            "form": form,
            "background_presets": ["midnight", "ember", "aurora", "onyx", "sunrise"],
            "text_presets": ["clean", "headline", "glow", "mono"],
        },
    )


def story_detail_view(request, id):
    story = get_object_or_404(
        StoryItem.objects.select_related("author", "author__profile").prefetch_related("comments__author__profile"),
        id=id,
    )
    if not can_view_story(request.user, story):
        return HttpResponseForbidden("You cannot view this story.")
    if not request.session.session_key:
        request.session.save()
    mark_story_viewed(request.user, story, request.session.session_key)
    siblings = list(visible_stories_for(request.user).filter(author=story.author).order_by("created_at"))
    ids = [item.id for item in siblings]
    index = ids.index(story.id) if story.id in ids else 0
    previous_story = siblings[index - 1] if index > 0 else None
    next_story = siblings[index + 1] if index + 1 < len(siblings) else None
    return render(
        request,
        "stories/detail.html",
        {
            "story": story,
            "previous_story": previous_story,
            "next_story": next_story,
            "comments": story.comments.all(),
            "story_position": index + 1,
            "story_total": len(siblings),
            "story_siblings": siblings,
            "active_story_boost": active_boost_for_story(story),
            "story_author_badge": premium_badge_for(story.author),
            "default_gift": active_gifts().first(),
            "under_review": story.is_hidden_by_moderation,
        },
    )


@login_required(login_url="login")
@require_http_methods(["POST"])
def story_like_view(request, id):
    story = get_object_or_404(StoryItem, id=id)
    reaction_type = request.POST.get("reaction_type") or StoryReaction.ReactionType.LIKE
    if reaction_type not in StoryReaction.ReactionType.values:
        reaction_type = StoryReaction.ReactionType.LIKE
    _, active = toggle_story_like(request.user, story, reaction_type)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        story.refresh_from_db()
        return JsonResponse({"liked": active, "like_count": story.like_count})
    return redirect(request.POST.get("next") or reverse("story_detail", kwargs={"id": story.id}))


@login_required(login_url="login")
@require_http_methods(["POST"])
def story_comment_view(request, id):
    story = get_object_or_404(StoryItem, id=id)
    comment = add_story_comment(request.user, story, request.POST.get("body", ""))
    if not comment:
        return HttpResponseForbidden("You cannot comment on this story.")
    return redirect(request.POST.get("next") or reverse("story_detail", kwargs={"id": story.id}))


@login_required(login_url="login")
@require_http_methods(["POST"])
def story_share_view(request, id):
    story = get_object_or_404(StoryItem, id=id)
    share = share_story(request.user, story, request.POST.get("target", "forward"))
    if not share:
        return HttpResponseForbidden("You cannot share this story.")
    return redirect(request.POST.get("next") or reverse("story_detail", kwargs={"id": story.id}))


@login_required(login_url="login")
@require_http_methods(["POST"])
def story_report_view(request, id):
    from posts.models import Report

    story = get_object_or_404(StoryItem.objects.select_related("author", "author__profile"), id=id)
    if not can_view_story(request.user, story):
        return HttpResponseForbidden("You cannot report this story.")
    reason = request.POST.get("reason") or Report.Reason.OTHER
    if reason not in Report.Reason.values:
        reason = Report.Reason.OTHER
    details = (request.POST.get("details") or "").strip()
    details = f"Story #{story.id}: {details}".strip()
    create_story_report(request.user, story=story, reason=reason, details=details)
    messages.success(request, "Story report submitted.")
    return redirect(request.POST.get("next") or reverse("story_detail", kwargs={"id": story.id}))


@require_http_methods(["POST"])
def story_view_view(request, id):
    story = get_object_or_404(StoryItem, id=id)
    if not request.session.session_key:
        request.session.save()
    view = mark_story_viewed(request.user, story, request.session.session_key)
    if not view:
        return HttpResponseForbidden("You cannot view this story.")
    return JsonResponse({"ok": True, "view_count": StoryItem.objects.get(pk=story.pk).view_count})


@login_required(login_url="login")
def story_viewers_view(request, id):
    story = get_object_or_404(StoryItem, id=id, author=request.user)
    viewers = story.views.select_related("viewer", "viewer__profile").order_by("-created_at")
    one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
    return render(request, "stories/viewers.html", {"story": story, "viewers": viewers, "one_hour_ago": one_hour_ago})
