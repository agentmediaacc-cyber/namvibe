from django import forms

from .models import Message


class MessageForm(forms.Form):
    text = forms.CharField(required=False, widget=forms.Textarea)
    attachment = forms.FileField(required=False)
    reply_to = forms.IntegerField(required=False)
    forward_to = forms.IntegerField(required=False)

    def clean(self):
        cleaned = super().clean()
        text = (cleaned.get("text") or "").strip()
        attachment = cleaned.get("attachment")
        forward_to = cleaned.get("forward_to")

        if not text and not attachment and not forward_to:
            raise forms.ValidationError("Write a message, attach a file, or choose a message to forward.")

        return cleaned


def attachment_type_for(file_obj):
    if not file_obj:
        return Message.ATTACHMENT_NONE

    content_type = getattr(file_obj, "content_type", "") or ""
    if content_type.startswith("image/"):
        return Message.ATTACHMENT_IMAGE
    if content_type.startswith("video/"):
        return Message.ATTACHMENT_VIDEO
    return Message.ATTACHMENT_FILE
