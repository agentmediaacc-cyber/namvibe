from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from messaging.services import get_or_create_direct_conversation
from .forms import DatingPreferenceForm, DatingProfileForm
from .models import DatingLike, DatingPass, DatingProfile, Match
from .services import discovery_queryset_for, like_user, matches_for, pass_user


def _dashboard_messages_url(conversation):
    return f"{reverse('user_dashboard')}?section=messages&conversation={conversation.pk}"


def dating_home_view(request):
    if not request.user.is_authenticated:
        return render(request, "dating/home.html")
    if not hasattr(request.user, "dating_profile"):
        return redirect("dating_profile_edit")
    return redirect("dating_discover")


@login_required(login_url="login")
def dating_profile_edit_view(request):
    profile = getattr(request.user, "dating_profile", None)
    form = DatingProfileForm(request.POST or None, request.FILES or None, instance=profile, user=request.user)
    preference = getattr(profile, "preferences", None) if profile else None
    preference_form = DatingPreferenceForm(request.POST or None, instance=preference, prefix="pref")
    if request.method == "POST" and form.is_valid() and preference_form.is_valid():
        dating_profile = form.save()
        pref = preference_form.save(commit=False)
        pref.dating_profile = dating_profile
        pref.save()
        messages.success(request, "Dating profile saved.")
        return redirect("dating_profile_detail", username=request.user.profile.username)
    return render(request, "dating/profile_form.html", {"form": form, "preference_form": preference_form, "dating_profile": profile})


@login_required(login_url="login")
def dating_discover_view(request):
    if not hasattr(request.user, "dating_profile"):
        messages.info(request, "Create your dating profile before browsing matches.")
        return redirect("dating_profile_edit")
    profiles = discovery_queryset_for(request.user, request.GET)
    recent_matches = matches_for(request.user)[:4]
    return render(
        request,
        "dating/discover.html",
        {
            "profiles": profiles,
            "primary_profile": profiles[0] if profiles else None,
            "recent_matches": recent_matches,
            "filters": request.GET,
            "gender_choices": DatingProfile.Gender.choices,
            "goal_choices": DatingProfile.RelationshipGoal.choices,
        },
    )


@login_required(login_url="login")
def dating_matches_view(request):
    return render(request, "dating/matches.html", {"matches": matches_for(request.user)})


@login_required(login_url="login")
def dating_likes_view(request):
    sent = DatingLike.objects.filter(from_user=request.user).select_related("to_user", "to_user__profile", "to_user__dating_profile").order_by("-created_at")
    received = DatingLike.objects.filter(to_user=request.user).select_related("from_user", "from_user__profile", "from_user__dating_profile").order_by("-created_at")
    passes = DatingPass.objects.filter(from_user=request.user).select_related("to_user", "to_user__profile").order_by("-created_at")
    return render(request, "dating/likes.html", {"sent_likes": sent, "received_likes": received, "passes": passes})


@login_required(login_url="login")
def dating_profile_detail_view(request, username):
    user = get_object_or_404(get_user_model().objects.select_related("profile"), profile__username__iexact=username)
    profile = get_object_or_404(DatingProfile.objects.select_related("user", "user__profile").prefetch_related("photos"), user=user)
    if not profile.is_visible and user != request.user:
        return HttpResponseForbidden("This dating profile is not visible.")
    liked = DatingLike.objects.filter(from_user=request.user, to_user=user).exists()
    passed = DatingPass.objects.filter(from_user=request.user, to_user=user).exists()
    return render(request, "dating/detail.html", {"dating_profile": profile, "liked": liked, "passed": passed})


@login_required(login_url="login")
@require_POST
def dating_like_view(request, username):
    target = get_object_or_404(get_user_model(), profile__username__iexact=username)
    like, match = like_user(request.user, target)
    if like is None:
        return HttpResponseForbidden("You cannot like this profile.")
    if match:
        messages.success(request, "It's a match.")
        return redirect("dating_matches")
    messages.success(request, "Like sent.")
    return redirect(request.POST.get("next") or "dating_discover")


@login_required(login_url="login")
@require_POST
def dating_pass_view(request, username):
    target = get_object_or_404(get_user_model(), profile__username__iexact=username)
    passed = pass_user(request.user, target)
    if passed is None:
        return HttpResponseForbidden("You cannot pass this profile.")
    messages.success(request, "Profile passed.")
    return redirect(request.POST.get("next") or "dating_discover")


@login_required(login_url="login")
def dating_message_match_view(request, username):
    target = get_object_or_404(get_user_model(), profile__username__iexact=username)
    user_one, user_two = (request.user, target) if request.user.id < target.id else (target, request.user)
    if not Match.objects.filter(user_one=user_one, user_two=user_two, is_active=True).exists():
        return HttpResponseForbidden("You can message after matching.")
    conversation = get_or_create_direct_conversation(request.user, target)
    return redirect(_dashboard_messages_url(conversation))
