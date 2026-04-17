import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.media import validate_image_file


class LiveSession(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        ENDED = "ended", "Ended"

    class AccessType(models.TextChoices):
        PUBLIC = "public", "Public"
        FOLLOWERS = "followers", "Followers"
        PREMIUM = "premium", "Premium"
        PRIVATE = "private", "Private"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="live_sessions")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED, db_index=True)
    thumbnail = models.ImageField(upload_to="live/thumbnails/", blank=True, validators=[validate_image_file])
    starts_at = models.DateTimeField(default=timezone.now, db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    access_type = models.CharField(max_length=16, choices=AccessType.choices, default=AccessType.PUBLIC, db_index=True)
    stream_key = models.CharField(max_length=120, blank=True)
    playback_url = models.URLField(blank=True)
    chat_enabled = models.BooleanField(default=True)
    viewer_count = models.PositiveIntegerField(default=0)
    peak_viewer_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_featured", "-viewer_count", "-starts_at"]
        indexes = [
            models.Index(fields=["status", "starts_at"]),
            models.Index(fields=["host", "status"]),
            models.Index(fields=["access_type", "status"]),
            models.Index(fields=["is_featured", "status", "viewer_count"]),
        ]

    def __str__(self):
        return self.title

    def start(self):
        self.status = self.Status.LIVE
        self.starts_at = self.starts_at or timezone.now()
        self.ends_at = None
        self.save(update_fields=["status", "starts_at", "ends_at", "updated_at"])

    def end(self):
        self.status = self.Status.ENDED
        self.ends_at = timezone.now()
        self.viewer_count = 0
        self.save(update_fields=["status", "ends_at", "viewer_count", "updated_at"])


class LiveMessage(models.Model):
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="live_messages")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user} in {self.session}"


class LiveReaction(models.Model):
    class ReactionType(models.TextChoices):
        LIKE = "like", "Like"
        LOVE = "love", "Love"
        FIRE = "fire", "Fire"
        WOW = "wow", "Wow"

    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="live_reactions")
    reaction_type = models.CharField(max_length=12, choices=ReactionType.choices, default=ReactionType.LIKE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "user"], name="unique_live_reaction"),
        ]
        indexes = [
            models.Index(fields=["session", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]


class LiveModerator(models.Model):
    class Role(models.TextChoices):
        MODERATOR = "moderator", "Moderator"
        PRODUCER = "producer", "Producer"

    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name="moderators")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="live_moderation_roles")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MODERATOR)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "user"], name="unique_live_moderator"),
        ]
        indexes = [models.Index(fields=["session", "role"])]


class LiveGift(models.Model):
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name="gifts")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="live_gifts_sent")
    gift_name = models.CharField(max_length=80)
    token_amount = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["session", "created_at"]), models.Index(fields=["sender", "created_at"])]


class LiveAccessPurchase(models.Model):
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name="access_purchases")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="live_access_purchases")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "user"], name="unique_live_access_purchase"),
        ]
        indexes = [models.Index(fields=["session", "is_active"]), models.Index(fields=["user", "created_at"])]
