"""Profile Completion Service — calculates percentage and missing tasks."""

def calculate_profile_completion(profile):
    """
    Calculates the percentage of profile completion and lists missing tasks.
    
    Returns:
    {
      "percent": 0-100,
      "missing": [{"key": "...", "label": "...", "action_url": "..."}, ...],
      "next_best_action": {...}
    }
    """
    if profile is None:
        return {"percent": 0, "missing": [], "next_best_action": None}

    tasks = [
        {"key": "avatar_url", "label": "Add profile photo", "action_url": "/profile/edit"},
        {"key": "cover_url", "label": "Add cover banner", "action_url": "/profile/edit"},
        {"key": "bio", "label": "Write bio", "action_url": "/profile/edit"},
        {"key": "location", "label": "Add location", "action_url": "/profile/edit"},
        {"key": "website", "label": "Add website", "action_url": "/profile/edit"},
        {"key": "skills", "label": "Add skills", "action_url": "/profile/edit"},
        {"key": "phone_verified", "label": "Verify phone", "action_url": "/security"},
        {"key": "email_verified", "label": "Verify email", "action_url": "/security"},
        {"key": "privacy", "label": "Review privacy settings", "action_url": "/security/privacy"}
    ]
    
    # Custom checks for some fields
    def is_filled(key):
        if key == "phone_verified":
            return bool(profile.get("phone_verified") or profile.get("phone_confirmed"))
        if key == "email_verified":
            return bool(profile.get("email_verified") or profile.get("email_confirmed"))
        if key == "privacy":
            # Assume privacy is reviewed if the profile is not brand new or has specific flags
            return bool(profile.get("privacy_reviewed") or profile.get("profile_completed"))
        if key == "location":
            return bool(profile.get("location") or profile.get("current_location") or profile.get("town"))
        
        val = profile.get(key)
        return val not in (None, "", [], {})

    missing = []
    filled_count = 0
    for task in tasks:
        if is_filled(task["key"]):
            filled_count += 1
        else:
            missing.append(task)
            
    percent = int((filled_count / len(tasks)) * 100) if tasks else 0
    
    next_best_action = missing[0] if missing else None
    
    return {
        "percent": percent,
        "missing": missing,
        "next_best_action": next_best_action
    }
