from django import forms
from django.utils import timezone

from .models import DatingPhoto, DatingPreference, DatingProfile


def parse_csv(value):
    return [item.strip() for item in (value or "").replace("\n", ",").split(",") if item.strip()]


class DatingProfileForm(forms.ModelForm):
    looking_for_text = forms.CharField(required=False, help_text="Comma separated genders.")
    interests_text = forms.CharField(required=False, help_text="Comma separated interests.")
    photos = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={"allow_multiple_selected": True}))
    primary_photo_id = forms.IntegerField(required=False)

    class Meta:
        model = DatingProfile
        fields = (
            "display_name",
            "birth_date",
            "gender",
            "bio",
            "city",
            "region",
            "country",
            "occupation",
            "height_cm",
            "relationship_goal",
            "is_visible",
            "show_age",
            "show_distance",
            "max_distance_km",
        )
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "bio": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["looking_for_text"].initial = ", ".join(self.instance.looking_for or [])
            self.fields["interests_text"].initial = ", ".join(self.instance.interests or [])

    def clean(self):
        cleaned = super().clean()
        birth_date = cleaned.get("birth_date")
        is_visible = cleaned.get("is_visible")
        if birth_date:
            today = timezone.localdate()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            if age < 18 and is_visible:
                self.add_error("is_visible", "You must be 18 or older to make your dating profile visible.")
        return cleaned

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user and not profile.user_id:
            profile.user = self.user
        profile.looking_for = parse_csv(self.cleaned_data.get("looking_for_text"))
        profile.interests = parse_csv(self.cleaned_data.get("interests_text"))
        if commit:
            profile.save()
            for index, image in enumerate(self.files.getlist("photos")):
                DatingPhoto.objects.create(
                    dating_profile=profile,
                    image=image,
                    sort_order=profile.photos.count() + index,
                    is_primary=not profile.photos.exists(),
                )
            primary_id = self.cleaned_data.get("primary_photo_id")
            if primary_id:
                photo = profile.photos.filter(id=primary_id).first()
                if photo:
                    photo.is_primary = True
                    photo.save(update_fields=["is_primary"])
        return profile


class DatingPreferenceForm(forms.ModelForm):
    preferred_genders_text = forms.CharField(required=False)

    class Meta:
        model = DatingPreference
        fields = ("age_min", "age_max", "preferred_region", "preferred_city", "distance_km")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["preferred_genders_text"].initial = ", ".join(self.instance.preferred_genders or [])

    def save(self, commit=True):
        preference = super().save(commit=False)
        preference.preferred_genders = parse_csv(self.cleaned_data.get("preferred_genders_text"))
        if commit:
            preference.save()
        return preference
