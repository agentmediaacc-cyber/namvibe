from django import forms
from django.utils import timezone

from .models import LiveSession


class LiveSessionForm(forms.ModelForm):
    start_mode = forms.ChoiceField(choices=[("now", "Start now"), ("schedule", "Schedule later")], initial="now")
    category = forms.ChoiceField(
        choices=[
            ("dating", "Dating"),
            ("music", "Music"),
            ("creator", "Creator"),
            ("pink_friday", "Pink Friday"),
            ("community", "Community"),
        ],
        initial="creator",
        required=False,
    )

    class Meta:
        model = LiveSession
        fields = ("title", "description", "thumbnail", "starts_at", "access_type", "chat_enabled", "is_featured")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        self.host = kwargs.pop("host", None)
        super().__init__(*args, **kwargs)
        self.fields["is_featured"].required = False
        self.fields["title"].widget.attrs.update({"placeholder": "Name your live room"})
        self.fields["description"].widget.attrs.update({"placeholder": "Tell people what this live session is about"})
        if not self.instance.pk:
            self.fields["starts_at"].initial = timezone.now()

    def save(self, commit=True):
        session = super().save(commit=False)
        if self.host and not session.host_id:
            session.host = self.host
        if self.cleaned_data.get("start_mode") == "now":
            session.status = LiveSession.Status.LIVE
            session.starts_at = timezone.now()
        else:
            session.status = LiveSession.Status.SCHEDULED
        if commit:
            session.save()
        return session


class LiveMessageForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), max_length=1000)
