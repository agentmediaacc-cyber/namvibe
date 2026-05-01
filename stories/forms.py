from django import forms
from django.utils import timezone

from core.media import validate_story_image_file, validate_story_video_file
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

    def clean_file(self):
        file_obj = self.cleaned_data.get("file")
        media_type = self.cleaned_data.get("media_type") or self.data.get("media_type")
        if not file_obj:
            return file_obj
        try:
            if media_type == StoryItem.MediaType.PHOTO:
                validate_story_image_file(file_obj)
            elif media_type == StoryItem.MediaType.VIDEO:
                validate_story_video_file(file_obj)
        except forms.ValidationError as exc:
            raise forms.ValidationError(exc.messages[0]) from exc
        return file_obj

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs.update({"accept": "image/*,video/*"})
        self.fields["text_content"].widget.attrs.update({"placeholder": "Share a quick update, mood, or story line"})
        self.fields["caption"].widget.attrs.update({"placeholder": "Add a short caption"})

    def save(self, commit=True):
        story = super().save(commit=False)
        hours = self.cleaned_data.get("duration_hours") or 24
        story.expires_at = timezone.now() + timezone.timedelta(hours=hours)
        if commit:
            story.save()
        return story
