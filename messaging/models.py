from django.db import models
from django.conf import settings
from django.utils import timezone


class Conversation(models.Model):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return "Conversation " + ", ".join(self.participants.values_list("username", flat=True)[:4])

    def other_participant(self, user):
        return self.participants.exclude(pk=user.pk).first()

    def unread_count_for(self, user):
        return self.messages.exclude(sender=user).filter(read_at__isnull=True).count()

    def mark_read_for(self, user):
        return self.messages.exclude(sender=user).filter(read_at__isnull=True).update(read_at=timezone.now())


class Message(models.Model):
    ATTACHMENT_NONE = "none"
    ATTACHMENT_IMAGE = "image"
    ATTACHMENT_VIDEO = "video"
    ATTACHMENT_FILE = "file"
    ATTACHMENT_CHOICES = [
        (ATTACHMENT_NONE, "None"),
        (ATTACHMENT_IMAGE, "Image"),
        (ATTACHMENT_VIDEO, "Video"),
        (ATTACHMENT_FILE, "File"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    text = models.TextField(blank=True)
    attachment = models.FileField(upload_to="messages/%Y/%m/", blank=True, null=True)
    attachment_type = models.CharField(max_length=12, choices=ATTACHMENT_CHOICES, default=ATTACHMENT_NONE)
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="replies",
    )
    forwarded_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="forwards",
    )
    read_at = models.DateTimeField(blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender} in conversation {self.conversation_id}"

    @property
    def is_read(self):
        return self.read_at is not None

    @property
    def is_deleted(self):
        return self.deleted_at is not None
