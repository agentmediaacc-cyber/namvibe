from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from communities.models import Community
from core.media import validate_image_file, validate_video_file
from .models import FlyerMeta, LiveAnnouncement, Poll, Post, PostMedia


def parse_chip_list(value):
    if not value:
        return []
    normalized = value.replace(",", " ").replace("\n", " ")
    return [item.strip() for item in normalized.split(" ") if item.strip()]


class BasePostForm(forms.ModelForm):
    target_username = forms.CharField(max_length=150, required=False)
    community_slug = forms.CharField(max_length=140, required=False)
    media_file = forms.FileField(required=False)
    save_draft = forms.BooleanField(required=False)
    hashtags_text = forms.CharField(max_length=320, required=False)
    mentions_text = forms.CharField(max_length=320, required=False)

    class Meta:
        model = Post
        fields = (
            "post_type",
            "title",
            "caption",
            "audience",
            "share_target",
            "allow_comments",
            "allow_sharing",
            "save_to_story",
            "premium_badge",
            "is_sensitive",
        )
        widgets = {
            "caption": forms.Textarea(attrs={"rows": 5}),
            "post_type": forms.HiddenInput(),
        }

    def __init__(self, *args, author=None, **kwargs):
        self.author = author
        super().__init__(*args, **kwargs)
        self.fields["allow_comments"].initial = True
        self.fields["allow_sharing"].initial = True
        self.fields["title"].widget.attrs.update({"placeholder": "Add a title or headline"})
        self.fields["caption"].widget.attrs.update({"placeholder": "Write a caption for your post..."})
        self.fields["hashtags_text"].widget.attrs.update({"placeholder": "#namvibe #windhoek"})
        self.fields["mentions_text"].widget.attrs.update({"placeholder": "@friend @creator"})
        self.fields["target_username"].widget.attrs.update({"placeholder": "@username"})
        self.fields["community_slug"].widget.attrs.update({"placeholder": "community-slug"})
        self.fields["media_file"].widget.attrs.update({"accept": "image/*,video/*"})
        if self.instance.pk:
            self.fields["hashtags_text"].initial = " ".join(self.instance.hashtags or [])
            self.fields["mentions_text"].initial = " ".join(self.instance.mentions or [])
            self.fields["target_username"].initial = getattr(self.instance.target_user, "username", "")
            self.fields["community_slug"].initial = getattr(self.instance.community, "slug", "")

    def clean(self):
        cleaned = super().clean()
        audience = cleaned.get("audience")
        target_username = cleaned.get("target_username", "").lstrip("@").strip()
        community_slug = cleaned.get("community_slug", "").strip()

        cleaned["target_user"] = None
        cleaned["community"] = None

        if audience == Post.Audience.SPECIFIC_USER:
            if not target_username:
                self.add_error("target_username", "Choose the user who can see this post.")
            else:
                user = get_user_model().objects.filter(username__iexact=target_username).first()
                if not user:
                    self.add_error("target_username", "That user was not found.")
                else:
                    cleaned["target_user"] = user

        if audience == Post.Audience.COMMUNITY:
            if not community_slug:
                self.add_error("community_slug", "Choose a community.")
            else:
                community = Community.objects.filter(slug__iexact=community_slug).first()
                if not community:
                    self.add_error("community_slug", "That community was not found.")
                else:
                    cleaned["community"] = community
        return cleaned

    def save(self, commit=True):
        post = super().save(commit=False)
        if self.author and not post.author_id:
            post.author = self.author
        post.hashtags = parse_chip_list(self.cleaned_data.get("hashtags_text"))
        post.mentions = parse_chip_list(self.cleaned_data.get("mentions_text"))
        post.target_user = self.cleaned_data.get("target_user")
        post.community = self.cleaned_data.get("community")
        if self.cleaned_data.get("save_draft"):
            post.status = Post.Status.DRAFT
            post.published_at = None
        elif post.status == Post.Status.DRAFT or not post.published_at:
            post.status = Post.Status.PUBLISHED
            post.published_at = timezone.now()
        if commit:
            post.save()
            self.save_media(post)
        return post

    def save_media(self, post):
        media_file = self.cleaned_data.get("media_file")
        if not media_file:
            return None
        media_type = PostMedia.MediaType.VIDEO if self.cleaned_data.get("post_type") in {Post.PostType.VIDEO, Post.PostType.REEL} else PostMedia.MediaType.IMAGE
        return PostMedia.objects.create(
            post=post,
            media_type=media_type,
            file=media_file,
            display_mode=self.data.get("display_mode") or PostMedia.DisplayMode.COVER,
            crop_style=self.data.get("crop_style") or PostMedia.CropStyle.SQUARE,
            image_effect=self.data.get("image_effect") or PostMedia.ImageEffect.NONE,
            overlay_text=self.data.get("overlay_text", ""),
        )


