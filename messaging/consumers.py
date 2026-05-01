import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.realtime import call_group_name, conversation_group_name, push_message_badge
from .models import Conversation, Message
from .presence import mark_user_offline, mark_user_online, presence_snapshot
from .services import create_message, serialize_message, users_are_friends


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.conversation = await self.get_conversation()
        if not self.conversation or not await self.can_access_conversation():
            await self.close(code=4403)
            return

        self.group_name = conversation_group_name(self.conversation_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await sync_to_async(mark_user_online)(self.user.id)
        await self.broadcast_presence("join")

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.broadcast_presence("leave")
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if getattr(self, "user", None) and self.user.is_authenticated:
            await sync_to_async(mark_user_offline)(self.user.id)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        data = json.loads(text_data)
        action = data.get("action")

        if action == "message":
            payload = await self.create_and_serialize_message(data)
            if payload:
                await self.channel_layer.group_send(
                    self.group_name,
                    {"type": "chat.message", "payload": payload},
                )
        elif action == "typing":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.typing",
                    "payload": {
                        "sender_id": self.user.id,
                        "sender_username": self.user.username,
                        "is_typing": bool(data.get("is_typing")),
                    },
                },
            )
        elif action == "read":
            await sync_to_async(self.mark_read)()
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.read",
                    "payload": {
                        "reader_id": self.user.id,
                        "conversation_id": self.conversation_id,
                    },
                },
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({"type": "message", **event["payload"]}))

    async def chat_typing(self, event):
        await self.send(text_data=json.dumps({"type": "typing", **event["payload"]}))

    async def chat_read(self, event):
        await self.send(text_data=json.dumps({"type": "read", **event["payload"]}))

    async def chat_presence(self, event):
        await self.send(text_data=json.dumps({"type": "presence", **event["payload"]}))

    async def create_and_serialize_message(self, data):
        text = (data.get("text") or "").strip()
        if not text:
            return None
        reply_to_id = data.get("reply_to")
        forward_to_id = data.get("forward_to")
        return await sync_to_async(self._create_message_sync)(text, reply_to_id, forward_to_id)

    def _create_message_sync(self, text, reply_to_id=None, forward_to_id=None):
        reply_to = self.conversation.messages.filter(pk=reply_to_id).first() if reply_to_id else None
        forwarded_from = (
            Message.objects.filter(pk=forward_to_id, conversation__participants=self.user).first()
            if forward_to_id
            else None
        )
        message = create_message(
            self.conversation,
            self.user,
            text=text,
            reply_to=reply_to,
            forwarded_from=forwarded_from,
        )
        message = (
            Message.objects.select_related("sender", "reply_to", "reply_to__sender", "forwarded_from")
            .get(pk=message.pk)
        )
        return serialize_message(message, self.user)

    @sync_to_async
    def get_conversation(self):
        return Conversation.objects.prefetch_related("participants").filter(pk=self.conversation_id).first()

    @sync_to_async
    def can_access_conversation(self):
        if not self.conversation.participants.filter(pk=self.user.pk).exists():
            return False
        other_user = self.conversation.other_participant(self.user)
        return bool(other_user and users_are_friends(self.user, other_user))

    def mark_read(self):
        self.conversation.mark_read_for(self.user)
        push_message_badge(self.user)

    async def broadcast_presence(self, event_name):
        other_user = await sync_to_async(self.conversation.other_participant)(self.user)
        presence = await sync_to_async(presence_snapshot)(self.user.id)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.presence",
                "payload": {
                    "event": event_name,
                    "user_id": self.user.id,
                    "username": self.user.username,
                    "label": presence["label"],
                    "is_online": presence["is_online"],
                    "other_user_id": getattr(other_user, "id", None),
                },
            },
        )


class CallSignalingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.conversation = await self.get_conversation()
        if not self.conversation or not await self.can_access_conversation():
            await self.close(code=4403)
            return

        self.group_name = call_group_name(self.conversation_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        data = json.loads(text_data)
        action = data.get("action")
        if action not in {"call_invite", "call_accept", "call_reject", "offer", "answer", "ice_candidate", "call_end"}:
            return

        payload = {
            "action": action,
            "sender_id": self.user.id,
            "sender_username": self.user.username,
            "mode": data.get("mode", "voice"),
            "payload": data.get("payload", {}),
        }
        if action == "call_invite":
            await sync_to_async(self.create_call_invite_notification)(payload["mode"])
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "call.signal", "payload": payload},
        )

    async def call_signal(self, event):
        await self.send(text_data=json.dumps({"type": "signal", **event["payload"]}))

    @sync_to_async
    def get_conversation(self):
        return Conversation.objects.prefetch_related("participants").filter(pk=self.conversation_id).first()

    @sync_to_async
    def can_access_conversation(self):
        if not self.conversation.participants.filter(pk=self.user.pk).exists():
            return False
        other_user = self.conversation.other_participant(self.user)
        return bool(other_user and users_are_friends(self.user, other_user))

    def create_call_invite_notification(self, mode):
        other_user = self.conversation.other_participant(self.user)
        if not other_user:
            return
        from accounts.models import Notification, notify

        notification = notify(
            recipient=other_user,
            notification_type=Notification.Type.SYSTEM,
            sender=self.user,
            message=f"@{self.user.username} invited you to a {'video' if mode == 'video' else 'voice'} call.",
            target_url=reverse("call_start", args=[self.user.id]),
        )
