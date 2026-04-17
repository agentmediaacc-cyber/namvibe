from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.media import validate_image_file


class DatingProfile(models.Model):
    class Gender(models.TextChoices):
        WOMAN = "woman", "Woman"
        MAN = "man", "Man"
        NON_BINARY = "non_binary", "Non-binary"
        OTHER = "other", "Other"

    class RelationshipGoal(models.TextChoices):
        SERIOUS = "serious", "Serious"
        DATING = "dating", "Dating"
        FRIENDSHIP = "friendship", "Friendship"
        NETWORKING = "networking", "Networking"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dating_profile")
    display_name = models.CharField(max_length=120, blank=True)
    birth_date = models.DateField()
    gender = models.CharField(max_length=20, choices=Gender.choices)
    looking_for = models.JSONField(default=list, blank=True)
    bio = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    region = models.CharField(max_length=100, blank=True, db_index=True)
    country = models.CharField(max_length=80, default="Namibia")
    occupation = models.CharField(max_length=120, blank=True)
    height_cm = models.PositiveIntegerField(null=True, blank=True)
    interests = models.JSONField(default=list, blank=True)
    relationship_goal = models.CharField(max_length=20, choices=RelationshipGoal.choices, default=RelationshipGoal.DATING, db_index=True)
    is_visible = models.BooleanField(default=False, db_index=True)
    is_verified_dating = models.BooleanField(default=False)
    show_age = models.BooleanField(default=True)
    show_distance = models.BooleanField(default=True)
    max_distance_km = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_visible", "gender", "relationship_goal"]),
            models.Index(fields=["city", "region"]),
            models.Index(fields=["is_verified_dating", "created_at"]),
        ]

    def __str__(self):
        return f"{self.display_name or self.user.username} dating profile"

    @property
    def age(self):
        today = timezone.localdate()
        years = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years

    @property
    def primary_photo(self):
        return self.photos.order_by("-is_primary", "sort_order", "id").first()

    def clean(self):
        if self.birth_date and self.age < 18 and self.is_visible:
            raise ValidationError("You must be 18 or older to make a dating profile visible.")

    def save(self, *args, **kwargs):
        if not self.display_name:
            social_profile = getattr(self.user, "profile", None)
            self.display_name = getattr(social_profile, "display_name", "") or self.user.get_full_name() or self.user.username
        if self.birth_date and self.age < 18:
            self.is_visible = False
        super().save(*args, **kwargs)


class DatingPhoto(models.Model):
    dating_profile = models.ForeignKey(DatingProfile, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="dating/photos/", validators=[validate_image_file])
    sort_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "sort_order", "id"]
        indexes = [models.Index(fields=["dating_profile", "is_primary", "sort_order"])]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_primary:
            DatingPhoto.objects.filter(dating_profile=self.dating_profile).exclude(pk=self.pk).update(is_primary=False)


class DatingPreference(models.Model):
    dating_profile = models.OneToOneField(DatingProfile, on_delete=models.CASCADE, related_name="preferences")
    age_min = models.PositiveIntegerField(default=18)
    age_max = models.PositiveIntegerField(default=60)
    preferred_genders = models.JSONField(default=list, blank=True)
    preferred_region = models.CharField(max_length=100, blank=True)
    preferred_city = models.CharField(max_length=100, blank=True)
    distance_km = models.PositiveIntegerField(null=True, blank=True)

    def clean(self):
        if self.age_min < 18:
            raise ValidationError("Dating preferences must start at 18 or older.")
        if self.age_max < self.age_min:
            raise ValidationError("Maximum age must be greater than minimum age.")


class DatingLike(models.Model):
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dating_likes_sent")
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dating_likes_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["from_user", "to_user"], name="unique_dating_like"),
            models.CheckConstraint(check=~Q(from_user=models.F("to_user")), name="prevent_self_dating_like"),
        ]
        indexes = [models.Index(fields=["from_user", "created_at"]), models.Index(fields=["to_user", "created_at"])]


class DatingPass(models.Model):
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dating_passes_sent")
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dating_passes_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["from_user", "to_user"], name="unique_dating_pass"),
            models.CheckConstraint(check=~Q(from_user=models.F("to_user")), name="prevent_self_dating_pass"),
        ]
        indexes = [models.Index(fields=["from_user", "created_at"]), models.Index(fields=["to_user", "created_at"])]


class Match(models.Model):
    user_one = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dating_matches_as_one")
    user_two = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dating_matches_as_two")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user_one", "user_two"], name="unique_dating_match_pair"),
            models.CheckConstraint(check=~Q(user_one=models.F("user_two")), name="prevent_self_dating_match"),
        ]
        indexes = [models.Index(fields=["user_one", "is_active"]), models.Index(fields=["user_two", "is_active"]), models.Index(fields=["created_at"])]

    def save(self, *args, **kwargs):
        if self.user_one_id and self.user_two_id and self.user_one_id > self.user_two_id:
            self.user_one_id, self.user_two_id = self.user_two_id, self.user_one_id
        super().save(*args, **kwargs)

    def other_user(self, user):
        return self.user_two if self.user_one_id == user.id else self.user_one
