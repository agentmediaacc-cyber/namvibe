from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import Follow
from wallet.models import GiftEvent
from wallet.services import InsufficientFunds, active_gifts, default_live_access_price, purchase_live_access, send_gift
from .forms import LiveMessageForm, LiveSessionForm
from .models import LiveMessage, LiveReaction, LiveSession
from .services import can_access_session, can_chat, create_chat_message, featured_sessions_for, live_now_for, related_sessions_for, scheduled_sessions_for


LIVE_CATEGORIES = ["Music", "Dating Talk", "Lifestyle", "Night Vibes", "Fitness", "Comedy", "Fashion", "Gaming", "Communities"]


def _safe_live_context(*, title="", safe_mode_message="", session=None, locked_premium=False):
    return {
        "title": title,
        "session": session,
        "live_sessions": [],
        "scheduled_sessions": [],
        "featured_sessions": [],
        "sessions": [],
        "messages": [],
        "message_form": LiveMessageForm(),
        "related_sessions": [],
        "can_chat": False,
        "is_host": False,
        "is_following": False,
        "locked_premium": locked_premium,
        "live_access_price": default_live_access_price(session) if session else default_live_access_price(None),
        "gift_catalog": [],
        "recent_gifts": [],
        "live_count": 0,
        "categories": LIVE_CATEGORIES,
        "safe_mode_message": safe_mode_message,
    }


def live_home_view(request):
    try:
        live_sessions = list(live_now_for(request.user))
        scheduled_sessions = list(scheduled_sessions_for(request.user)[:8])
        featured_sessions = list(featured_sessions_for(request.user)[:6])
        safe_mode_message = ""
    except Exception as exc:
        live_sessions = []
        scheduled_sessions = []
        featured_sessions = []
        safe_mode_message = str(exc)
    return render(
        request,
        "live/home.html",
        {
            "live_sessions": live_sessions,
            "scheduled_sessions": scheduled_sessions,
            "featured_sessions": featured_sessions,
            "live_count": len(live_sessions),
            "categories": LIVE_CATEGORIES,
            "safe_mode_message": safe_mode_message,
        },
    )


def live_featured_view(request):
    safe_mode_message = ""
    try:
        sessions = list(featured_sessions_for(request.user))
    except Exception as exc:
        sessions = []
        safe_mode_message = str(exc)
    return render(request, "live/list.html", {"title": "Featured live creators", "sessions": sessions, "safe_mode_message": safe_mode_message})


def live_scheduled_view(request):
    safe_mode_message = ""
    try:
        sessions = list(scheduled_sessions_for(request.user))
    except Exception as exc:
        sessions = []
        safe_mode_message = str(exc)
    return render(request, "live/list.html", {"title": "Upcoming live sessions", "sessions": sessions, "safe_mode_message": safe_mode_message})


@login_required(login_url="login")
def live_start_view(request):
    form = LiveSessionForm(request.POST or None, request.FILES or None, host=request.user)
    if request.method == "POST" and form.is_valid():
        session = form.save()
        messages.success(request, "Live session created.")
        return redirect("live_room", uuid=session.uuid)
    return render(request, "live/start.html", {"form": form})


def live_room_view(request, uuid):
    try:
        session = get_object_or_404(
            LiveSession.objects.select_related("host", "host__profile").prefetch_related("messages__user__profile", "moderators__user"),
            uuid=uuid,
        )
        locked_premium = session.access_type == LiveSession.AccessType.PREMIUM and not can_access_session(request.user, session)
        if locked_premium and request.user.is_authenticated:
            context = _safe_live_context(title=session.title, session=session, locked_premium=True)
            context.update(
                {
                    "related_sessions": list(related_sessions_for(request.user, session)),
                    "is_following": Follow.objects.filter(follower=request.user, following=session.host).exists(),
                }
            )
            return render(request, "live/room.html", context)
        if not can_access_session(request.user, session):
            if not request.user.is_authenticated:
                return redirect(f"{reverse('login')}?next={request.path}")
            return HttpResponseForbidden("This live room is not available.")
        if session.status == LiveSession.Status.LIVE and (not request.user.is_authenticated or session.host_id != request.user.id):
            LiveSession.objects.filter(pk=session.pk).update(
                viewer_count=session.viewer_count + 1,
                peak_viewer_count=max(session.peak_viewer_count, session.viewer_count + 1),
            )
            session.refresh_from_db()
        is_following = request.user.is_authenticated and Follow.objects.filter(follower=request.user, following=session.host).exists()
        return render(
            request,
            "live/room.html",
            {
                "session": session,
                "messages": session.messages.filter(is_deleted=False).select_related("user", "user__profile").order_by("-created_at")[:80],
                "message_form": LiveMessageForm(),
                "related_sessions": related_sessions_for(request.user, session),
                "can_chat": can_chat(request.user, session),
                "is_host": request.user.is_authenticated and request.user == session.host,
                "is_following": is_following,
                "locked_premium": False,
                "live_access_price": default_live_access_price(session),
                "gift_catalog": active_gifts(),
                "recent_gifts": GiftEvent.objects.filter(live_session=session).select_related("sender", "gift").order_by("-created_at")[:8],
            },
        )
    except Exception as exc:
        return render(request, "live/room.html", _safe_live_context(title="Live room", safe_mode_message=str(exc)))


