import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class LiveRoom(models.Model):
    STATUS_SCHEDULED = "scheduled"
    STATUS_LIVE = "live"
    STATUS_ENDED = "ended"
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_LIVE, "Live"),
        (STATUS_ENDED, "Ended"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hosted_live_rooms")
    host_full_name = models.CharField(max_length=140, blank=True)
    host_username = models.CharField(max_length=140, blank=True)
    host_email = models.EmailField(blank=True)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    audience = models.CharField(max_length=80, default="Public")
    room_access = models.CharField(max_length=80, default="Open Room")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    theme = models.CharField(max_length=60, default="theme-purple")
    quality = models.CharField(max_length=40, default="1280x720")
    frame_rate = models.PositiveIntegerField(default=30)
    view_mode = models.CharField(max_length=40, default="normal")
    allow_gifts = models.BooleanField(default=True)
    allow_comments = models.BooleanField(default=True)
    allow_cohost = models.BooleanField(default=False)
    allow_premium_join = models.BooleanField(default=False)
    allow_premium_view = models.BooleanField(default=False)
    vip_badge = models.BooleanField(default=False)
    private_line = models.BooleanField(default=False)
    location_text = models.CharField(max_length=240, blank=True)
    viewer_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_locked(self):
        locked_audience = self.audience in ["Premium Members", "VIP Only", "Activated Accounts", "Private Room"]
        locked_access = self.room_access in ["Invite Only", "Premium Locked", "VIP Locked", "Private Communication"]
        return locked_audience or locked_access or self.allow_premium_view or self.allow_premium_join or self.vip_badge or self.private_line

    def user_can_view(self, user):
        if user.is_authenticated and user.pk == self.host_id:
            return True
        if self.status == self.STATUS_ENDED:
            return False
        if not self.is_locked:
            return True
        return user.is_authenticated

    def start(self):
        self.status = self.STATUS_LIVE
        self.started_at = self.started_at or timezone.now()
        self.ended_at = None
        self.save(update_fields=["status", "started_at", "ended_at", "updated_at"])

    def end(self):
        self.status = self.STATUS_ENDED
        self.ended_at = timezone.now()
        self.viewer_count = 0
        self.save(update_fields=["status", "ended_at", "viewer_count", "updated_at"])


class LiveComment(models.Model):
    room = models.ForeignKey(LiveRoom, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    full_name = models.CharField(max_length=140, blank=True)
    username = models.CharField(max_length=140, blank=True)
    message = models.TextField()
    is_host = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class LiveGift(models.Model):
    room = models.ForeignKey(LiveRoom, on_delete=models.CASCADE, related_name="gifts")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    sender_username = models.CharField(max_length=140, blank=True)
    gift_name = models.CharField(max_length=80)
    token_amount = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class LiveViewer(models.Model):
    room = models.ForeignKey(LiveRoom, on_delete=models.CASCADE, related_name="viewers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    channel_name = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=140, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-joined_at"]
