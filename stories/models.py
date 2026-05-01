from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import Block, Follow, FriendRequest
from core.media import validate_story_image_file, validate_story_video_file


class StoryQuerySet(models.QuerySet):
    def active(self):
        return self.filter(expires_at__gt=timezone.now())

    def visible_to(self, user):
        qs = self.active()
        public = Q(audience=StoryItem.Audience.PUBLIC)
        if not user.is_authenticated:
            return qs.filter(public)

        blocked_pairs = Block.objects.filter(Q(blocker=user) | Q(blocked=user)).values_list("blocker_id", "blocked_id")
        hidden_ids = {item for pair in blocked_pairs for item in pair if item != user.id}
        followed_ids = Follow.objects.filter(follower=user).values_list("following_id", flat=True)
        friend_pairs = FriendRequest.objects.filter(
            Q(from_user=user) | Q(to_user=user),
            status=FriendRequest.Status.ACCEPTED,
        ).values_list("from_user_id", "to_user_id")
        friend_ids = {item for pair in friend_pairs for item in pair if item != user.id}
        return qs.exclude(author_id__in=hidden_ids).filter(
            public
            | Q(author=user)
            | Q(audience=StoryItem.Audience.FOLLOWERS, author_id__in=followed_ids)
            | Q(audience=StoryItem.Audience.FRIENDS, author_id__in=friend_ids)
        ).distinct()


class StoryItem(models.Model):
    class MediaType(models.TextChoices):
        TEXT = "text", "Text"
        PHOTO = "photo", "Photo"
        VIDEO = "video", "Video"

    class Audience(models.TextChoices):
        PUBLIC = "public", "Public"
        FOLLOWERS = "followers", "Followers"
        FRIENDS = "friends", "Friends"
        PRIVATE = "private", "Only me"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stories")
    media_type = models.CharField(max_length=12, choices=MediaType.choices, default=MediaType.TEXT)
    file = models.FileField(upload_to="stories/", blank=True)
    text_content = models.TextField(blank=True)
    caption = models.CharField(max_length=220, blank=True)
    background_style = models.CharField(max_length=80, default="midnight")
    text_style = models.CharField(max_length=80, default="clean")
    link_url = models.URLField(blank=True)
    link_label = models.CharField(max_length=80, blank=True)
    audience = models.CharField(max_length=16, choices=Audience.choices, default=Audience.PUBLIC, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)

    objects = StoryQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["author", "created_at"]),
            models.Index(fields=["audience", "expires_at"]),
            models.Index(fields=["expires_at", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        super().save(*args, **kwargs)

    def clean(self):
        if self.file and self.media_type == self.MediaType.PHOTO:
            validate_story_image_file(self.file)
        if self.file and self.media_type == self.MediaType.VIDEO:
            validate_story_video_file(self.file)

    def __str__(self):
        return f"{self.author} story"


class StoryView(models.Model):
    story = models.ForeignKey(StoryItem, on_delete=models.CASCADE, related_name="views")
    viewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="story_views")
    session_key = models.CharField(max_length=80, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["story", "created_at"]),
            models.Index(fields=["viewer", "created_at"]),
        ]


class StoryReaction(models.Model):
    class ReactionType(models.TextChoices):
        LIKE = "like", "Like"
        LOVE = "love", "Love"
        FIRE = "fire", "Fire"
        WOW = "wow", "Wow"

    story = models.ForeignKey(StoryItem, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="story_reactions")
    reaction_type = models.CharField(max_length=12, choices=ReactionType.choices, default=ReactionType.LIKE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["story", "user"], name="unique_story_reaction")]
        indexes = [models.Index(fields=["story", "created_at"]), models.Index(fields=["user", "created_at"])]


class StoryComment(models.Model):
    story = models.ForeignKey(StoryItem, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="story_comments")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["story", "created_at"]), models.Index(fields=["author", "created_at"])]


class StoryShare(models.Model):
    story = models.ForeignKey(StoryItem, on_delete=models.CASCADE, related_name="shares")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="story_shares")
    target = models.CharField(max_length=24, default="forward")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["story", "created_at"]), models.Index(fields=["user", "created_at"])]
