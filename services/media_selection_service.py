"""Shared media URL selection helpers.

This module chooses between stored renditions without inventing new ones.
"""

from __future__ import annotations

from services.media_pipeline import normalize_public_media_url


def _pick_first(*values):
    for value in values:
        normalized = normalize_public_media_url(value or "")
        if normalized:
            return normalized
    return ""


def select_avatar_url(row):
    row = row or {}
    return _pick_first(
        row.get("avatar_url"),
        row.get("profile_photo"),
        row.get("photo_url"),
        row.get("profile_picture"),
        row.get("creator_avatar"),
        row.get("profile_image"),
        row.get("thumbnail_url"),
    )


def select_video_url(row):
    row = row or {}
    return _pick_first(
        row.get("video_1080p_url"),
        row.get("video_720p_url"),
        row.get("video_source_url"),
        row.get("video_url"),
        row.get("media_url"),
    )


def select_poster_url(row):
    row = row or {}
    return _pick_first(
        row.get("poster_url"),
        row.get("thumbnail_url"),
        row.get("poster_720p_url"),
        row.get("media_thumbnail_url"),
    )


def select_photo_url(row):
    row = row or {}
    return _pick_first(
        row.get("photo_1080p_url"),
        row.get("photo_720p_url"),
        row.get("full_media_url"),
        row.get("media_url"),
        row.get("public_url"),
    )
