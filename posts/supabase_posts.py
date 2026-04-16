from pathlib import Path
from uuid import uuid4
from datetime import datetime
import json

DATA_DIR = Path("data")
POSTS_FILE = DATA_DIR / "posts.json"
MEDIA_ROOT = Path("media")


def _ensure_posts_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not POSTS_FILE.exists():
        POSTS_FILE.write_text("[]", encoding="utf-8")


def _read_posts():
    _ensure_posts_file()
    try:
        return json.loads(POSTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_posts(posts):
    _ensure_posts_file()
    POSTS_FILE.write_text(json.dumps(posts, indent=2), encoding="utf-8")


def get_public_posts(limit=None):
    posts = _read_posts()
    posts = sorted(posts, key=lambda x: x.get("created_at", ""), reverse=True)
    if isinstance(limit, int):
        posts = posts[:limit]
    return posts


def get_posts_by_user(user_email):
    posts = _read_posts()
    return [p for p in posts if p.get("author_email") == user_email]


def get_post(post_id):
    posts = _read_posts()
    for post in posts:
        if post.get("id") == post_id:
            return post
    return None


def save_media_locally(file_obj, subdir="posts"):
    try:
        target_dir = MEDIA_ROOT / subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        original_name = getattr(file_obj, "name", "upload.bin")
        ext = ""
        if "." in original_name:
            ext = "." + original_name.split(".")[-1].lower()

        filename = f"{uuid4().hex}{ext}"
        target_path = target_dir / filename

        with open(target_path, "wb") as f:
            if hasattr(file_obj, "chunks"):
                for chunk in file_obj.chunks():
                    f.write(chunk)
            else:
                f.write(file_obj.read())

        return f"/media/{subdir}/{filename}"
    except Exception:
        return None


def create_post(author_email="", author_name="", content="", media_file=None):
    posts = _read_posts()

    media_url = None
    if media_file is not None:
        media_url = save_media_locally(media_file, "posts")

    new_post = {
        "id": uuid4().hex,
        "author_email": author_email or "guest@namvibe.local",
        "author_name": author_name or "Namvibe User",
        "content": (content or "").strip(),
        "media_url": media_url,
        "likes": 0,
        "comments": 0,
        "created_at": datetime.utcnow().isoformat(),
        "is_public": True,
    }

    posts.append(new_post)
    _write_posts(posts)
    return new_post


def update_post(post_id, content=None):
    posts = _read_posts()
    for post in posts:
        if post.get("id") == post_id:
            if content is not None:
                post["content"] = content.strip()
            _write_posts(posts)
            return post
    return None


def delete_post(post_id):
    posts = _read_posts()
    new_posts = [p for p in posts if p.get("id") != post_id]
    changed = len(new_posts) != len(posts)
    if changed:
        _write_posts(new_posts)
    return changed
