from django.db import models
from django.contrib.auth.models import User


class AccountProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="account_profile")
    full_name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    cellphone_number = models.CharField(max_length=30, unique=True)
    residential_address = models.TextField()
    country_of_origin = models.CharField(max_length=80)
    current_country = models.CharField(max_length=80)
    profile_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} (@{self.user.username})"
