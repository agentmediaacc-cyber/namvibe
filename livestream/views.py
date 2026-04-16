import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import LiveComment, LiveGift, LiveRoom


def _account_context(request):
    return {
        "full_name": request.session.get("eharo_full_name", request.user.get_full_name() or request.user.username),
        "username": request.session.get("eharo_username", request.user.username),
        "email": request.session.get("eharo_email", request.user.email),
    }


def _json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def _room_to_dict(room):
    return {
        "id": str(room.id),
        "host_full_name": room.host_full_name,
        "host_username": room.host_username,
        "host_email": room.host_email,
        "title": room.title,
        "description": room.description,
        "audience": room.audience,
        "room_access": room.room_access,
        "status": room.status,
        "theme": room.theme,
        "quality": room.quality,
        "frame_rate": room.frame_rate,
        "view_mode": room.view_mode,
        "allow_gifts": room.allow_gifts,
        "allow_comments": room.allow_comments,
        "allow_cohost": room.allow_cohost,
        "allow_premium_join": room.allow_premium_join,
        "allow_premium_view": room.allow_premium_view,
        "vip_badge": room.vip_badge,
        "private_line": room.private_line,
        "location_text": room.location_text,
        "viewer_count": room.viewer_count,
        "started_at": room.started_at.isoformat() if room.started_at else None,
        "ended_at": room.ended_at.isoformat() if room.ended_at else None,
        "created_at": room.created_at.isoformat() if room.created_at else None,
    }


def _comment_to_dict(comment):
    return {
        "id": comment.id,
        "username": comment.username,
        "full_name": comment.full_name,
        "message": comment.message,
        "is_host": comment.is_host,
        "created_at": comment.created_at.isoformat(),
    }


def _gift_to_dict(gift):
    return {
        "id": gift.id,
        "sender_username": gift.sender_username,
        "gift_name": gift.gift_name,
        "token_amount": gift.token_amount,
        "created_at": gift.created_at.isoformat(),
    }


def _broadcast(room_id, payload):
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            f"live_room_{room_id}",
            {"type": "live.event", "payload": payload},
        )


def _host_required(request, room):
    return request.user.is_authenticated and room.host_id == request.user.id


@login_required(login_url="login")
def live_studio_view(request):
    context = _account_context(request)
    return render(request, "livestream/studio.html", context)


@login_required(login_url="login")
def live_broadcast_view(request, room_id):
    room = get_object_or_404(LiveRoom, pk=room_id)
    if not _host_required(request, room):
        return HttpResponseForbidden("Only the room host can manage this live broadcast.")

    context = {
        "room": room,
        "comments": room.comments.order_by("-created_at")[:80],
        "gifts": room.gifts.order_by("-created_at")[:30],
        "viewer_count": room.viewer_count,
    }
    return render(request, "livestream/broadcast.html", context)


def live_join_view(request, room_id):
    room = get_object_or_404(LiveRoom, pk=room_id)
    if not room.user_can_view(request.user):
        if not request.user.is_authenticated:
            return redirect("login")
        return HttpResponseForbidden("This live room is private.")

    context = {
        "room": room,
        "comments": room.comments.order_by("-created_at")[:50],
        "gifts": room.gifts.order_by("-created_at")[:20],
        "viewer_name": request.session.get("eharo_full_name", "Guest"),
        "viewer_username": request.session.get("eharo_username", "guest"),
        "viewer_user_id": request.session.get("eharo_user_id", ""),
    }
    return render(request, "livestream/join.html", context)


@require_GET
def live_rooms_api(request):
    rooms = LiveRoom.objects.exclude(status=LiveRoom.STATUS_ENDED)[:30]
    return JsonResponse({"ok": True, "rooms": [_room_to_dict(room) for room in rooms]})


@require_POST
def create_live_room_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Login required."}, status=403)

    data = _json_body(request)
    room = LiveRoom.objects.create(
        host=request.user,
        host_full_name=request.session.get("eharo_full_name", request.user.get_full_name() or request.user.username),
        host_username=request.session.get("eharo_username", request.user.username),
        host_email=request.session.get("eharo_email", request.user.email),
        title=data.get("title") or "Untitled Live",
        description=data.get("description", ""),
        audience=data.get("audience", "Public"),
        room_access=data.get("room_access", "Open Room"),
        status=LiveRoom.STATUS_SCHEDULED,
        theme=data.get("theme", "theme-purple"),
        quality=data.get("quality", "1280x720"),
        frame_rate=int(data.get("frame_rate", 30) or 30),
        view_mode=data.get("view_mode", "normal"),
        allow_gifts=bool(data.get("allow_gifts", True)),
        allow_comments=bool(data.get("allow_comments", True)),
        allow_cohost=bool(data.get("allow_cohost", False)),
        allow_premium_join=bool(data.get("allow_premium_join", False)),
        allow_premium_view=bool(data.get("allow_premium_view", False)),
        vip_badge=bool(data.get("vip_badge", False)),
        private_line=bool(data.get("private_line", False)),
        location_text=data.get("location_text", ""),
    )
    return JsonResponse({"ok": True, "room": _room_to_dict(room)})


