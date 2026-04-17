from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import StoryCreateForm
from .models import StoryItem, StoryReaction
from .services import add_story_comment, can_view_story, mark_story_viewed, share_story, toggle_story_like, visible_stories_for


@login_required(login_url="login")
def create_story_view(request):
    form = StoryCreateForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        story = form.save(commit=False)
        story.author = request.user
        story.save()
        messages.success(request, "Story published.")
        return redirect("story_detail", id=story.id)
    return render(request, "stories/create.html", {"form": form})


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
        {"story": story, "previous_story": previous_story, "next_story": next_story, "comments": story.comments.all()},
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


@require_http_methods(["POST"])
def story_view_view(request, id):
    story = get_object_or_404(StoryItem, id=id)
    if not request.session.session_key:
        request.session.save()
    view = mark_story_viewed(request.user, story, request.session.session_key)
    if not view:
        return HttpResponseForbidden("You cannot view this story.")
    return JsonResponse({"ok": True, "view_count": StoryItem.objects.get(pk=story.pk).view_count})
