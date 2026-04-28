from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from messaging.models import Conversation, Message
from messaging.services import get_or_create_direct_conversation
from .forms import DatingPreferenceForm, DatingProfileForm
from .models import DatingLike, DatingPass, DatingProfile, DatingProfileView, Match
from .services import (
    BOOST_COST_COINS,
    SUPER_LIKE_COST_COINS,
    can_send_standard_like,
    coin_balance_for,
    discovery_queryset_for,
    like_user,
    likes_used_today,
    matches_for,
    pass_user,
    boost_cooldown_hours_left,
    purchase_boost,
    purchase_super_like,
    remaining_likes_today,
)


from django.db.models import Q


def _dashboard_messages_url(conversation):
    return f"{reverse('user_dashboard')}?section=messages&conversation={conversation.pk}"


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def onboarding_items_for(user):
    items = []
    progress_steps = 0
    total_steps = 4
    profile = None

    try:
        profile = DatingProfile.objects.filter(user=user).prefetch_related("photos").first()
    except Exception:
        return ([{"label": "Create dating profile", "done": False, "url": reverse("dating_profile")}], 0)

    if profile:
        progress_steps += 1
        items.append({"label": "Create dating profile", "done": True, "url": reverse("dating_profile")})
    else:
        items.append({"label": "Create dating profile", "done": False, "url": reverse("dating_profile")})

    has_bio = bool(profile and profile.bio)
    has_interests = bool(profile and profile.interests)
    has_photo = bool(profile and profile.photos.exists())

    progress_steps += int(has_bio)
    progress_steps += int(has_interests)
    progress_steps += int(has_photo)

    items.extend(
        [
            {"label": "Add a short bio", "done": has_bio, "url": reverse("dating_profile")},
            {"label": "Pick your interests", "done": has_interests, "url": reverse("dating_profile")},
            {"label": "Upload a dating photo", "done": has_photo, "url": reverse("dating_profile")},
        ]
    )

    return items, int((progress_steps / total_steps) * 100)


def _anonymous_dating_context():
    return {
        "onboarding_items": [],
        "onboarding_progress": 0,
        "profile": None,
        "dating_profile": None,
        "coin_balance": None,
        "discovery_profiles": [],
        "suggested_profiles": [],
        "recent_matches": [],
        "likes_count": 0,
        "matches_count": 0,
        "views_count": 0,
        "profile_strength": 0,
        "boost_cost_coins": BOOST_COST_COINS,
        "super_like_cost_coins": SUPER_LIKE_COST_COINS,
        "likes_used_today": 0,
        "remaining_likes_today": 0,
        "super_likes_sent": 0,
        "super_likes_received": 0,
        "boost_hours_left": 0,
        "premium_tier_label": DatingProfile.PremiumTier.FREE.title(),
    }


def _safe_conversation_redirect(request_user, target_user):
    conversation = get_or_create_direct_conversation(request_user, target_user)
    return redirect(_dashboard_messages_url(conversation))


def dating_home_view(request):
    if not request.user.is_authenticated:
        return render(request, "dating/home.html", _anonymous_dating_context())

    profile = getattr(request.user, "dating_profile", None)
    coin_balance = coin_balance_for(request.user)
    onboarding_items, onboarding_progress = onboarding_items_for(request.user)

    likes_count = DatingLike.objects.filter(to_user=request.user).count()
    matches_count = Match.objects.filter(
        Q(user_one=request.user) | Q(user_two=request.user),
        is_active=True
    ).count()

    views_count = 0
    if profile:
        views_count = DatingProfileView.objects.filter(viewed_profile=profile).values("viewer").distinct().count()

    discovery_profiles = discovery_queryset_for(request.user)[:3]
    recent_matches = matches_for(request.user)[:5]

    sent_likes_qs = DatingLike.objects.filter(from_user=request.user)
    received_likes_qs = DatingLike.objects.filter(to_user=request.user)
    super_likes_sent = sent_likes_qs.filter(is_super_like=True).count()
    super_likes_received = received_likes_qs.filter(is_super_like=True).count()
    boost_hours_left = boost_cooldown_hours_left(profile) if profile else 0
    premium_tier_label = profile.get_premium_tier_display() if profile else DatingProfile.PremiumTier.FREE.title()

    profile_strength = profile.completeness_percentage if profile else 0

    form = DatingProfileForm(request.POST or None, request.FILES or None, instance=profile, user=request.user)
    preference = getattr(profile, "preferences", None) if profile else None
    preference_form = DatingPreferenceForm(request.POST or None, instance=preference, prefix="pref")

    if request.method == "POST":
        if form.is_valid() and preference_form.is_valid():
            dating_profile = form.save()
            pref = preference_form.save(commit=False)
            pref.dating_profile = dating_profile
            pref.save()
            messages.success(request, "Dating profile updated.")
            return redirect("dating")

    return render(
        request, 
        "dating/profile.html", 
        {
            "profile": profile,
            "dating_profile": profile,
            "form": form,
            "preference_form": preference_form,
            "onboarding_items": onboarding_items,
            "onboarding_progress": onboarding_progress,
            "likes_count": likes_count,
            "matches_count": matches_count,
            "views_count": views_count,
            "discovery_profiles": discovery_profiles,
            "suggested_profiles": discovery_profiles,
            "profile_strength": profile_strength,
            "recent_matches": recent_matches,
            "coin_balance": coin_balance,
            "boost_cost_coins": BOOST_COST_COINS,
            "super_like_cost_coins": SUPER_LIKE_COST_COINS,
            "likes_used_today": likes_used_today(request.user) if profile else 0,
            "remaining_likes_today": remaining_likes_today(request.user) if profile else 0,
            "super_likes_sent": super_likes_sent,
            "super_likes_received": super_likes_received,
            "boost_hours_left": boost_hours_left,
            "premium_tier_label": premium_tier_label,
        }
    )


