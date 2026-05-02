from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.shortcuts import render

from posts.services import create_message_report
from .forms import MessageForm, attachment_type_for
from .models import Conversation, Message
from .services import (
    blocked_between,
    call_gate_state,
    create_message,
    get_or_create_direct_conversation,
    messaging_dashboard_context,
    users_are_friends,
)


def _dashboard_messages_url(conversation):
    query = urlencode({"section": "messages", "conversation": conversation.pk})
    return f"{reverse('user_dashboard')}?{query}"


@login_required(login_url="login")
def messages_home_view(request):
    from accounts.views import _account_shell_context

    profile = request.user.profile
    account_profile = getattr(request.user, "account_profile", None)
    conversation_id = request.GET.get("conversation")
    context = {
        **_account_shell_context(request, profile, account_profile),
        **call_gate_state(request.user, "voice"),
        **messaging_dashboard_context(request.user, conversation_id),
        "account_shell_title": "Messages",
        "account_shell_subtitle": "Private chats, previews, and safe call gates",
    }
    return render(request, "messaging/home.html", context)


@login_required(login_url="login")
def conversation_redirect(request, conversation_id):
    conversation = get_object_or_404(Conversation.objects.filter(participants=request.user), pk=conversation_id)
    return redirect(_dashboard_messages_url(conversation))


@login_required(login_url="login")
def start_chat(request, user_id):
    other_user = get_object_or_404(get_user_model(), pk=user_id)
    if other_user == request.user:
        messages.error(request, "Choose another member to start a chat.")
        return redirect("user_dashboard")
    if not users_are_friends(request.user, other_user):
        messages.error(request, "Chat opens after a friend request is accepted.")
        return redirect("profile_detail", username=other_user.profile.username)

    conversation = get_or_create_direct_conversation(request.user, other_user)
    return redirect(_dashboard_messages_url(conversation))


@login_required(login_url="login")
@require_POST
def send_message(request, conversation_id):
    conversation = get_object_or_404(Conversation.objects.filter(participants=request.user), pk=conversation_id)
    other_user = conversation.other_participant(request.user)
    if not other_user or blocked_between(request.user, other_user):
        messages.error(request, "Chat is no longer available for this conversation.")
        return redirect("messages_home")
    form = MessageForm(request.POST, request.FILES)

    if not form.is_valid():
        messages.error(request, form.errors.get("__all__", ["Message could not be sent."])[0])
        return redirect(_dashboard_messages_url(conversation))

    reply_to = None
    reply_to_id = form.cleaned_data.get("reply_to")
    if reply_to_id:
        reply_to = conversation.messages.filter(pk=reply_to_id).first()

    forwarded_from = None
    forward_to_id = form.cleaned_data.get("forward_to")
    if forward_to_id:
        forwarded_from = Message.objects.filter(
            pk=forward_to_id,
            conversation__participants=request.user,
        ).first()

    text = (form.cleaned_data.get("text") or "").strip()
    attachment = form.cleaned_data.get("attachment")

    if forwarded_from and not text:
        text = forwarded_from.text

    create_message(
        conversation,
        request.user,
        text=text,
        attachment=attachment,
        reply_to=reply_to,
        forwarded_from=forwarded_from,
    )

    return redirect(_dashboard_messages_url(conversation))


@login_required(login_url="login")
@require_POST
def delete_message(request, message_id):
    message = get_object_or_404(
        Message.objects.filter(conversation__participants=request.user, sender=request.user),
        pk=message_id,
    )
    message.deleted_at = timezone.now()
    message.text = ""
    message.save(update_fields=["deleted_at", "text"])
    return redirect(_dashboard_messages_url(message.conversation))


@login_required(login_url="login")
def call_gate_view(request, user_id, mode):
    other_user = get_object_or_404(get_user_model(), pk=user_id)
    if other_user == request.user:
        messages.error(request, "Choose another member to start a call.")
        return redirect("user_dashboard")
    if not users_are_friends(request.user, other_user):
        messages.error(request, "Calls unlock after friendship is accepted.")
        return redirect("profile_detail", username=other_user.profile.username)
    if mode not in {"voice", "video"}:
        mode = "voice"
    conversation = get_or_create_direct_conversation(request.user, other_user)
    return render(
        request,
        "messaging/call_gate.html",
        {
            "other_user": other_user,
            "conversation": conversation,
            "gate": call_gate_state(request.user, mode),
        },
    )


@login_required(login_url="login")
def call_lobby_view(request, user_id):
    other_user = get_object_or_404(get_user_model(), pk=user_id)
    if other_user == request.user:
        messages.error(request, "Choose another member to start a call.")
        return redirect("user_dashboard")
    if not users_are_friends(request.user, other_user):
        messages.error(request, "Calls unlock after friendship is accepted.")
        return redirect("profile_detail", username=other_user.profile.username)

    conversation = get_or_create_direct_conversation(request.user, other_user)
    initial_mode = request.GET.get("mode", "voice")
    if initial_mode not in {"voice", "video"}:
        initial_mode = "voice"
    return render(
        request,
        "messaging/call_lobby.html",
        {
            "other_user": other_user,
            "conversation": conversation,
            "voice_gate": call_gate_state(request.user, "voice"),
            "video_gate": call_gate_state(request.user, "video"),
            "initial_mode": initial_mode,
        },
    )


@login_required(login_url="login")
@require_POST
def report_message_view(request, message_id):
    from posts.models import Report

    message = get_object_or_404(
        Message.objects.select_related("conversation", "sender", "sender__profile").filter(conversation__participants=request.user),
        pk=message_id,
    )
    if message.sender == request.user:
        return HttpResponseForbidden("You cannot report your own message.")
    reason = request.POST.get("reason") or Report.Reason.OTHER
    if reason not in Report.Reason.values:
        reason = Report.Reason.OTHER
    create_message_report(
        request.user,
        message=message,
        reason=reason,
        details=request.POST.get("details", ""),
    )
    messages.success(request, "Message report submitted.")
    return redirect(_dashboard_messages_url(message.conversation))
