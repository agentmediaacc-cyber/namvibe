"""Shared avatar normalization helpers for production surfaces."""

from __future__ import annotations

from services.media_selection_service import select_avatar_url


def avatar_initials(profile: dict | None) -> str:
    profile = profile or {}
    name = profile.get("display_name") or profile.get("full_name") or profile.get("username") or "NamVibe"
    bits = [part for part in str(name).replace("@", " ").split() if part]
    if not bits:
        return "NV"
    return "".join(part[0].upper() for part in bits[:2])


def avatar_meta(profile: dict | None) -> dict:
    profile = profile or {}
    raw_avatar = any(
        profile.get(key)
        for key in (
            "avatar_url",
            "profile_photo",
            "photo_url",
            "profile_picture",
            "creator_avatar",
            "profile_image",
            "thumbnail_url",
        )
    )
    avatar_url = select_avatar_url(profile)
    has_image = bool(raw_avatar)
    alt = str(profile.get("display_name") or profile.get("full_name") or profile.get("username") or "").strip()
    return {
        "avatar_url": avatar_url,
        "avatar_alt": f"{alt} profile picture" if alt else "Profile picture",
        "avatar_initials": avatar_initials(profile),
        "avatar_has_image": has_image,
    }
