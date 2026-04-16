import os
from pathlib import Path

MEDIA_ROOT = Path("media")


def get_public_posts(*args, **kwargs):
    return []


def get_posts_by_user(*args, **kwargs):
    return []


def get_post(*args, **kwargs):
    return None


def create_post(*args, **kwargs):
    return None


def update_post(*args, **kwargs):
    return None


def delete_post(*args, **kwargs):
    return False


def save_media_locally(file_obj, subdir="posts"):
    try:
        target_dir = MEDIA_ROOT / subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        name = getattr(file_obj, "name", "upload.bin")
        target_path = target_dir / name

        with open(target_path, "wb") as f:
            if hasattr(file_obj, "chunks"):
                for chunk in file_obj.chunks():
                    f.write(chunk)
            else:
                f.write(file_obj.read())

        return str(target_path)
    except Exception:
        return None
