from django.db import models
from django.utils import timezone

from core.media import validate_image_file, validate_video_file


class AdvertisementQuerySet(models.QuerySet):
    def active_for(self, placement):
        now = timezone.now()
        return self.filter(
            placement=placement,
            status=Advertisement.Status.ACTIVE,
            is_public=True,
            starts_at__lte=now,
        ).filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now)).order_by("-priority", "-created_at")


class Advertisement(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    class Placement(models.TextChoices):
        HOMEPAGE_TOP = "homepage_top", "Homepage top"
        HOMEPAGE_MID = "homepage_mid", "Homepage mid"
        HOMEPAGE_SIDEBAR = "homepage_sidebar", "Homepage sidebar"
        DISCOVER = "discover", "Discover"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        EXPIRED = "expired", "Expired"

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True, null=True)
    sponsor_name = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    media_type = models.CharField(max_length=12, choices=MediaType.choices, default=MediaType.IMAGE)
    image = models.ImageField(upload_to="ads/images/", blank=True, validators=[validate_image_file])
    video = models.FileField(upload_to="ads/videos/", blank=True, validators=[validate_video_file])
    destination_url = models.URLField(blank=True)
    call_to_action = models.CharField(max_length=80, default="Learn more")
    placement = models.CharField(max_length=24, choices=Placement.choices, default=Placement.HOMEPAGE_MID, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    starts_at = models.DateTimeField(default=timezone.now, db_index=True)
    ends_at = models.DateTimeField(blank=True, null=True, db_index=True)
    priority = models.IntegerField(default=0, db_index=True)
    is_public = models.BooleanField(default=True)
    impression_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AdvertisementQuerySet.as_manager()

    class Meta:
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["placement", "status", "starts_at", "ends_at"]),
            models.Index(fields=["is_public", "priority"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.sponsor_name})"

    @property
    def is_active_now(self):
        now = timezone.now()
        return self.status == self.Status.ACTIVE and self.is_public and self.starts_at <= now and (self.ends_at is None or self.ends_at >= now)
