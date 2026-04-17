from django import forms

from .models import Community


class CommunityForm(forms.ModelForm):
    class Meta:
        model = Community
        fields = ("name", "slug", "description", "avatar", "cover", "privacy")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_slug(self):
        slug = self.cleaned_data["slug"].strip().lower()
        qs = Community.objects.filter(slug__iexact=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A community already uses this slug.")
        return slug
