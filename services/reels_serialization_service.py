"""Canonical reel serialization and feed cursor helpers."""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timezone
import json
from typing import Any, Dict, Iterable, List, Mapping, Optional

from services.neon_service import fast_query


MAX_FEED_LIMIT = 20
DEFAULT_FEED_LIMIT = 10


def _int(value: Any) -> int:
    try:
        return max(int(value or 0), 0)
    except Exception:
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}
    return bool(value)


def _str(value: Any) -> str:
    return str(value) if value is not None else ""


def _iso(value: Any) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return None
    return _str(value)


def encode_feed_cursor(created_at: Any, reel_id: Any) -> Optional[str]:
    if not created_at or not reel_id:
        return None
    payload = {"v": 1, "created_at": _iso(created_at), "id": _str(reel_id)}
    return urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii").rstrip("=")


def decode_feed_cursor(cursor: Optional[str]) -> Optional[Dict[str, str]]:
    if not cursor:
        return None
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = urlsafe_b64decode((cursor + padding).encode("ascii")).decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        if data.get("v") != 1:
            return None
        created_at = data.get("created_at")
        reel_id = data.get("id")
        if not created_at or not reel_id:
            return None
        return {"created_at": str(created_at), "id": str(reel_id)}
    except Exception:
        return None


def _profile_index(profile_rows: Iterable[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    index = {}
    for row in profile_rows or []:
        pid = row.get("id")
        if pid:
            index[str(pid)] = row
    return index


def load_creator_profiles(profile_ids: Iterable[Any]) -> Dict[str, Mapping[str, Any]]:
    ids = list(dict.fromkeys(str(pid) for pid in (profile_ids or []) if pid))
    if not ids:
        return {}
    rows = fast_query(
        """
        SELECT id, username, display_name, full_name, avatar_url, profile_photo,
               is_verified, verification_level, profile_visibility
        FROM chain_profiles
        WHERE id = ANY(%s::uuid[])
        """,
        (ids,),
        timeout_ms=2000,
        default=[],
    ) or []
    return _profile_index(rows)


def serialize_reel(row: Optional[Mapping[str, Any]], *, viewer_id: Any = None, creator: Optional[Mapping[str, Any]] = None, following: bool = False) -> Dict[str, Any]:
    row = row or {}
    creator = creator or {}
    created_at = row.get("created_at")
    profile_id = row.get("profile_id") or row.get("creator_id")
    username = creator.get("username") or row.get("username") or ""
    display_name = creator.get("display_name") or creator.get("full_name") or row.get("display_name") or username
    avatar_url = creator.get("avatar_url") or creator.get("profile_photo") or row.get("avatar_url") or ""
    video_url = row.get("video_url") or row.get("media_url") or ""
    thumbnail_url = row.get("thumbnail_url") or row.get("poster_url") or ""
    duration = row.get("duration_seconds")
    width = row.get("width")
    height = row.get("height")
    aspect_ratio = None
    try:
        if width and height:
            aspect_ratio = round(float(width) / float(height), 6)
    except Exception:
        aspect_ratio = None
    reel_id = row.get("id")
    can_edit = bool(viewer_id and profile_id and str(viewer_id) == str(profile_id))
    can_delete = can_edit
    can_report = bool(viewer_id and profile_id and str(viewer_id) != str(profile_id))
    if not viewer_id:
        can_report = True
    creator_url = f"/profile/@{username}" if username else (f"/profile/{profile_id}" if profile_id else "/profile/")
    return {
        "id": _str(reel_id),
        "creator_id": _str(profile_id),
        "profile_id": _str(profile_id),
        "creator_username": username,
        "creator_display_name": display_name,
        "creator_avatar_url": avatar_url,
        "creator_is_verified": _bool(creator.get("is_verified") or row.get("is_verified")),
        "username": username,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "is_verified": _bool(creator.get("is_verified") or row.get("is_verified")),
        "caption": row.get("caption") or "",
        "video_url": video_url,
        "thumbnail_url": thumbnail_url,
        "duration_seconds": float(duration) if duration is not None else None,
        "aspect_ratio": aspect_ratio,
        "visibility": row.get("visibility") or "public",
        "created_at": _iso(created_at),
        "likes_count": _int(row.get("likes_count")),
        "comments_count": _int(row.get("comments_count")),
        "shares_count": _int(row.get("shares_count")),
        "saves_count": _int(row.get("saves_count")),
        "views_count": _int(row.get("views_count")),
        "is_liked": _bool(row.get("is_liked") or row.get("viewer_has_liked")),
        "is_saved": _bool(row.get("is_saved") or row.get("viewer_has_saved")),
        "is_following_creator": _bool(following or row.get("is_following_creator")),
        "can_edit": can_edit,
        "can_delete": can_delete,
        "can_report": can_report,
        "music": {
            "title": row.get("music_title") or None,
            "artist": row.get("music_artist") or None,
            "url": row.get("music_url") or None,
            "start_seconds": row.get("music_start_seconds"),
            "duration_seconds": row.get("music_duration_seconds"),
        } if any(row.get(k) for k in ("music_title", "music_artist", "music_url")) else None,
        "location": row.get("location") or None,
        "hashtags": row.get("hashtags") or [],
        "open_url": f"/reels/{reel_id}" if reel_id else "/reels/",
        "creator_url": creator_url,
    }


def serialize_reels(rows: Iterable[Mapping[str, Any]], *, viewer_id: Any = None, following_ids: Optional[Iterable[Any]] = None) -> List[Dict[str, Any]]:
    rows = list(rows or [])
    needs_profiles = any(
        not (row.get("username") or row.get("display_name") or row.get("avatar_url") or row.get("is_verified") is not None)
        for row in rows
    )
    profiles = load_creator_profiles([row.get("profile_id") for row in rows]) if needs_profiles else {}
    following_set = {str(pid) for pid in (following_ids or [])}
    return [
        serialize_reel(row, viewer_id=viewer_id, creator=profiles.get(str(row.get("profile_id"))), following=str(row.get("profile_id")) in following_set)
        for row in rows
    ]
