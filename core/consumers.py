import json

from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

from core.realtime import notification_group_name
from messaging.presence import mark_user_offline, mark_user_online


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return
        self.group_name = notification_group_name(self.user.id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await sync_to_async(mark_user_online)(self.user.id)
        await self.send_initial_counts()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if getattr(self, "user", None) and self.user.is_authenticated:
            await sync_to_async(mark_user_offline)(self.user.id)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        data = json.loads(text_data)
        action = data.get("action")
        if action == "sync_counts":
            await self.send_initial_counts()

    async def send_initial_counts(self):
        counts = await sync_to_async(self._counts_for_user)()
        await self.send(text_data=json.dumps({"type": "counts", **counts}))

    def _counts_for_user(self):
        from accounts.models import Notification
        from messaging.models import Message

        return {
            "notification_count": Notification.objects.filter(recipient=self.user, is_read=False).count(),
            "message_count": (
                Message.objects.filter(conversation__participants=self.user, read_at__isnull=True)
                .exclude(sender=self.user)
                .count()
            ),
        }

    async def notification_event(self, event):
        await self.send(text_data=json.dumps({"type": "notification", **event["payload"]}))

    async def notification_counts(self, event):
        await self.send(text_data=json.dumps({"type": "counts", **event["payload"]}))

    async def message_badge(self, event):
        await self.send(text_data=json.dumps({"type": "counts", **event["payload"]}))