def live_chat_view(request, uuid):
    session = get_object_or_404(LiveSession, uuid=uuid)
    if not can_access_session(request.user, session):
        return HttpResponseForbidden("This live chat is not available.")
    messages_qs = session.messages.filter(is_deleted=False).select_related("user", "user__profile").order_by("-created_at")[:80]
    return render(request, "live/_chat_messages.html", {"messages": messages_qs, "session": session})


@login_required(login_url="login")
@require_POST
def live_message_view(request, uuid):
    session = get_object_or_404(LiveSession, uuid=uuid)
    form = LiveMessageForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Message cannot be empty.")
        return redirect("live_room", uuid=session.uuid)
    message = create_chat_message(request.user, session, form.cleaned_data["body"])
    if not message:
        return HttpResponseForbidden("You cannot send messages in this room.")
    return redirect("live_room", uuid=session.uuid)


@login_required(login_url="login")
@require_POST
def live_end_view(request, uuid):
    session = get_object_or_404(LiveSession, uuid=uuid)
    if session.host != request.user:
        return HttpResponseForbidden("Only the host can end this session.")
    session.end()
    messages.success(request, "Live session ended.")
    return redirect("live_room", uuid=session.uuid)


@login_required(login_url="login")
@require_POST
def live_react_view(request, uuid):
    session = get_object_or_404(LiveSession, uuid=uuid)
    if not can_access_session(request.user, session):
        return HttpResponseForbidden("You cannot react to this live.")
    reaction_type = request.POST.get("reaction_type") or LiveReaction.ReactionType.LIKE
    if reaction_type not in LiveReaction.ReactionType.values:
        reaction_type = LiveReaction.ReactionType.LIKE
    reaction, created = LiveReaction.objects.get_or_create(session=session, user=request.user, defaults={"reaction_type": reaction_type})
    if not created and reaction.reaction_type != reaction_type:
        reaction.reaction_type = reaction_type
        reaction.save(update_fields=["reaction_type"])
    session.like_count = session.reactions.count()
    session.save(update_fields=["like_count"])
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "like_count": session.like_count})
    return redirect("live_room", uuid=session.uuid)


@login_required(login_url="login")
@require_POST
def live_purchase_access_view(request, uuid):
    session = get_object_or_404(LiveSession, uuid=uuid)
    try:
        purchase_live_access(request.user, session, default_live_access_price(session))
    except InsufficientFunds:
        messages.error(request, "Your wallet balance is not enough to unlock this premium room.")
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Premium live access unlocked.")
    return redirect("live_room", uuid=session.uuid)


@login_required(login_url="login")
@require_POST
def live_gift_view(request, uuid):
    session = get_object_or_404(LiveSession, uuid=uuid)
    if not can_access_session(request.user, session):
        return HttpResponseForbidden("You cannot send gifts in this room.")
    gift = get_object_or_404(active_gifts(), slug=request.POST.get("gift"))
    try:
        send_gift(request.user, session.host, gift, request.POST.get("quantity") or 1, live_session=session)
    except InsufficientFunds:
        messages.error(request, "Your wallet balance is not enough for this gift.")
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"You sent {gift.name} to @{session.host.profile.username}.")
    return redirect("live_room", uuid=session.uuid)


def live_studio_view(request):
    return redirect("live_start")
