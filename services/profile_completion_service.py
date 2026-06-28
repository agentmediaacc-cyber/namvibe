"""Profile completion service using registration data."""
from services.neon_service import fast_query, write_query
from services.logging_service import log_info

COMPLETION_FIELDS = {
    "full_name": 10,
    "username": 5,
    "avatar_url": 15,
    "cover_url": 5,
    "bio": 10,
    "phone": 5,
    "email": 5,
    "date_of_birth": 5,
    "gender": 3,
    "town": 5,
    "country": 5,
    "location": 5,
    "website": 5,
    "interests": 7,
    "profile_photo": 10,
}

def calculate_completion(profile):
    if not profile:
        return {"percentage": 0, "completed": [], "missing": []}
    completed = []
    missing = []
    score = 0
    total = sum(COMPLETION_FIELDS.values())
    for field, weight in COMPLETION_FIELDS.items():
        value = profile.get(field)
        if value and str(value).strip():
            score += weight
            completed.append(field)
        else:
            missing.append(field)
    pct = min(100, int((score / total) * 100))
    return {"percentage": pct, "completed": completed, "missing": missing, "score": score, "total": total}

def get_completion(profile_id):
    rows = fast_query(
        "SELECT full_name, username, avatar_url, cover_url, bio, phone, email, "
        "date_of_birth, gender, town, country, location, website, interests, profile_photo "
        "FROM chain_profiles WHERE id = %s",
        (profile_id,), default=[]
    )
    if not rows:
        return {"percentage": 0, "completed": [], "missing": []}
    return calculate_completion(rows[0])

def update_completion_percentage(profile_id):
    result = get_completion(profile_id)
    write_query(
        "UPDATE chain_profiles SET completion_percentage = %s, profile_completed = %s WHERE id = %s",
        (result["percentage"], result["percentage"] >= 80, profile_id)
    )
    return result

# Alias for backward compatibility with existing imports
calculate_profile_completion = calculate_completion
