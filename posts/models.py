import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import Block, Follow, FriendRequest
from core.media import validate_image_file, validate_media_file, validate_video_file


class PostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Post.Status.PUBLISHED, published_at__isnull=False)

    def visible_to(self, user):
        queryset = self.exclude(status__in=[Post.Status.DELETED, Post.Status.ARCHIVED])
        public_filter = Q(audience=Post.Audience.PUBLIC, status=Post.Status.PUBLISHED)

        if not user.is_authenticated:
            return queryset.filter(public_filter)

        blocked_user_ids = set(
            Block.objects.filter(Q(blocker=user) | Q(blocked=user)).values_list("blocker_id", "blocked_id")
        )
        hidden_ids = {item for pair in blocked_user_ids for item in pair if item != user.id}

        following_ids = Follow.objects.filter(follower=user).values_list("following_id", flat=True)
        friend_ids = FriendRequest.objects.filter(
            Q(from_user=user) | Q(to_user=user),
            status=FriendRequest.Status.ACCEPTED,
        ).values_list("from_user_id", "to_user_id")
        friend_user_ids = {item for pair in friend_ids for item in pair if item != user.id}

        visibility_filter = (
            public_filter
            | Q(author=user)
            | Q(audience=Post.Audience.FOLLOWERS, author_id__in=following_ids, status=Post.Status.PUBLISHED)
            | Q(audience=Post.Audience.FRIENDS, author_id__in=friend_user_ids, status=Post.Status.PUBLISHED)
            | Q(audience=Post.Audience.SPECIFIC_USER, target_user=user, status=Post.Status.PUBLISHED)
            | Q(
                audience=Post.Audience.COMMUNITY,
                community__memberships__user=user,
                community__memberships__status="active",
                status=Post.Status.PUBLISHED,
            )
        )
        return queryset.exclude(author_id__in=hidden_ids).filter(visibility_filter).distinct()


class Post(models.Model):
    class PostType(models.TextChoices):
        TEXT = "text", "Text"
        PHOTO = "photo", "Photo"
        VIDEO = "video", "Video"
        FLYER = "flyer", "Flyer"
        STORY = "story", "Story"
        REEL = "reel", "Reel"
        LIVE = "live", "Live"
        POLL = "poll", "Poll"

    class Audience(models.TextChoices):
        PUBLIC = "public", "Public"
        FOLLOWERS = "followers", "Followers"
        FRIENDS = "friends", "Friends"
        PRIVATE = "private", "Private"
        SPECIFIC_USER = "specific_user", "Specific user"
        COMMUNITY = "community", "Community"

    class ShareTarget(models.TextChoices):
        MAIN_FEED = "main_feed", "Main feed"
        PROFILE = "profile", "Profile"
        COMMUNITY = "community", "Community"
        STORY = "story", "Story"
        REELS = "reels", "Reels"
        LIVE = "live", "Live"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"
        DELETED = "deleted", "Deleted"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    community = models.ForeignKey("communities.Community", on_delete=models.SET_NULL, null=True, blank=True, related_name="posts")
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="targeted_posts")
    post_type = models.CharField(max_length=16, choices=PostType.choices, default=PostType.TEXT, db_index=True)
    title = models.CharField(max_length=180, blank=True)
    caption = models.TextField(blank=True)
    hashtags = models.JSONField(default=list, blank=True)
    mentions = models.JSONField(default=list, blank=True)
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.PUBLIC, db_index=True)
    share_target = models.CharField(max_length=20, choices=ShareTarget.choices, default=ShareTarget.MAIN_FEED)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    allow_comments = models.BooleanField(default=True)
    allow_sharing = models.BooleanField(default=True)
    save_to_story = models.BooleanField(default=False)
    premium_badge = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    save_count = models.PositiveIntegerField(default=0)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["author"]),
            models.Index(fields=["status"]),
            models.Index(fields=["audience"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["published_at"]),
            models.Index(fields=["post_type"]),
            models.Index(fields=["author", "published_at"]),
            models.Index(fields=["post_type", "published_at"]),
            models.Index(fields=["audience", "status"]),
            models.Index(fields=["status", "published_at"]),
        ]

    def __str__(self):
        label = self.title or self.caption[:60] or self.get_post_type_display()
        return f"{label} by {self.author}"

    def clean(self):
        if self.audience == self.Audience.COMMUNITY and not self.community_id:
            raise ValidationError("Community posts require a community.")
        if self.audience == self.Audience.SPECIFIC_USER and not self.target_user_id:
            raise ValidationError("Specific user posts require a target user.")

    def publish(self):
        self.status = self.Status.PUBLISHED
        if not self.published_at:
            self.published_at = timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])

    def soft_delete(self):
        self.status = self.Status.DELETED
        self.save(update_fields=["status", "updated_at"])

    @property
    def primary_media(self):
        return self.media.order_by("sort_order", "id").first()


class PostMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"
        LOGO = "logo", "Logo"

    class DisplayMode(models.TextChoices):
        COVER = "cover", "Cover"
        CONTAIN = "contain", "Contain"
        FILL = "fill", "Fill"

    class CropStyle(models.TextChoices):
        SQUARE = "square", "Square"
        PORTRAIT = "portrait", "Portrait"
        LANDSCAPE = "landscape", "Landscape"
        STORY = "story", "Story"
        REEL = "reel", "Reel"

    class ImageEffect(models.TextChoices):
        NONE = "none", "None"
        WARM = "warm", "Warm"
        COOL = "cool", "Cool"
        CINEMATIC = "cinematic", "Cinematic"
        VIVID = "vivid", "Vivid"
        BW = "bw", "Black and white"

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media")
    media_type = models.CharField(max_length=12, choices=MediaType.choices)
    file = models.FileField(upload_to="posts/media/")
    thumbnail = models.ImageField(upload_to="posts/thumbnails/", blank=True, validators=[validate_image_file])
    alt_text = models.CharField(max_length=180, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    display_mode = models.CharField(max_length=12, choices=DisplayMode.choices, default=DisplayMode.COVER)
    crop_style = models.CharField(max_length=16, choices=CropStyle.choices, default=CropStyle.SQUARE)
    image_effect = models.CharField(max_length=16, choices=ImageEffect.choices, default=ImageEffect.NONE)
    overlay_text = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        indexes = [models.Index(fields=["post", "sort_order"])]

    def clean(self):
        if self.file:
            validate_media_file(self.file, self.media_type)

    def __str__(self):
        return f"{self.get_media_type_display()} for {self.post_id}"


class Poll(models.Model):
    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name="poll")
    question = models.CharField(max_length=220)
    multiple_choice = models.BooleanField(default=False)
    closes_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.question


class PollOption(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=140)
    vote_count = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.text


class PollVote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    option = models.ForeignKey(PollOption, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="poll_votes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "poll"], name="unique_user_poll_vote"),
        ]

    def clean(self):
        if self.option_id and self.poll_id and self.option.poll_id != self.poll_id:
            raise ValidationError("Poll option does not belong to this poll.")


class FlyerMeta(models.Model):
    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name="flyer_meta")
    flyer_title = models.CharField(max_length=180)
    body = models.TextField(blank=True)
    call_to_action = models.CharField(max_length=120, blank=True)
    background_style = models.CharField(max_length=80, default="gradient-violet")
    text_color = models.CharField(max_length=32, default="#ffffff")
    layout_style = models.CharField(max_length=40, default="centered")

    def __str__(self):
        return self.flyer_title


class LiveAnnouncement(models.Model):
    class AccessType(models.TextChoices):
        PUBLIC = "public", "Public"
        PRIVATE = "private", "Private"
        VIP = "vip", "VIP"
        PAID = "paid", "Paid"

    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name="live_announcement")
    scheduled_for = models.DateTimeField()
    stream_title = models.CharField(max_length=180)
    access_type = models.CharField(max_length=16, choices=AccessType.choices, default=AccessType.PUBLIC)
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.stream_title


class Like(models.Model):
    class ReactionType(models.TextChoices):
        LIKE = "like", "Like"
        LOVE = "love", "Love"
        FIRE = "fire", "Fire"
        LAUGH = "laugh", "Laugh"
        WOW = "wow", "Wow"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_likes")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    reaction_type = models.CharField(max_length=12, choices=ReactionType.choices, default=ReactionType.LIKE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="unique_user_post_like"),
        ]
        indexes = [
            models.Index(fields=["post", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user} {self.reaction_type} {self.post_id}"


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_comments")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies")
    body = models.TextField()
    is_pinned = models.BooleanField(default=False)
    like_count = models.PositiveIntegerField(default=0)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "created_at"]
        indexes = [
            models.Index(fields=["post", "parent", "created_at"]),
            models.Index(fields=["author", "created_at"]),
            models.Index(fields=["post", "is_pinned"]),
        ]

    def __str__(self):
        return f"Comment by {self.author} on {self.post_id}"


class CommentReaction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comment_reactions")
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="reactions")
    reaction_type = models.CharField(max_length=12, choices=Like.ReactionType.choices, default=Like.ReactionType.LIKE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "comment"], name="unique_user_comment_reaction"),
        ]
        indexes = [
            models.Index(fields=["comment", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]


class Share(models.Model):
    class Target(models.TextChoices):
        FEED = "feed", "Feed"
        PROFILE = "profile", "Profile"
        COMMUNITY = "community", "Community"
        DIRECT = "direct", "Direct"

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="shares")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_shares")
    target = models.CharField(max_length=16, choices=Target.choices, default=Target.FEED)
    message = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["post", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["target", "created_at"]),
        ]


class Save(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="saves")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_saves")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="unique_user_post_save"),
        ]
        indexes = [
            models.Index(fields=["post", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]


class PostView(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="post_views")
    session_key = models.CharField(max_length=80, blank=True, db_index=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["post", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["session_key", "created_at"]),
        ]


class Report(models.Model):
    class Reason(models.TextChoices):
        SPAM = "spam", "Spam"
        HARASSMENT = "harassment", "Harassment"
        HATE = "hate", "Hate speech"
        NUDITY = "nudity", "Nudity"
        VIOLENCE = "violence", "Violence"
        SCAM = "scam", "Scam"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWING = "reviewing", "Reviewing"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True, related_name="reports")
    reported_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="received_reports")
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["post", "status", "created_at"]),
            models.Index(fields=["reported_user", "status", "created_at"]),
            models.Index(fields=["reporter", "created_at"]),
        ]

    def clean(self):
        if not self.post_id and not self.reported_user_id:
            raise ValidationError("Report a post or a user.")
