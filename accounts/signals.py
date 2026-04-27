import logging
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        try:
            Profile.objects.get_or_create(
                user=instance,
                defaults={
                    "username": instance.username,
                    "display_name": instance.username,
                },
            )
        except Exception as exc:
            logger.error("Failed to create Profile for user %s: %s", instance.username, exc)
