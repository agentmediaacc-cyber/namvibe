import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import LiveComment, LiveGift, LiveRoom, LiveViewer


class LiveRoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"live_room_{self.room_id}"
        self.user = self.scope.get("user")
        self.room = await self.get_room()

        if not self.room or not await self.can_view_room():
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.add_viewer()
        await self.broadcast_state("join")

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.remove_viewer()
            await self.broadcast_state("leave")
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        data = json.loads(text_data)
        action = data.get("action")

        if action == "comment":
            await self.create_comment(data.get("message", ""))
        elif action == "gift":
            await self.create_gift(data.get("gift_name", "Star"), int(data.get("token_amount", 0) or 0))
        elif action == "start":
            if await self.is_host():
                await self.start_room()
                await self.broadcast_state("start")
        elif action == "end":
            if await self.is_host():
                await self.end_room()
                await self.broadcast_state("end")
        elif action == "signal":
            await self.channel_layer.group_send(self.group_name, {"type": "live.signal", "payload": data})

    async def live_event(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    async def live_signal(self, event):
        await self.send(text_data=json.dumps({"type": "signal", **event["payload"]}))

    @sync_to_async
    def get_room(self):
        return LiveRoom.objects.filter(pk=self.room_id).first()

    @sync_to_async
    def can_view_room(self):
        return self.room.user_can_view(self.user)

    @sync_to_async
    def is_host(self):
        return bool(self.user and self.user.is_authenticated and self.user.pk == self.room.host_id)

    @sync_to_async
    def add_viewer(self):
        display_name = "Guest"
        if self.user and self.user.is_authenticated:
            display_name = self.user.get_full_name() or self.user.username
        LiveViewer.objects.update_or_create(
            channel_name=self.channel_name,
            defaults={"room": self.room, "user": self.user if self.user.is_authenticated else None, "display_name": display_name},
        )
        self.room.viewer_count = self.room.viewers.count()
        self.room.save(update_fields=["viewer_count", "updated_at"])

    @sync_to_async
    def remove_viewer(self):
        LiveViewer.objects.filter(channel_name=self.channel_name).delete()
        room = LiveRoom.objects.filter(pk=self.room_id).first()
        if room:
            room.viewer_count = room.viewers.count()
            room.save(update_fields=["viewer_count", "updated_at"])

    @sync_to_async
    def room_state(self):
        room = LiveRoom.objects.get(pk=self.room_id)
        return {
            "id": str(room.id),
            "status": room.status,
            "viewer_count": room.viewer_count,
            "title": room.title,
            "audience": room.audience,
            "room_access": room.room_access,
        }

    async def broadcast_state(self, event_name):
        state = await self.room_state()
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "live.event", "payload": {"type": "state", "event": event_name, "room": state}},
        )

    async def create_comment(self, message):
        message = (message or "").strip()
        if not message or not self.room.allow_comments:
            return
        comment = await self.save_comment(message)
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "live.event", "payload": {"type": "comment", "comment": comment}},
        )

    @sync_to_async
    def save_comment(self, message):
        user = self.user if self.user and self.user.is_authenticated else None
        comment = LiveComment.objects.create(
            room=self.room,
            user=user,
            full_name=(user.get_full_name() if user else "") or "Guest",
            username=(user.username if user else "guest"),
            message=message,
            is_host=bool(user and user.pk == self.room.host_id),
        )
        return {
            "id": comment.id,
            "username": comment.username,
            "full_name": comment.full_name,
            "message": comment.message,
            "is_host": comment.is_host,
            "created_at": comment.created_at.isoformat(),
        }

    async def create_gift(self, gift_name, token_amount):
        if not self.room.allow_gifts:
            return
        gift = await self.save_gift(gift_name, token_amount)
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "live.event", "payload": {"type": "gift", "gift": gift}},
        )

    @sync_to_async
    def save_gift(self, gift_name, token_amount):
        user = self.user if self.user and self.user.is_authenticated else None
        gift = LiveGift.objects.create(
            room=self.room,
            sender=user,
            sender_username=(user.username if user else "guest"),
            gift_name=gift_name or "Star",
            token_amount=token_amount,
        )
        return {
            "id": gift.id,
            "sender_username": gift.sender_username,
            "gift_name": gift.gift_name,
            "token_amount": gift.token_amount,
            "created_at": gift.created_at.isoformat(),
        }

    @sync_to_async
    def start_room(self):
        self.room.start()

    @sync_to_async
    def end_room(self):
        self.room.end()
