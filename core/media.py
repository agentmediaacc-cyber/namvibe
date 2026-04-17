import mimetypes
from fractions import Fraction

from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions


IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
VIDEO_MIME_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
AUDIO_MIME_TYPES = {"audio/mpeg", "audio/mp4", "audio/wav", "audio/ogg"}

MAX_IMAGE_SIZE = 8 * 1024 * 1024
MAX_VIDEO_SIZE = 250 * 1024 * 1024
MAX_AUDIO_SIZE = 40 * 1024 * 1024


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
