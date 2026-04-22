from django import forms
from django.utils import timezone

from .models import StoryItem


class StoryCreateForm(forms.ModelForm):
    duration_hours = forms.IntegerField(min_value=1, max_value=48, required=False, initial=24)

    class Meta:
        model = StoryItem
        fields = (
            "media_type",
            "file",
            "text_content",
            "caption",
            "background_style",
            "text_style",
            "link_url",
            "link_label",
            "audience",
        )
        widgets = {
            "text_content": forms.Textarea(attrs={"rows": 5, "placeholder": "Tell your story"}),
            "caption": forms.TextInput(attrs={"placeholder": "Add a caption"}),
            "link_url": forms.URLInput(attrs={"placeholder": "https://"}),
            "link_label": forms.TextInput(attrs={"placeholder": "Link label"}),
        }

    def clean(self):
        cleaned = super().clean()
        media_type = cleaned.get("media_type")
        file_obj = cleaned.get("file")
        text = cleaned.get("text_content", "").strip()
        if media_type == StoryItem.MediaType.TEXT and not text:
            self.add_error("text_content", "Write story text.")
        if media_type in {StoryItem.MediaType.PHOTO, StoryItem.MediaType.VIDEO} and not file_obj:
            self.add_error("file", "Upload a file for this story type.")
        return cleaned

    def save(self, commit=True):
        story = super().save(commit=False)
        hours = self.cleaned_data.get("duration_hours") or 24
        story.expires_at = timezone.now() + timezone.timedelta(hours=hours)
        if commit:
            story.save()
        return story
