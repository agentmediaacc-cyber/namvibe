"""Weighted profile completion for NamVibe profiles."""


COMPLETION_WEIGHTS = {
    "avatar": 15,
    "cover": 10,
    "bio": 15,
    "location": 10,
    "phone_verified": 10,
    "email_verified": 10,
    "identity_verified": 15,
    "first_content": 15,
}


CHECKLIST = {
    "avatar": {"label": "Add profile photo", "action_url": "/profile/edit"},
    "cover": {"label": "Add cover banner", "action_url": "/profile/edit"},
    "bio": {"label": "Write bio", "action_url": "/profile/edit"},
    "location": {"label": "Add location", "action_url": "/profile/edit"},
    "phone_verified": {"label": "Verify phone", "action_url": "/security"},
    "email_verified": {"label": "Verify email", "action_url": "/security"},
    "identity_verified": {"label": "Verify identity", "action_url": "/profile/verification"},
    "first_content": {"label": "Upload first reel/post", "action_url": "/posts/create"},
}


def _present(value):
    return value not in (None, "", [], {})


def _has_avatar(profile):
    return _present(profile.get("avatar_url") or profile.get("photo_url") or profile.get("thumbnail_url") or profile.get("profile_photo"))


def _has_cover(profile):
    return _present(profile.get("cover_url") or profile.get("cover_path") or profile.get("banner_url") or profile.get("banner_path"))


def _has_location(profile):
    return _present(
        profile.get("location")
        or profile.get("current_location")
        or profile.get("town")
        or profile.get("city")
        or profile.get("region")
        or profile.get("country")
        or profile.get("country_origin")
        or profile.get("current_country")
    )


def _has_first_content(profile):
    for key in ("posts_count", "reels_count", "stories_count", "status_count"):
        try:
            if int(profile.get(key) or 0) > 0:
                return True
        except (TypeError, ValueError):
            pass
    return bool(profile.get("has_first_content") or profile.get("has_posts") or profile.get("has_reels") or profile.get("has_stories"))


def _completion_state(profile):
    profile = profile or {}
    return {
        "avatar": _has_avatar(profile),
        "cover": _has_cover(profile),
        "bio": _present(profile.get("bio")),
        "location": _has_location(profile),
        "phone_verified": bool(profile.get("phone_verified") or profile.get("phone_confirmed") or profile.get("phone_number_verified")),
        "email_verified": bool(profile.get("email_verified") or profile.get("email_confirmed") or profile.get("verified_email")),
        "identity_verified": bool(profile.get("identity_verified") or profile.get("is_verified") or profile.get("verified")),
        "first_content": _has_first_content(profile),
    }


def calculate_profile_completion(profile):
    """Return weighted completion, missing checklist, and next best action."""
    if not profile:
        return {"percent": 0, "score": 0, "total": 100, "missing": [], "checklist": [], "next_best_action": None}

    state = _completion_state(profile)
    score = sum(COMPLETION_WEIGHTS[key] for key, ok in state.items() if ok)
    missing = []
    checklist = []
    for key, weight in COMPLETION_WEIGHTS.items():
        task = {**CHECKLIST[key], "key": key, "weight": weight, "complete": bool(state[key])}
        checklist.append(task)
        if not state[key]:
            missing.append(task)

    return {
        "percent": max(0, min(100, int(score))),
        "score": score,
        "total": 100,
        "missing": missing,
        "checklist": checklist,
        "next_best_action": missing[0] if missing else None,
    }
