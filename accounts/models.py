from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

from core.media import validate_image_file


class AccountProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="account_profile")
    full_name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    phone_country_code = models.CharField(max_length=8, blank=True, default="+264")
    cellphone_number = models.CharField(max_length=30, unique=True)
    residential_address = models.TextField()
    country_of_origin = models.CharField(max_length=80)
    current_country = models.CharField(max_length=80)
    profile_completed = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    verification_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} (@{self.user.username})"

    @property
    def public_label(self):
        profile = getattr(self.user, "profile", None)
        return getattr(profile, "display_name", "") or getattr(profile, "username", "") or self.user.username


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=120, blank=True)
    username = models.SlugField(max_length=150, unique=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="profiles/avatars/", blank=True, validators=[validate_image_file])
    cover_image = models.ImageField(upload_to="profiles/covers/", blank=True, validators=[validate_image_file])
    website = models.URLField(blank=True)
    town = models.CharField(max_length=120, blank=True, db_index=True)
    region = models.CharField(max_length=120, blank=True, db_index=True)
    location = models.CharField(max_length=120, blank=True, db_index=True)
    is_verified = models.BooleanField(default=False)
    is_creator = models.BooleanField(default=False)
    is_private = models.BooleanField(default=False)
    follower_count = models.PositiveIntegerField(default=0)
    following_count = models.PositiveIntegerField(default=0)
    post_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["is_creator", "is_verified"]),
            models.Index(fields=["town", "region"]),
            models.Index(fields=["location"]),
        ]

    def __str__(self):
        return f"{self.display_name or self.user.get_full_name() or self.user.username} (@{self.username})"

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.user.username
        if not self.display_name:
            self.display_name = self.username or self.user.username
        super().save(*args, **kwargs)


class AccountRole(models.Model):
    class Role(models.TextChoices):
        MEMBER = "member", "Member"
        SUPPORT = "support", "Support"
        PLATFORM_ADMIN = "platform_admin", "Platform admin"
        MASTER_ADMIN = "master_admin", "Master admin"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account_role")
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.MEMBER, db_index=True)
    supabase_uid = models.CharField(max_length=64, blank=True, db_index=True)
    can_manage_promos = models.BooleanField(default=False)
    can_manage_support = models.BooleanField(default=False)
    can_moderate_users = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["supabase_uid"]),
        ]

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def is_admin(self):
        return self.role in {self.Role.PLATFORM_ADMIN, self.Role.MASTER_ADMIN}

    @property
    def is_master_admin(self):
        return self.role == self.Role.MASTER_ADMIN


class Follow(models.Model):
    follower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following_edges")
    following = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="follower_edges")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["follower", "following"], name="unique_follow_edge"),
            models.CheckConstraint(check=~Q(follower=models.F("following")), name="prevent_self_follow"),
        ]
        indexes = [
            models.Index(fields=["follower", "created_at"]),
            models.Index(fields=["following", "created_at"]),
        ]

    def __str__(self):
        return f"{self.follower} follows {self.following}"


class FriendRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CANCELED = "canceled", "Canceled"

    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_friend_requests")
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_friend_requests")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["from_user", "to_user"], name="unique_friend_request"),
            models.CheckConstraint(check=~Q(from_user=models.F("to_user")), name="prevent_self_friend_request"),
        ]
        indexes = [
            models.Index(fields=["to_user", "status", "created_at"]),
            models.Index(fields=["from_user", "status", "created_at"]),
        ]

    def clean(self):
        if self.from_user_id and self.to_user_id and self.from_user_id == self.to_user_id:
            raise ValidationError("You cannot send a friend request to yourself.")

    def __str__(self):
        return f"{self.from_user} -> {self.to_user} ({self.status})"


class Block(models.Model):
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocking_edges")
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocked_by_edges")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_block_edge"),
            models.CheckConstraint(check=~Q(blocker=models.F("blocked")), name="prevent_self_block"),
        ]
        indexes = [
            models.Index(fields=["blocker", "created_at"]),
            models.Index(fields=["blocked", "created_at"]),
        ]

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked}"


class Mute(models.Model):
    muter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="muting_edges")
    muted = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="muted_by_edges")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["muter", "muted"], name="unique_mute_edge"),
            models.CheckConstraint(check=~Q(muter=models.F("muted")), name="prevent_self_mute"),
        ]
        indexes = [
            models.Index(fields=["muter", "created_at"]),
            models.Index(fields=["muted", "created_at"]),
        ]

    def __str__(self):
        return f"{self.muter} muted {self.muted}"


class Notification(models.Model):
    class Type(models.TextChoices):
        FOLLOW = "follow", "New follower"
        LIKE = "like", "New like"
        COMMENT = "comment", "New comment"
        FRIEND_REQUEST = "friend_request", "Friend request"
        SYSTEM = "system", "System update"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="sent_notifications")
    notification_type = models.CharField(max_length=20, choices=Type.choices)
    message = models.TextField(blank=True)
    target_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
        ]

    def __str__(self):
        return f"Notification for {self.recipient} ({self.notification_type})"


def notify(recipient, notification_type, sender=None, message="", target_url=""):
    if recipient == sender:
        return None
    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        sender=sender,
        message=message,
        target_url=target_url,
    )


def refresh_profile_counts(user):
    profile = getattr(user, "profile", None)
    if not profile:
        return
    Profile.objects.filter(pk=profile.pk).update(
        follower_count=Follow.objects.filter(following=user).count(),
        following_count=Follow.objects.filter(follower=user).count(),
    )


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    Profile.objects.get_or_create(
        user=instance,
        defaults={
            "username": instance.username,
            "display_name": instance.username,
        },
    )
    AccountRole.objects.get_or_create(user=instance)


@receiver(post_save, sender=Follow)
def update_follow_counts_on_save(sender, instance, **kwargs):
    refresh_profile_counts(instance.follower)
    refresh_profile_counts(instance.following)


@receiver(post_delete, sender=Follow)
def update_follow_counts_on_delete(sender, instance, **kwargs):
    refresh_profile_counts(instance.follower)
    refresh_profile_counts(instance.following)
