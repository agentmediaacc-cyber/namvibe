from django.db import models


class SystemPromoCard(models.Model):
    class Placement(models.TextChoices):
        HOMEPAGE_FEED = "homepage_feed", "Homepage feed"
        HOMEPAGE_FLOAT = "homepage_float", "Homepage float"
        SUPPORT_DASHBOARD = "support_dashboard", "Support dashboard"

    title = models.CharField(max_length=140)
    body = models.TextField()
    icon = models.CharField(max_length=16, blank=True)
    cta_label = models.CharField(max_length=80, default="Open")
    cta_url = models.CharField(max_length=240, blank=True)
    placement = models.CharField(max_length=32, choices=Placement.choices, default=Placement.HOMEPAGE_FEED, db_index=True)
    priority = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    audience = models.CharField(max_length=24, default="all", db_index=True)
    dismissible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["placement", "is_active", "priority"]),
        ]

    def __str__(self):
        return self.title
