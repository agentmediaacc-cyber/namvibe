import logging
from pathlib import Path
from uuid import UUID
from uuid import uuid4
import os

import requests
from django.conf import settings


logger = logging.getLogger(__name__)
SUPABASE_URL = getattr(settings, "SUPABASE_URL", os.getenv("SUPABASE_URL", "")).rstrip("/")
SUPABASE_SERVICE_KEY = getattr(
    settings,
    "SUPABASE_SERVICE_ROLE_KEY",
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_SERVICE_KEY", "")),
)


def _table_url():
    return f"{SUPABASE_URL}/rest/v1/posts"


def _headers(prefer_return=False):
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer_return:
        headers["Prefer"] = "return=representation"
    return headers


def _supabase_ready():
    return bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_missing_column(response):
    return response.status_code == 400 and "does not exist" in response.text


def _valid_uuid_or_none(value):
    if not value:
        return None
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        return None


def _normalize_post(post):
    if not isinstance(post, dict):
        return {}

    normalized = dict(post)
    normalized["user_id"] = normalized.get("user_id") or normalized.get("author_id") or ""
    normalized["full_name"] = normalized.get("full_name") or normalized.get("author_name") or "Namvibe User"
    normalized["author_name"] = normalized.get("full_name")
    normalized["author_email"] = normalized.get("email") or normalized.get("author_email") or ""
    normalized["media_url"] = normalized.get("media_url") or normalized.get("image_url")
    normalized["content"] = normalized.get("caption") or normalized.get("content") or normalized.get("title") or ""
    normalized["caption"] = normalized.get("caption") or normalized.get("content") or ""
    normalized["title"] = normalized.get("title") or "Untitled Post"
    normalized["username"] = normalized.get("username") or "user"
    normalized["audience"] = normalized.get("audience") or normalized.get("privacy") or "Public"
    normalized["share_to"] = normalized.get("share_to") or "Main Feed"
    normalized["status"] = normalized.get("status") or "published"
    normalized["post_type"] = normalized.get("post_type") or normalized.get("media_type") or "text"
    normalized["hashtags"] = normalized.get("hashtags") or ""
    normalized["tagged_users"] = normalized.get("tagged_users") or ""
    normalized["views_count"] = _safe_int(normalized.get("views_count"), 0)
    normalized["likes_count"] = _safe_int(normalized.get("likes_count"), 0)
    normalized["comments_count"] = _safe_int(normalized.get("comments_count"), 0)
    normalized["shares_count"] = _safe_int(normalized.get("shares_count"), 0)
    normalized["forwards_count"] = _safe_int(normalized.get("forwards_count"), 0)
    normalized["saves_count"] = _safe_int(normalized.get("saves_count"), 0)
    normalized["media_type"] = normalized.get("media_type") or ("photo" if normalized.get("media_url") else "text")
    return normalized


def _request_posts(params):
    if not _supabase_ready():
        return None

    try:
        response = requests.get(
            _table_url(),
            headers=_headers(),
            params=params,
            timeout=30,
        )
        if response.ok:
            return [_normalize_post(post) for post in response.json()]
        if not _is_missing_column(response):
            logger.warning("Supabase posts read failed: %s %s", response.status_code, response.text)
    except Exception as exc:
        logger.warning("Supabase posts read failed: %s", exc)
    return None


def count_public_posts():
    if not _supabase_ready():
        return 0

    try:
        response = requests.get(
            _table_url(),
            headers={**_headers(), "Prefer": "count=exact"},
            params={
                "select": "id",
                "audience": "eq.Public",
                "status": "eq.published",
                "limit": "1",
            },
            timeout=30,
        )
        if response.ok:
            content_range = response.headers.get("content-range", "")
            if "/" in content_range:
                return _safe_int(content_range.rsplit("/", 1)[-1], 0)
        if not _is_missing_column(response):
            logger.warning("Supabase posts count failed: %s %s", response.status_code, response.text)
    except Exception as exc:
        logger.warning("Supabase posts count failed: %s", exc)

    try:
        response = requests.get(
            _table_url(),
            headers={**_headers(), "Prefer": "count=exact"},
            params={"select": "id", "privacy": "eq.public", "limit": "1"},
            timeout=30,
        )
        if response.ok:
            content_range = response.headers.get("content-range", "")
            if "/" in content_range:
                return _safe_int(content_range.rsplit("/", 1)[-1], 0)
    except Exception as exc:
        print("SUPABASE POSTS LEGACY COUNT ERROR:", exc)

    return 0


def get_public_posts(limit=20):
    params = {
        "select": "*",
        "audience": "eq.Public",
        "status": "eq.published",
        "order": "created_at.desc",
    }
    if isinstance(limit, int):
        params["limit"] = str(limit)
    rows = _request_posts(params)
    if rows is not None:
        return rows

    legacy_params = {
        "select": "*",
        "privacy": "eq.public",
        "order": "created_at.desc",
    }
    if isinstance(limit, int):
        legacy_params["limit"] = str(limit)
    rows = _request_posts(legacy_params)
    if rows is not None:
        return rows

    fallback_params = {
        "select": "*",
        "order": "created_at.desc",
    }
    if isinstance(limit, int):
        fallback_params["limit"] = str(limit)
    return _request_posts(fallback_params) or []


def get_posts_by_user(user_id):
    if not user_id:
        return []

    user_uuid = _valid_uuid_or_none(user_id)
    if not user_uuid:
        logger.warning("Supabase user posts lookup skipped because user id is not a valid UUID: %s", user_id)
        return []

    rows = _request_posts({
        "select": "*",
        "user_id": f"eq.{user_uuid}",
        "order": "created_at.desc",
    })
    if rows is not None:
        return rows

    return _request_posts({
        "select": "*",
        "author_id": f"eq.{user_uuid}",
        "order": "created_at.desc",
    }) or []