@login_required(login_url="login")
def dating_profile_view(request):
    return dating_home_view(request)


@login_required(login_url="login")
def dating_profile_edit_view(request):
    return redirect("dating_profile")


@login_required(login_url="login")
def dating_discover_view(request):
    if not hasattr(request.user, "dating_profile"):
        messages.info(request, "Create your dating profile before browsing matches.")
        return redirect("dating_profile_edit")
    profiles = discovery_queryset_for(request.user, request.GET)
    return render(
        request,
        "dating/discover.html",
        {
            "profiles": profiles,
            "filters": request.GET,
            "coin_balance": coin_balance_for(request.user),
            "super_like_cost_coins": SUPER_LIKE_COST_COINS,
            "can_send_standard_like": can_send_standard_like(request.user),
            "remaining_likes_today": remaining_likes_today(request.user),
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
    return render(
        request,
        "dating/likes.html",
        {
            "sent_likes": sent,
            "received_likes": received,
            "passes": passes,
            "super_like_cost_coins": SUPER_LIKE_COST_COINS,
        },
    )


@login_required(login_url="login")
@require_POST
def dating_boost_view(request):
    profile = getattr(request.user, "dating_profile", None)
    if not profile:
        return redirect("dating")
    result = purchase_boost(request.user)
    if not result["ok"]:
        if result["reason"] == "cooldown":
            messages.info(request, f"Profile already boosted! You can boost again in {result['hours_left']} hours.")
        elif result["reason"] == "insufficient_coins":
            messages.error(request, f"You need {BOOST_COST_COINS} coins to boost your profile.")
        else:
            messages.error(request, "Your dating profile is not ready for boosting yet.")
        return redirect("dating")

    messages.success(request, f"Your profile is now boosted. {BOOST_COST_COINS} coins were deducted.")
    return redirect("dating")


@login_required(login_url="login")
def dating_views_view(request):
    profile = getattr(request.user, "dating_profile", None)
    if not profile:
        return redirect("dating")
    
    # Get unique viewers, most recent first
    from django.db.models import Max
    viewer_ids = DatingProfileView.objects.filter(viewed_profile=profile).values("viewer").annotate(latest_view=Max("created_at")).order_by("-latest_view")
    
    views = []
    for v in viewer_ids:
        view_obj = DatingProfileView.objects.filter(viewed_profile=profile, viewer_id=v['viewer'], created_at=v['latest_view']).select_related("viewer", "viewer__profile", "viewer__dating_profile").first()
        if view_obj:
            views.append(view_obj)
            
    return render(request, "dating/views.html", {"views": views})


@login_required(login_url="login")
def dating_profile_detail_view(request, username):
    user = get_object_or_404(get_user_model().objects.select_related("profile"), profile__username__iexact=username)
    profile = get_object_or_404(DatingProfile.objects.select_related("user", "user__profile").prefetch_related("photos"), user=user)
    if not profile.is_visible and user != request.user:
        return HttpResponseForbidden("This dating profile is not visible.")
    
    # Track view
    if request.user.is_authenticated and request.user != user:
        DatingProfileView.objects.create(viewer=request.user, viewed_profile=profile)
        
    outgoing_like = DatingLike.objects.filter(from_user=request.user, to_user=user).first()
    liked = bool(outgoing_like)
    passed = DatingPass.objects.filter(from_user=request.user, to_user=user).exists()
    
    # Check for match
    user_one, user_two = (request.user, user) if request.user.id < user.id else (user, request.user)
    is_match = Match.objects.filter(user_one=user_one, user_two=user_two, is_active=True).exists()
    
    return render(request, "dating/detail.html", {
        "dating_profile": profile, 
        "liked": liked, 
        "super_liked": bool(outgoing_like and outgoing_like.is_super_like),
        "passed": passed,
        "is_match": is_match,
        "super_like_cost_coins": SUPER_LIKE_COST_COINS,
    })


@login_required(login_url="login")
@require_POST
def dating_like_view(request, username):
    target = get_object_or_404(get_user_model(), profile__username__iexact=username)
    like, match = like_user(request.user, target)
    if like is None:
        if _is_ajax(request):
            return JsonResponse({"ok": False, "error": "Daily like limit reached for your current tier."}, status=400)
        messages.error(request, "Daily like limit reached for your current tier.")
        return redirect(request.POST.get("next") or "dating_discover")
    if match:
        if _is_ajax(request):
            return JsonResponse({"ok": True, "match": True})
        messages.success(request, "🔥 It's a match! Start chatting now.")
        return redirect("dating_matches")
    if _is_ajax(request):
        return JsonResponse({"ok": True, "match": False})
    messages.success(request, "Like sent.")
    return redirect(request.POST.get("next") or "dating_discover")


@login_required(login_url="login")
@require_POST
def dating_super_like_view(request, username):
    target = get_object_or_404(get_user_model(), profile__username__iexact=username)
    result = purchase_super_like(request.user, target)
    if not result["ok"]:
        if result["reason"] == "duplicate":
            if _is_ajax(request):
                return JsonResponse({"ok": False, "error": "You already sent a Super Like to this profile."}, status=400)
            messages.info(request, "You already sent a Super Like to this profile.")
            return redirect(request.POST.get("next") or "dating_discover")
        if result["reason"] == "insufficient_coins":
            if _is_ajax(request):
                return JsonResponse({"ok": False, "error": f"You need {SUPER_LIKE_COST_COINS} coins to send a Super Like."}, status=400)
            messages.error(request, f"You need {SUPER_LIKE_COST_COINS} coins to send a Super Like.")
            return redirect(request.POST.get("next") or "dating_discover")
        if _is_ajax(request):
            return JsonResponse({"ok": False, "error": "You cannot super like this profile."}, status=403)
        return HttpResponseForbidden("You cannot super like this profile.")

    match = result["match"]
    if match:
        if _is_ajax(request):
            return JsonResponse({"ok": True, "match": True, "super_like": True})
        messages.success(request, "⭐ Super Like sent and it’s a match!")
        return redirect("dating_matches")
    if _is_ajax(request):
        return JsonResponse({"ok": True, "match": False, "super_like": True})
    messages.success(request, f"Super Like sent. {SUPER_LIKE_COST_COINS} coins were deducted.")
    return redirect(request.POST.get("next") or "dating_discover")


@login_required(login_url="login")
@require_POST
def dating_pass_view(request, username):
    target = get_object_or_404(get_user_model(), profile__username__iexact=username)
    passed = pass_user(request.user, target)
    if passed is None:
        if _is_ajax(request):
            return JsonResponse({"ok": False, "error": "You cannot pass this profile."}, status=403)
        return HttpResponseForbidden("You cannot pass this profile.")
    if _is_ajax(request):
        return JsonResponse({"ok": True})
    messages.success(request, "Profile passed.")
    return redirect(request.POST.get("next") or "dating_discover")


@login_required(login_url="login")
def dating_message_match_view(request, username=None):
    if not username:
        messages.info(request, "Open a match first to start chatting.")
        return redirect("dating_matches")
    target = get_object_or_404(get_user_model(), profile__username__iexact=username)
    user_one, user_two = (request.user, target) if request.user.id < target.id else (target, request.user)
    if not Match.objects.filter(user_one=user_one, user_two=user_two, is_active=True).exists():
        messages.info(request, "You can message after matching.")
        return redirect("dating_profile_detail", username=username)
    return _safe_conversation_redirect(request.user, target)


@login_required(login_url="login")
@require_POST
def dating_send_message(request, username):
    target = get_object_or_404(get_user_model(), profile__username__iexact=username)
    user_one, user_two = (request.user, target) if request.user.id < target.id else (target, request.user)
    if not Match.objects.filter(user_one=user_one, user_two=user_two, is_active=True).exists():
        return HttpResponseForbidden("You can only message people you have matched with.")

    text = request.POST.get("text", "").strip()
    if not text:
        messages.error(request, "Message cannot be empty.")
        return redirect("dating_message_match", username=username)

    conversation = get_or_create_direct_conversation(request.user, target)
    Message.objects.create(conversation=conversation, sender=request.user, text=text)
    conversation.save()
    messages.success(request, "Message sent.")
    return redirect(_dashboard_messages_url(conversation))
