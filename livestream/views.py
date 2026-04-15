from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
import json

from .supabase_live import (
    create_live_room,
    list_live_rooms,
    get_live_room,
    update_live_room,
    create_live_comment,
    list_live_comments,
    create_live_gift,
    list_live_gifts,
)

def live_studio_view(request):
    if not request.session.get("eharo_user_id"):
        return redirect("login")

    context = {
        "full_name": request.session.get("eharo_full_name", ""),
        "username": request.session.get("eharo_username", ""),
        "email": request.session.get("eharo_email", ""),
    }
    return render(request, "livestream/studio.html", context)


def live_broadcast_view(request, room_id):
    room = {}
    comments = []
    gifts = []

    room_resp = get_live_room(room_id)
    if room_resp.ok and room_resp.json():
        room = room_resp.json()[0]

    comments_resp = list_live_comments(room_id, limit=80)
    if comments_resp.ok:
        comments = comments_resp.json()

    gifts_resp = list_live_gifts(room_id, limit=30)
    if gifts_resp.ok:
        gifts = gifts_resp.json()

    context = {
        "room": room,
        "comments": comments,
        "gifts": gifts,
    }
    return render(request, "livestream/broadcast.html", context)

def live_join_view(request, room_id):
    room = {}
    comments = []
    gifts = []

    room_resp = get_live_room(room_id)
    if room_resp.ok and room_resp.json():
        room = room_resp.json()[0]

    comments_resp = list_live_comments(room_id, limit=50)
    if comments_resp.ok:
        comments = comments_resp.json()

    gifts_resp = list_live_gifts(room_id, limit=20)
    if gifts_resp.ok:
        gifts = gifts_resp.json()

    context = {
        "room": room,
        "comments": comments,
        "gifts": gifts,
        "viewer_name": request.session.get("eharo_full_name", "Guest"),
        "viewer_username": request.session.get("eharo_username", "guest"),
        "viewer_user_id": request.session.get("eharo_user_id", ""),
    }
    return render(request, "livestream/join.html", context)

@require_GET
def live_rooms_api(request):
    resp = list_live_rooms(limit=30, only_live=False)
    if not resp.ok:
        return JsonResponse({"ok": False, "error": resp.text}, status=500)
    return JsonResponse({"ok": True, "rooms": resp.json()})

@require_POST
def create_live_room_api(request):
    if not request.session.get("eharo_user_id"):
        return JsonResponse({"ok": False, "error": "Login required"}, status=403)

    data = json.loads(request.body.decode("utf-8"))
    payload = {
        "host_user_id": request.session.get("eharo_user_id"),
        "host_full_name": request.session.get("eharo_full_name", ""),
        "host_username": request.session.get("eharo_username", ""),
        "host_email": request.session.get("eharo_email", ""),
        "title": data.get("title", "Untitled Live"),
        "description": data.get("description", ""),
        "audience": data.get("audience", "Public"),
        "room_access": data.get("room_access", "Open Room"),
        "status": data.get("status", "live"),
        "theme": data.get("theme", "theme-purple"),
        "quality": data.get("quality", "1280x720"),
        "frame_rate": int(data.get("frame_rate", 30)),
        "view_mode": data.get("view_mode", "normal"),
        "allow_gifts": bool(data.get("allow_gifts", True)),
        "allow_comments": bool(data.get("allow_comments", True)),
        "allow_cohost": bool(data.get("allow_cohost", False)),
        "allow_premium_join": bool(data.get("allow_premium_join", False)),
        "allow_premium_view": bool(data.get("allow_premium_view", False)),
        "vip_badge": bool(data.get("vip_badge", False)),
        "private_line": bool(data.get("private_line", False)),
        "location_text": data.get("location_text", ""),
        "started_at": timezone.now().isoformat(),
    }
    resp = create_live_room(payload)
    if not resp.ok:
        return JsonResponse({"ok": False, "error": resp.text}, status=500)
    room = resp.json()[0]
    return JsonResponse({"ok": True, "room": room})

@require_POST
def update_live_room_api(request, room_id):
    data = json.loads(request.body.decode("utf-8"))
    resp = update_live_room(room_id, data)
    if not resp.ok:
        return JsonResponse({"ok": False, "error": resp.text}, status=500)
    rows = resp.json()
    return JsonResponse({"ok": True, "room": rows[0] if rows else {}})

@require_GET
def live_comments_api(request, room_id):
    resp = list_live_comments(room_id, limit=80)
    if not resp.ok:
        return JsonResponse({"ok": False, "error": resp.text}, status=500)
    return JsonResponse({"ok": True, "comments": resp.json()})

@require_POST
def create_live_comment_api(request, room_id):
    data = json.loads(request.body.decode("utf-8"))
    payload = {
        "room_id": room_id,
        "user_id": request.session.get("eharo_user_id", ""),
        "full_name": request.session.get("eharo_full_name", data.get("full_name", "Guest")),
        "username": request.session.get("eharo_username", data.get("username", "guest")),
        "message": data.get("message", ""),
        "is_host": bool(data.get("is_host", False)),
    }
    resp = create_live_comment(payload)
    if not resp.ok:
        return JsonResponse({"ok": False, "error": resp.text}, status=500)
    return JsonResponse({"ok": True, "comment": resp.json()[0]})

@require_GET
def live_gifts_api(request, room_id):
    resp = list_live_gifts(room_id, limit=30)
    if not resp.ok:
        return JsonResponse({"ok": False, "error": resp.text}, status=500)
    return JsonResponse({"ok": True, "gifts": resp.json()})

@require_POST
def create_live_gift_api(request, room_id):
    data = json.loads(request.body.decode("utf-8"))
    payload = {
        "room_id": room_id,
        "sender_user_id": request.session.get("eharo_user_id", ""),
        "sender_username": request.session.get("eharo_username", "guest"),
        "gift_name": data.get("gift_name", "Star"),
        "token_amount": int(data.get("token_amount", 0)),
    }
    resp = create_live_gift(payload)
    if not resp.ok:
        return JsonResponse({"ok": False, "error": resp.text}, status=500)
    return JsonResponse({"ok": True, "gift": resp.json()[0]})