def get_post(post_id):
    rows = _request_posts({
        "select": "*",
        "id": f"eq.{str(post_id)}",
        "limit": "1",
    }) or []
    return rows[0] if rows else None


def save_media_locally(file_obj, subdir="posts"):
    try:
        target_dir = Path(settings.MEDIA_ROOT) / subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        original_name = getattr(file_obj, "name", "upload.bin")
        ext = ""
        if "." in original_name:
            ext = "." + original_name.rsplit(".", 1)[-1].lower()

        filename = f"{uuid4().hex}{ext}"
        target_path = target_dir / filename

        with open(target_path, "wb") as file_handle:
            if hasattr(file_obj, "chunks"):
                for chunk in file_obj.chunks():
                    file_handle.write(chunk)
            else:
                file_handle.write(file_obj.read())

        return f"{settings.MEDIA_URL}{subdir}/{filename}"
    except Exception as exc:
        logger.warning("Post media save failed: %s", exc)
        return None


def _checkbox_value(value, default=False):
    if value is None:
        return default
    return value in [True, "true", "True", "on", "1", "yes"]


def _media_type_from_file(file_obj):
    content_type = getattr(file_obj, "content_type", "") or ""
    if content_type.startswith("image/"):
        return "photo"
    if content_type.startswith("video/"):
        return "video"
    return "text"


def create_post(
    user_id,
    full_name="",
    username="",
    email="",
    post_type="text",
    title="",
    caption="",
    hashtags="",
    tagged_users="",
    audience="Public",
    share_to="Main Feed",
    group_name="",
    single_user="",
    specific_user="",
    community_name="",
    background_theme="theme-purple",
    font_theme="font-modern",
    crop_style="cover",
    image_effect="none",
    video_mode="normal",
    display_mode="cover",
    overlay_text="",
    flyer_background="gradient-violet",
    flyer_text_color="#ffffff",
    flyer_layout="centered",
    flyer_title="",
    flyer_body="",
    flyer_cta="",
    music_track="",
    motion_effect="none",
    poll_question="",
    poll_options="",
    media_type="text",
    allow_comments=True,
    allow_share=True,
    save_story=False,
    premium_badge=False,
    save_draft=False,
    media_file=None,
):
    if not _supabase_ready() or not user_id:
        return None

    user_uuid = _valid_uuid_or_none(user_id)
    if not user_uuid:
        logger.warning("Supabase post sync skipped because user id is not a valid UUID: %s", user_id)
        return None

    media_url = None
    if media_file is not None:
        media_url = save_media_locally(media_file, "posts")
        if media_type == "text":
            media_type = _media_type_from_file(media_file)

    caption = (caption or "").strip()
    title = (title or "").strip()

    payload = {
        "user_id": user_uuid,
        "full_name": full_name or "Namvibe User",
        "username": username or "user",
        "email": email or "",
        "post_type": post_type or media_type or "text",
        "title": title,
        "caption": caption,
        "hashtags": hashtags or "",
        "tagged_users": tagged_users or "",
        "audience": audience or "Public",
        "share_to": share_to or "Main Feed",
        "group_name": group_name or "",
        "single_user": single_user or specific_user or "",
        "specific_user": specific_user or single_user or "",
        "community_name": community_name or group_name or "",
        "background_theme": background_theme or "theme-purple",
        "font_theme": font_theme or "font-modern",
        "crop_style": crop_style or "cover",
        "image_effect": image_effect or "none",
        "video_mode": video_mode or "normal",
        "display_mode": display_mode or "cover",
        "overlay_text": overlay_text or "",
        "flyer_background": flyer_background or "gradient-violet",
        "flyer_text_color": flyer_text_color or "#ffffff",
        "flyer_layout": flyer_layout or "centered",
        "flyer_title": flyer_title or "",
        "flyer_body": flyer_body or "",
        "flyer_cta": flyer_cta or "",
        "music_track": music_track or "",
        "motion_effect": motion_effect or "none",
        "motion_status": "queued" if music_track or motion_effect not in ["", "none"] else "",
        "poll_question": poll_question or "",
        "poll_options": poll_options or "",
        "media_type": media_type or "text",
        "media_url": media_url,
        "allow_comments": _checkbox_value(allow_comments, True),
        "allow_share": _checkbox_value(allow_share, True),
        "save_story": _checkbox_value(save_story, False),
        "premium_badge": _checkbox_value(premium_badge, False),
        "views_count": 0,
        "likes_count": 0,
        "comments_count": 0,
        "shares_count": 0,
        "forwards_count": 0,
        "saves_count": 0,
        "status": "draft" if _checkbox_value(save_draft, False) else "published",
    }

    try:
        response = requests.post(
            _table_url(),
            headers=_headers(prefer_return=True),
            json=payload,
            timeout=30,
        )
        if response.ok:
            rows = response.json()
            return _normalize_post(rows[0]) if rows else None

        if response.status_code == 400:
            legacy_payload = {
                "author_id": user_uuid,
                "content": caption or title,
                "image_url": media_url,
                "privacy": (audience or "Public").lower(),
            }
            legacy_response = requests.post(
                _table_url(),
                headers=_headers(prefer_return=True),
                json=legacy_payload,
                timeout=30,
            )
            if legacy_response.ok:
                rows = legacy_response.json()
                return _normalize_post(rows[0]) if rows else None
            logger.warning(
                "Supabase legacy post create failed: %s %s",
                legacy_response.status_code,
                legacy_response.text,
            )
        else:
            logger.warning("Supabase post create failed: %s %s", response.status_code, response.text)
    except Exception as exc:
        logger.warning("Supabase post create failed: %s", exc)
    return None
