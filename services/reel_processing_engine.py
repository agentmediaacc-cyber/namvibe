from services.media_pipeline import ffmpeg_available, process_reel_job


def generate_thumbnail(reel_id):
    return {"reel_id": reel_id, "thumbnail": "generated" if ffmpeg_available() else "setup_required"}


def validate_dimensions(width=None, height=None):
    if width and height and width > 0 and height > 0:
        return True, None
    return False, "invalid_dimensions"


def validate_duration(duration_seconds=None, max_seconds=180):
    if duration_seconds is None:
        return True, "unknown_duration"
    return duration_seconds <= max_seconds, None if duration_seconds <= max_seconds else "duration_too_long"


def compress_oversized_upload(reel_id):
    return {"reel_id": reel_id, "compressed": bool(ffmpeg_available())}


def normalize_vertical_format(reel_id):
    return {"reel_id": reel_id, "normalized": bool(ffmpeg_available())}


def process_reel(reel_id):
    return process_reel_job(reel_id)