@require_POST
def start_live_room_api(request, room_id):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Login required."}, status=403)

    room = get_object_or_404(LiveRoom, pk=room_id)
    if not _host_required(request, room):
        return JsonResponse({"ok": False, "error": "Only the host can start this room."}, status=403)

    room.start()
    payload = {"type": "state", "event": "start", "room": _room_to_dict(room)}
    _broadcast(room.id, payload)
    return JsonResponse({"ok": True, "room": _room_to_dict(room)})


@require_POST
def end_live_room_api(request, room_id):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Login required."}, status=403)

    room = get_object_or_404(LiveRoom, pk=room_id)
    if not _host_required(request, room):
        return JsonResponse({"ok": False, "error": "Only the host can end this room."}, status=403)

    room.end()
    room.viewers.all().delete()
    payload = {"type": "state", "event": "end", "room": _room_to_dict(room)}
    _broadcast(room.id, payload)
    return JsonResponse({"ok": True, "room": _room_to_dict(room)})


@require_POST
def update_live_room_api(request, room_id):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Login required."}, status=403)

    room = get_object_or_404(LiveRoom, pk=room_id)
    if not _host_required(request, room):
        return JsonResponse({"ok": False, "error": "Only the host can update this room."}, status=403)

    data = _json_body(request)
    editable_fields = {
        "title",
        "description",
        "audience",
        "room_access",
        "theme",
        "quality",
        "frame_rate",
        "view_mode",
        "allow_gifts",
        "allow_comments",
        "allow_cohost",
        "allow_premium_join",
        "allow_premium_view",
        "vip_badge",
        "private_line",
        "location_text",
    }
    for field in editable_fields:
        if field in data:
            setattr(room, field, data[field])
    room.updated_at = timezone.now()
    room.save()
    _broadcast(room.id, {"type": "state", "event": "update", "room": _room_to_dict(room)})
    return JsonResponse({"ok": True, "room": _room_to_dict(room)})


@require_GET
def live_comments_api(request, room_id):
    room = get_object_or_404(LiveRoom, pk=room_id)
    if not room.user_can_view(request.user):
        raise Http404
    comments = room.comments.order_by("-created_at")[:80]
    return JsonResponse({"ok": True, "comments": [_comment_to_dict(comment) for comment in comments]})


@require_POST
def create_live_comment_api(request, room_id):
    room = get_object_or_404(LiveRoom, pk=room_id)
    if not room.user_can_view(request.user):
        return JsonResponse({"ok": False, "error": "You cannot comment in this room."}, status=403)
    if not room.allow_comments:
        return JsonResponse({"ok": False, "error": "Comments are disabled."}, status=403)

    data = _json_body(request)
    message = (data.get("message") or "").strip()
    if not message:
        return JsonResponse({"ok": False, "error": "Message is required."}, status=400)

    user = request.user if request.user.is_authenticated else None
    comment = LiveComment.objects.create(
        room=room,
        user=user,
        full_name=(user.get_full_name() if user else "") or request.session.get("eharo_full_name", "Guest"),
        username=(user.username if user else "") or request.session.get("eharo_username", "guest"),
        message=message,
        is_host=bool(user and user.id == room.host_id),
    )
    payload = {"type": "comment", "comment": _comment_to_dict(comment)}
    _broadcast(room.id, payload)
    return JsonResponse({"ok": True, "comment": payload["comment"]})


@require_GET
def live_gifts_api(request, room_id):
    room = get_object_or_404(LiveRoom, pk=room_id)
    if not room.user_can_view(request.user):
        raise Http404
    gifts = room.gifts.order_by("-created_at")[:30]
    return JsonResponse({"ok": True, "gifts": [_gift_to_dict(gift) for gift in gifts]})


@require_POST
def create_live_gift_api(request, room_id):
    room = get_object_or_404(LiveRoom, pk=room_id)
    if not room.user_can_view(request.user):
        return JsonResponse({"ok": False, "error": "You cannot send gifts in this room."}, status=403)
    if not room.allow_gifts:
        return JsonResponse({"ok": False, "error": "Gifts are disabled."}, status=403)

    data = _json_body(request)
    user = request.user if request.user.is_authenticated else None
    gift = LiveGift.objects.create(
        room=room,
        sender=user,
        sender_username=(user.username if user else "") or request.session.get("eharo_username", "guest"),
        gift_name=data.get("gift_name", "Star"),
        token_amount=int(data.get("token_amount", 0) or 0),
    )
    payload = {"type": "gift", "gift": _gift_to_dict(gift)}
    _broadcast(room.id, payload)
    return JsonResponse({"ok": True, "gift": payload["gift"]})
