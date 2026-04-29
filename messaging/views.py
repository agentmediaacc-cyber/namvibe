from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.shortcuts import render

from .forms import MessageForm, attachment_type_for
from .models import Conversation, Message
from .services import call_gate_state, get_or_create_direct_conversation, messaging_dashboard_context


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

    conversation = get_or_create_direct_conversation(request.user, other_user)
    return redirect(_dashboard_messages_url(conversation))


@login_required(login_url="login")
@require_POST
def send_message(request, conversation_id):
    conversation = get_object_or_404(Conversation.objects.filter(participants=request.user), pk=conversation_id)
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

    Message.objects.create(
        conversation=conversation,
        sender=request.user,
        text=text,
        attachment=attachment,
        attachment_type=attachment_type_for(attachment),
        reply_to=reply_to,
        forwarded_from=forwarded_from,
    )
    conversation.save()

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
