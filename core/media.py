import mimetypes
from fractions import Fraction

from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions
from django.conf import settings


IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
VIDEO_MIME_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
AUDIO_MIME_TYPES = {"audio/mpeg", "audio/mp4", "audio/wav", "audio/ogg"}

MAX_IMAGE_SIZE = getattr(settings, "COVER_UPLOAD_MAX_BYTES", 8 * 1024 * 1024)
MAX_VIDEO_SIZE = getattr(settings, "POST_VIDEO_MAX_BYTES", 80 * 1024 * 1024)
MAX_STORY_MEDIA_SIZE = getattr(settings, "STORY_MEDIA_MAX_BYTES", 20 * 1024 * 1024)
MAX_AUDIO_SIZE = getattr(settings, "AUDIO_UPLOAD_MAX_BYTES", 40 * 1024 * 1024)
DEFAULT_AVATAR = "images/default-avatar.svg"
DEFAULT_COVER = "images/default-cover.svg"
DEFAULT_MEDIA = "images/default-media.svg"
DEFAULT_LIVE_COVER = "images/default-live-cover.svg"


def _content_type(file_obj):
    explicit_type = getattr(file_obj, "content_type", None)
    if explicit_type:
        return explicit_type.lower()
    guessed_type, _ = mimetypes.guess_type(getattr(file_obj, "name", ""))
    return (guessed_type or "").lower()


def validate_file_size(file_obj, max_bytes, label="file"):
    if file_obj and file_obj.size > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise ValidationError(f"This {label} must be {max_mb}MB or smaller.")


def validate_mime_type(file_obj, allowed_types, label="file"):
    mime_type = _content_type(file_obj)
    if mime_type not in allowed_types:
        allowed = ", ".join(sorted(allowed_types))
        raise ValidationError(f"Unsupported {label} type. Allowed types: {allowed}.")


def validate_image_file(file_obj):
    validate_file_size(file_obj, MAX_IMAGE_SIZE, "image")
    validate_mime_type(file_obj, IMAGE_MIME_TYPES, "image")
    try:
        width, height = get_image_dimensions(file_obj)
    except Exception as exc:
        raise ValidationError("Upload a valid image file.") from exc
    if not width or not height:
        raise ValidationError("Upload a valid image file.")


def validate_video_file(file_obj):
    validate_file_size(file_obj, MAX_VIDEO_SIZE, "video")
    validate_mime_type(file_obj, VIDEO_MIME_TYPES, "video")


def validate_story_image_file(file_obj):
    validate_file_size(file_obj, MAX_STORY_MEDIA_SIZE, "story image")
    validate_mime_type(file_obj, IMAGE_MIME_TYPES, "story image")
    try:
        width, height = get_image_dimensions(file_obj)
    except Exception as exc:
        raise ValidationError("Upload a valid story image file.") from exc
    if not width or not height:
        raise ValidationError("Upload a valid story image file.")


def validate_story_video_file(file_obj):
    validate_file_size(file_obj, MAX_STORY_MEDIA_SIZE, "story video")
    validate_mime_type(file_obj, VIDEO_MIME_TYPES, "story video")


def validate_audio_file(file_obj):
    validate_file_size(file_obj, MAX_AUDIO_SIZE, "audio")
    validate_mime_type(file_obj, AUDIO_MIME_TYPES, "audio")


def validate_media_file(file_obj, media_type):
    validators = {
        "image": validate_image_file,
        "photo": validate_image_file,
        "video": validate_video_file,
        "reel": validate_video_file,
        "audio": validate_audio_file,
    }
    validator = validators.get(media_type)
    if validator:
        validator(file_obj)


def aspect_ratio(width, height):
    if not width or not height:
        return ""
    ratio = Fraction(width, height).limit_denominator(20)
    return f"{ratio.numerator}:{ratio.denominator}"


def classify_aspect_ratio(width, height):
    if not width or not height:
        return "unknown"
    ratio = width / height
    if 0.95 <= ratio <= 1.05:
        return "square"
    if ratio < 0.7:
        return "story"
    if ratio < 0.95:
        return "portrait"
    if ratio > 1.35:
        return "landscape"
    return "portrait"


def media_file_exists(file_field):
    if not file_field:
        return False
    name = getattr(file_field, "name", "")
    if not name:
        return False

    storage = getattr(file_field, "storage", None)
    if storage and hasattr(storage, "exists"):
        try:
            return bool(storage.exists(name))
        except Exception:
            return False

    return False


def _asset_url(path):
    return f"{settings.STATIC_URL.rstrip('/')}/{path.lstrip('/')}"


def safe_file_url(file_field, fallback=DEFAULT_MEDIA):
    if not file_field:
        return _asset_url(fallback)

    name = getattr(file_field, "name", "")
    if not name:
        return _asset_url(fallback)

    storage = getattr(file_field, "storage", None)
    if storage and hasattr(storage, "exists"):
        try:
            if storage.exists(name):
                return file_field.url
            return _asset_url(fallback)
        except Exception:
            pass

    try:
        return file_field.url
    except Exception:
        return _asset_url(fallback)


def profile_avatar_url(profile):
    return safe_file_url(getattr(profile, "avatar", None), DEFAULT_AVATAR)


def profile_cover_url(profile):
    return safe_file_url(getattr(profile, "cover_image", None), DEFAULT_COVER)


def post_media_url(media):
    return safe_file_url(getattr(media, "file", None), DEFAULT_MEDIA)


def live_cover_url(session):
    return safe_file_url(getattr(session, "thumbnail", None), DEFAULT_LIVE_COVER)