class TextPostForm(BasePostForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["post_type"].initial = Post.PostType.TEXT


class PhotoPostForm(BasePostForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["media_file"].widget.attrs.update({"accept": "image/jpeg,image/png,image/webp,image/gif"})

    def clean_media_file(self):
        media_file = self.cleaned_data.get("media_file")
        if media_file:
            try:
                validate_image_file(media_file)
            except forms.ValidationError as exc:
                raise forms.ValidationError(exc.messages[0]) from exc
        elif not self.instance.pk:
            raise forms.ValidationError("Upload an image.")
        return media_file


class VideoPostForm(BasePostForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["media_file"].widget.attrs.update({"accept": "video/mp4,video/quicktime,video/webm"})

    def clean_media_file(self):
        media_file = self.cleaned_data.get("media_file")
        if media_file:
            try:
                validate_video_file(media_file)
            except forms.ValidationError as exc:
                raise forms.ValidationError(exc.messages[0]) from exc
        elif not self.instance.pk:
            raise forms.ValidationError("Upload a video.")
        return media_file


class StoryPostForm(PhotoPostForm):
    pass


class ReelPostForm(VideoPostForm):
    pass


class FlyerPostForm(BasePostForm):
    flyer_title = forms.CharField(max_length=180)
    flyer_body = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    flyer_cta = forms.CharField(max_length=120, required=False)
    flyer_background = forms.CharField(max_length=80, required=False, initial="gradient-violet")
    flyer_text_color = forms.CharField(max_length=32, required=False, initial="#ffffff")
    flyer_layout = forms.CharField(max_length=40, required=False, initial="centered")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        flyer = getattr(self.instance, "flyer_meta", None)
        if flyer:
            self.fields["flyer_title"].initial = flyer.flyer_title
            self.fields["flyer_body"].initial = flyer.body
            self.fields["flyer_cta"].initial = flyer.call_to_action
            self.fields["flyer_background"].initial = flyer.background_style
            self.fields["flyer_text_color"].initial = flyer.text_color
            self.fields["flyer_layout"].initial = flyer.layout_style

    def save(self, commit=True):
        post = super().save(commit=commit)
        if commit:
            FlyerMeta.objects.update_or_create(
                post=post,
                defaults={
                    "flyer_title": self.cleaned_data["flyer_title"],
                    "body": self.cleaned_data.get("flyer_body", ""),
                    "call_to_action": self.cleaned_data.get("flyer_cta", ""),
                    "background_style": self.cleaned_data.get("flyer_background") or "gradient-violet",
                    "text_color": self.cleaned_data.get("flyer_text_color") or "#ffffff",
                    "layout_style": self.cleaned_data.get("flyer_layout") or "centered",
                },
            )
        return post


class PollPostForm(BasePostForm):
    poll_question = forms.CharField(max_length=220)
    poll_options = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))
    poll_multiple_choice = forms.BooleanField(required=False)
    poll_closes_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        poll = getattr(self.instance, "poll", None)
        if poll:
            self.fields["poll_question"].initial = poll.question
            self.fields["poll_options"].initial = "\n".join(poll.options.values_list("text", flat=True))
            self.fields["poll_multiple_choice"].initial = poll.multiple_choice
            self.fields["poll_closes_at"].initial = poll.closes_at

    def clean_poll_options(self):
        options = [item.strip() for item in self.cleaned_data["poll_options"].splitlines() if item.strip()]
        if len(options) < 2:
            raise forms.ValidationError("Add at least two poll options.")
        if len(options) > 8:
            raise forms.ValidationError("Use eight poll options or fewer.")
        return options

    def save(self, commit=True):
        post = super().save(commit=commit)
        if commit:
            poll, _ = Poll.objects.update_or_create(
                post=post,
                defaults={
                    "question": self.cleaned_data["poll_question"],
                    "multiple_choice": self.cleaned_data.get("poll_multiple_choice", False),
                    "closes_at": self.cleaned_data.get("poll_closes_at"),
                },
            )
            poll.options.all().delete()
            for index, option_text in enumerate(self.cleaned_data["poll_options"]):
                poll.options.create(text=option_text, sort_order=index)
        return post


class LiveAnnouncementPostForm(BasePostForm):
    stream_title = forms.CharField(max_length=180)
    scheduled_for = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    access_type = forms.ChoiceField(choices=LiveAnnouncement.AccessType.choices)
    ticket_price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        live = getattr(self.instance, "live_announcement", None)
        if live:
            self.fields["stream_title"].initial = live.stream_title
            self.fields["scheduled_for"].initial = live.scheduled_for
            self.fields["access_type"].initial = live.access_type
            self.fields["ticket_price"].initial = live.ticket_price

    def save(self, commit=True):
        post = super().save(commit=commit)
        if commit:
            LiveAnnouncement.objects.update_or_create(
                post=post,
                defaults={
                    "stream_title": self.cleaned_data["stream_title"],
                    "scheduled_for": self.cleaned_data["scheduled_for"],
                    "access_type": self.cleaned_data["access_type"],
                    "ticket_price": self.cleaned_data.get("ticket_price") or 0,
                },
            )
        return post


POST_TYPE_FORMS = {
    Post.PostType.TEXT: TextPostForm,
    Post.PostType.PHOTO: PhotoPostForm,
    Post.PostType.VIDEO: VideoPostForm,
    Post.PostType.FLYER: FlyerPostForm,
    Post.PostType.STORY: StoryPostForm,
    Post.PostType.REEL: ReelPostForm,
    Post.PostType.LIVE: LiveAnnouncementPostForm,
    Post.PostType.POLL: PollPostForm,
}


class PostForm(BasePostForm):
    """Compatibility form name for older imports."""
