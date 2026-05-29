import random
import re
from datetime import datetime, timezone
import uuid

from flask import session

from engines.cache_engine import cache_key, delete_cache, get_cache, set_cache
from engines.performance_engine import normalize_username, profile_completion_score, safe_int
from services.neon_service import write_query, fast_query, get_table_columns, table_exists as neon_table_exists
from services.supabase_safe import column_safe_payload, safe_count, safe_insert, safe_select, safe_update, table_exists


PROFILE_COLUMNS = {
    "id",
    "auth_user_id",
    "username",
    "email",
    "normalized_email",
    "full_name",
    "bio",
    "gender",
    "age",
    "country_origin",
    "current_location",
    "phone",
    "normalized_phone",
    "residential_address",
    "town",
    "region",
    "country_of_birth",
    "date_of_birth",
    "current_residential_location",
    "avatar_url",
    "avatar_upload_id",
    "profile_photo",
    "cover_url",
    "cover_upload_id",
    "profile_photo",
    "profile_video_url",
    "video_intro_url",
    "relationship_status",
    "relationship_goal",
    "creator_category",
    "profile_type",
    "interests",
    "languages",
    "is_public",
    "is_verified",
    "is_premium",
    "premium_tier",
    "followers_count",
    "following_count",
    "profile_views",
    "total_likes",
    "wallet_balance",
    "profile_completion",
    "profile_completed",
    "onboarding_step",
    "password_set",
    "auth_provider",
    "provider_user_id",
    "zodiac_sign",
    "show_zodiac",
    "allow_zodiac_display",
    "allow_birthday_notifications",
    "profile_visibility",
    "terms_accepted",
    "human_confirmed",
    "anonymous_profile",
    "creator_mode_enabled",
    "seller_mode_enabled",
    "dating_mode_enabled",
    "premium_mode_enabled",
    "account_mode",
    "last_login_at",
    "login_count",
    "linked_providers",
    "username_slug",
    "oauth_metadata",
    "is_creator",
    "created_at",
    "updated_at",
}

NEON_PROFILE_COLUMNS = {
    "id",
    "auth_user_id",
    "email",
    "username",
    "display_name",
    "full_name",
    "bio",
    "phone",
    "date_of_birth",
    "residential_address",
    "preferred_language",
    "town",
    "region",
    "country",
    "current_location",
    "country_origin",
    "avatar_url",
    "cover_url",
    "storage_bucket",
    "storage_path",
    "interests",
    "activities",
    "looking_for",
    "gender",
    "relationship_status",
    "creator_category",
    "profile_type",
    "is_verified",
    "is_premium",
    "followers_count",
    "following_count",
    "posts_count",
    "reels_count",
    "live_rooms_count",
    "profile_views",
    "wallet_balance",
    "verified",
    "visibility",
    "allow_messages",
    "allow_dating",
    "allow_gifts",
    "terms_accepted_at",
    "privacy_accepted_at",
    "onboarding_step",
    "profile_completed",
    "tour_seen",
    "last_login_at",
    "login_count",
    "dating_mode_enabled",
    "is_creator",
    "created_at",
    "updated_at",
    "deleted_at",
}


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _normalize_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _clean_email(value):
    cleaned = str(value or "").strip().lower()
    return cleaned or None


def _normalize_phone(value):
    cleaned = "".join(ch for ch in str(value or "") if ch.isdigit() or ch == "+")
    if cleaned.startswith("00"):
        cleaned = f"+{cleaned[2:]}"
    if cleaned and not cleaned.startswith("+"):
        cleaned = f"+{cleaned}"
    return cleaned or None


def _username_valid(username):
    return bool(re.fullmatch(r"[a-z0-9_]{3,30}", username or ""))


def _username_suggestions(username, town=None):
    base = normalize_username(username or "chain")
    place = normalize_username(town or "world")
    year_suffix = str(datetime.now(timezone.utc).year)[-2:]
    candidates = [f"{base}{random.randint(10, 99)}", f"{base}{place}", f"{base}{year_suffix}"]
    suggestions = []
    seen = set()
    for candidate in candidates:
        trimmed = candidate[:30]
        if trimmed and trimmed not in seen:
            seen.add(trimmed)
            suggestions.append(trimmed)
    return suggestions[:3]


def _bool_value(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "1", "on", "yes"}


def _age_from_dob(date_of_birth):
    if not date_of_birth:
        return None
    try:
        dob = datetime.fromisoformat(str(date_of_birth)).date()
        today = datetime.now(timezone.utc).date()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except ValueError:
        return None


def profile_age(profile):
    if not profile:
        return None
    age = profile.get("age")
    if age not in (None, ""):
        try:
            return int(age)
        except (TypeError, ValueError):
            pass
    return _age_from_dob(profile.get("date_of_birth"))


def is_adult_profile(profile):
    """
    Returns:
    - True if age >= 18
    - False if age < 18
    - None if age is unknown (missing DOB)
    """
    age = profile_age(profile)
    if age is None:
        return None
    return age >= 18


def verify_profile_age(profile):
    """
    Standard age gate check for routes.
    Returns (ok, redirect_target or error_message)
    """
    is_adult = is_adult_profile(profile)
    if is_adult is True:
        return True, None
    if is_adult is False:
        return False, "CHAIN is only available to users 18 and older."
    # is_adult is None -> missing DOB
    return False, "REDIRECT_AGE_CHECK"


def _upsert_single(table, key_field, key_value, payload, fallback_columns=None):
    existing = safe_select(table, columns="id", filters={key_field: key_value}, limit=1, order_by=None)
    if existing:
        safe_update(table, payload, eq={"id": existing[0]["id"]}, fallback_columns=fallback_columns)
        return existing[0]["id"]
    inserted = safe_insert(table, {key_field: key_value, **payload}, fallback_columns=fallback_columns)
    if inserted:
        return inserted[0].get("id")
    return None


def normalize_profile(profile):
    if not profile:
        return None

    normalized = dict(profile)
    normalized["avatar_url"] = normalized.get("avatar_url") or normalized.get("profile_photo")
    normalized["cover_url"] = normalized.get("cover_url") or normalized.get("cover_photo")
    normalized["profile_video_url"] = normalized.get("profile_video_url") or normalized.get("video_intro_url")
    normalized["profile_type"] = normalized.get("profile_type") or ("creator" if normalized.get("is_creator") else "member")
    normalized["creator_category"] = normalized.get("creator_category") or normalized.get("profile_type")
    normalized["premium_tier"] = normalized.get("premium_tier") or ("premium" if normalized.get("is_premium") else "free")
    normalized["is_premium"] = bool(normalized.get("is_premium") or normalized.get("premium_tier") not in {None, "", "free"})
    normalized["wallet_balance"] = normalized.get("wallet_balance") or 0
    normalized["interests"] = _normalize_list(normalized.get("interests"))
    normalized["activities"] = _normalize_list(normalized.get("activities"))
    normalized["looking_for"] = _normalize_list(normalized.get("looking_for"))
    normalized["languages"] = _normalize_list(normalized.get("languages"))
    normalized["linked_providers"] = _normalize_list(normalized.get("linked_providers"))
    normalized["profile_completion"] = normalized.get("profile_completion") or calculate_completion(normalized)
    normalized["profile_completed"] = normalized.get("profile_completed")
    if normalized["profile_completed"] is None:
        normalized["profile_completed"] = normalized["profile_completion"] >= 55
    normalized["creator_mode_enabled"] = _bool_value(normalized.get("creator_mode_enabled") or normalized.get("profile_type") in {"creator", "host"})
    normalized["seller_mode_enabled"] = _bool_value(normalized.get("seller_mode_enabled") or normalized.get("profile_type") == "seller")
    normalized["dating_mode_enabled"] = _bool_value(normalized.get("dating_mode_enabled"))
    normalized["premium_mode_enabled"] = _bool_value(normalized.get("premium_mode_enabled") or normalized.get("is_premium"))
    normalized["show_zodiac"] = _bool_value(normalized.get("show_zodiac"))
    normalized["visibility"] = normalized.get("visibility") or normalized.get("profile_visibility") or "public"
    normalized["allow_messages"] = _bool_value(normalized.get("allow_messages"), True)
    normalized["allow_dating"] = _bool_value(normalized.get("allow_dating"))
    normalized["allow_gifts"] = _bool_value(normalized.get("allow_gifts"), True)
    normalized["preferred_language"] = normalized.get("preferred_language") or normalized.get("current_language")
    normalized["age"] = profile_age(normalized)
    return normalized


def _neon_profiles_enabled():
    return neon_table_exists("chain_profiles")


def _neon_profile_columns():
    columns = [column for column in get_table_columns("chain_profiles", timeout_ms=500) if column in NEON_PROFILE_COLUMNS]
    if not columns:
        columns = ["id", "auth_user_id", "email", "username", "display_name", "full_name", "profile_completed", "created_at", "updated_at"]
    return ", ".join(columns)


def _neon_get_profile_by(field, value):
    if not _neon_profiles_enabled() or value in (None, ""):
        return None
    if field in {"id", "auth_user_id"}:
        try:
            uuid.UUID(str(value))
        except (ValueError, TypeError):
            return None
    try:
        # Use fast_query for public/readonly lookups
        rows = fast_query(
            f"SELECT {_neon_profile_columns()} FROM chain_profiles WHERE {field} = %s AND deleted_at IS NULL LIMIT 1",
            [value],
            timeout_ms=500,
        )
        row = rows[0] if rows else None
        return normalize_profile(row) if row else None
    except Exception as error:
        print(f"[profile_service] neon lookup failed for {field}: {error}")
        return None


def _neon_insert_profile(payload):
    if not payload:
        return None
    columns = list(payload.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    
    # Use ON CONFLICT to ensure one user = one profile
    sql = f"""
        INSERT INTO chain_profiles ({', '.join(columns)}) 
        VALUES ({placeholders}) 
        ON CONFLICT (auth_user_id) DO UPDATE 
        SET updated_at = now() 
        RETURNING id, auth_user_id, email, username, display_name, full_name, profile_completed
    """
    try:
        results = write_query(sql, list(payload.values()), timeout_ms=3000)
        return results[0] if results else None
    except Exception as error:
        print(f"[profile_service] _neon_insert_profile failed: {error}")
        raise


def _neon_update_profile(profile_id, payload):
    if not payload:
        return None
    assignments = ", ".join(f"{key} = %s" for key in payload.keys())
    params = list(payload.values()) + [profile_id]
    try:
        write_query(
            f"UPDATE chain_profiles SET {assignments}, updated_at = now() WHERE id = %s",
            params,
            timeout_ms=3000,
        )
        return _neon_get_profile_by("id", profile_id)
    except Exception as error:
        print(f"[profile_service] _neon_update_profile failed: {error}")
        return None


def ensure_neon_profile(auth_user_id, defaults=None):
    defaults = defaults or {}
    profile = _neon_get_profile_by("auth_user_id", auth_user_id)
    if profile:
        return True, profile
    if not _neon_profiles_enabled():
        return False, "Neon chain_profiles table is unavailable."
    username = normalize_username(defaults.get("username") or session.get("username") or "chainuser")
    if not _username_valid(username):
        username = "chainuser"
    while _neon_get_profile_by("username", username):
        username = _username_suggestions(username, defaults.get("town"))[0]
    payload = {
        "auth_user_id": auth_user_id,
        "email": _clean_email(defaults.get("email") or session.get("email")),
        "username": username,
        "display_name": (defaults.get("display_name") or defaults.get("full_name") or username).strip(),
        "full_name": (defaults.get("full_name") or defaults.get("display_name") or username).strip(),
        "phone": defaults.get("phone") or session.get("phone"),
        "date_of_birth": defaults.get("date_of_birth"),
        "residential_address": defaults.get("residential_address"),
        "preferred_language": defaults.get("preferred_language"),
        "interests": defaults.get("interests") or [],
        "activities": defaults.get("activities") or [],
        "looking_for": defaults.get("looking_for") or [],
        "bio": defaults.get("bio") or "",
        "town": defaults.get("town"),
        "region": defaults.get("region"),
        "profile_completed": bool(defaults.get("profile_completed", False)),
        "dating_mode_enabled": bool(defaults.get("dating_mode_enabled", False)),
        "is_creator": bool(defaults.get("profile_type") in {"creator", "host"}),
        "creator_category": defaults.get("profile_type"),
        "onboarding_step": defaults.get("onboarding_step") or "account",
        "tour_seen": bool(defaults.get("tour_seen", False)),
    }
    try:
        _neon_insert_profile(payload)
        return True, _neon_get_profile_by("auth_user_id", auth_user_id)
    except Exception as error:
        print(f"[profile_service] ensure_neon_profile failed: {error}")
        return False, "Profile could not be saved yet."


def get_current_profile():
    try:
        auth_user_id = session.get("auth_user_id")
        if not auth_user_id:
            return None

        cached_profile = get_cache(cache_key("current_profile", auth_user_id))
        if cached_profile is not None:
            return cached_profile

        profile = _neon_get_profile_by("auth_user_id", auth_user_id)
        if not profile and session.get("profile_id"):
            profile = _neon_get_profile_by("id", session.get("profile_id"))
        if not profile:
            profiles = safe_select("chain_profiles", columns="*", filters={"auth_user_id": auth_user_id}, limit=1)
            if not profiles and session.get("profile_id"):
                profiles = safe_select("chain_profiles", columns="*", filters={"id": session.get("profile_id")}, limit=1)
            profile = normalize_profile(profiles[0]) if profiles else None

        if profile:
            session["profile_id"] = profile["id"]
            session["username"] = profile["username"]
            set_cache(cache_key("current_profile", auth_user_id), profile, ttl=60)
            return profile

        return None
    except Exception as error:
        print(f"[profile_service] get_current_profile failed: {error}")
        return None


def get_public_profiles(limit=20):
    key = cache_key("public_profiles", limit)
    cached_profiles = get_cache(key)
    if cached_profiles is not None:
        return cached_profiles
    profiles = safe_select(
        "chain_profiles",
        columns="id,username,full_name,bio,current_location,avatar_url,premium_tier,is_premium,is_verified,age,country_origin,interests,cover_url",
        filters={"is_public": True},
        limit=limit,
    )
    result = [normalize_profile(profile) for profile in profiles]
    set_cache(key, result, ttl=60)
    return result


def get_profile_by_username(username):
    try:
        cleaned = username[1:] if username.startswith("@") else username
        key = cache_key("profile_username", cleaned)
        cached_profile = get_cache(key)
        if cached_profile is not None:
            return cached_profile
        profile = _neon_get_profile_by("username", cleaned)
        if not profile:
            profiles = safe_select("chain_profiles", columns="*", filters={"username": cleaned}, limit=1)
            profile = normalize_profile(profiles[0]) if profiles else None
        set_cache(key, profile, ttl=120)
        return profile
    except Exception as error:
        print(f"[profile_service] get_profile_by_username failed: {error}")
        return None


def get_profile_by_id(profile_id):
    key = cache_key("profile_id", profile_id)
    cached_profile = get_cache(key)
    if cached_profile is not None:
        return cached_profile
    profile = _neon_get_profile_by("id", profile_id)
    if not profile:
        profiles = safe_select("chain_profiles", columns="*", filters={"id": profile_id}, limit=1, order_by=None)
        profile = normalize_profile(profiles[0]) if profiles else None
    set_cache(key, profile, ttl=120)
    return profile


def calculate_completion(profile):
    return profile_completion_score(profile)


def required_profile_fields():
    return [
        "full_name",
        "username",
        "phone",
        "date_of_birth",
        "gender",
        "country_of_birth",
        "region",
        "town",
        "current_residential_location",
        "residential_address",
    ]


def get_profile_completion(profile):
    if not profile:
        return 0
    required = required_profile_fields()
    filled = 0
    for field in required:
        value = profile.get(field)
        if value not in (None, "", []):
            filled += 1
    return int((filled / len(required)) * 100)


def is_profile_complete(profile):
    if not profile:
        return False
    return all((profile.get(field) not in (None, "", [])) for field in required_profile_fields())


def _profile_payload_from_form(data, auth_user_id=None):
    username = normalize_username((data.get("username") or session.get("username") or "").lower().strip())
    email = _clean_email(data.get("email") or session.get("email"))
    phone = _normalize_phone(data.get("phone") or session.get("phone"))
    avatar_url = data.get("avatar_url") or data.get("profile_photo")
    avatar_upload_id = data.get("avatar_upload_id")
    cover_url = data.get("cover_url") or data.get("cover_photo")
    cover_upload_id = data.get("cover_upload_id")
    premium_tier = data.get("premium_tier") or ("premium" if data.get("is_premium") else "free")

    raw_payload = {
        "auth_user_id": auth_user_id or session.get("auth_user_id"),
        "username": username,
        "email": email,
        "normalized_email": email,
        "full_name": (data.get("full_name") or "").strip(),
        "bio": data.get("bio") or "",
        "gender": data.get("gender"),
        "age": safe_int(data.get("age"), None) if data.get("age") not in (None, "") else _age_from_dob(data.get("date_of_birth")),
        "country_origin": data.get("country_origin"),
        "preferred_language": data.get("preferred_language") or data.get("language_preferences"),
        "current_location": data.get("current_location"),
        "phone": phone,
        "normalized_phone": phone,
        "residential_address": data.get("residential_address"),
        "town": data.get("town"),
        "region": data.get("region"),
        "country_of_birth": data.get("country_of_birth") or data.get("country_origin"),
        "date_of_birth": data.get("date_of_birth"),
        "current_residential_location": data.get("current_residential_location") or data.get("current_location"),
        "avatar_url": avatar_url,
        "avatar_upload_id": avatar_upload_id,
        "profile_photo": avatar_url,
        "cover_url": cover_url,
        "cover_upload_id": cover_upload_id,
        "cover_photo": cover_url,
        "profile_video_url": data.get("profile_video_url") or data.get("video_intro_url"),
        "video_intro_url": data.get("profile_video_url") or data.get("video_intro_url"),
        "relationship_status": data.get("relationship_status") or data.get("relationship_goal"),
        "relationship_goal": data.get("relationship_status") or data.get("relationship_goal"),
        "creator_category": data.get("creator_category") or data.get("profile_type"),
        "profile_type": data.get("profile_type", "member"),
        "zodiac_sign": data.get("zodiac_sign"),
        "show_zodiac": _bool_value(data.get("show_zodiac")),
        "allow_zodiac_display": _bool_value(data.get("show_zodiac")),
        "allow_birthday_notifications": _bool_value(data.get("allow_birthday_notifications"), True),
        "profile_visibility": data.get("profile_visibility", "public"),
        "creator_mode_enabled": _bool_value(data.get("creator_mode_enabled")) or data.get("profile_type") in {"creator", "host"},
        "seller_mode_enabled": _bool_value(data.get("seller_mode_enabled")) or data.get("profile_type") == "seller",
        "dating_mode_enabled": _bool_value(data.get("dating_mode_enabled")),
        "premium_mode_enabled": _bool_value(data.get("premium_mode_enabled")) or str(data.get("premium_tier", "")).lower() == "premium",
        "account_mode": data.get("account_mode") or data.get("profile_type", "member"),
        "interests": _normalize_list(data.get("interests")),
        "activities": _normalize_list(data.get("activities")),
        "looking_for": _normalize_list(data.get("looking_for")),
        "languages": _normalize_list(data.get("languages")),
        "is_public": str(data.get("is_public", "true")).lower() not in {"false", "0", "off"},
        "is_verified": str(data.get("is_verified", "false")).lower() in {"true", "1", "on"},
        "is_premium": str(data.get("is_premium", "false")).lower() in {"true", "1", "on"} or premium_tier not in {"", "free"},
        "premium_tier": premium_tier,
        "wallet_balance": data.get("wallet_balance"),
        "username_slug": username,
        "terms_accepted": _bool_value(data.get("terms_accepted") or data.get("consent_accepted")),
        "human_confirmed": _bool_value(data.get("human_confirmed") or data.get("real_person_confirmed")),
        "anonymous_profile": _bool_value(data.get("anonymous_profile") or data.get("is_anonymous_avatar")),
        "updated_at": _utcnow_iso(),
    }
    raw_payload["profile_completion"] = get_profile_completion(raw_payload)
    raw_payload["profile_completed"] = False
    raw_payload["onboarding_step"] = "profile_setup"
    raw_payload["is_creator"] = raw_payload["profile_type"] in {"creator", "host"}
    return column_safe_payload("chain_profiles", raw_payload, fallback_columns=PROFILE_COLUMNS)


def _find_existing_profile(uid=None, profile_id=None, username=None, email=None):
    rows = []
    if uid:
        rows = safe_select("chain_profiles", columns="id,auth_user_id,username,email,phone", filters={"auth_user_id": uid}, limit=1, order_by=None)
    if not rows and profile_id:
        rows = safe_select("chain_profiles", columns="id,auth_user_id,username,email,phone", filters={"id": profile_id}, limit=1, order_by=None)
    if not rows and email:
        rows = safe_select("chain_profiles", columns="id,auth_user_id,username,email,phone", filters={"normalized_email": email}, limit=1, order_by=None)
    if not rows and username:
        rows = safe_select("chain_profiles", columns="id,auth_user_id,username,email,phone", filters={"username": username}, limit=1, order_by=None)
    return rows[0] if rows else None


def _check_duplicate_identity(payload, existing_id=None):
    username = payload.get("username")
    email = payload.get("normalized_email") or payload.get("email")
    phone = payload.get("normalized_phone") or payload.get("phone")
    town = payload.get("town")

    if username:
        owner = _neon_get_profile_by("username", username)
        if owner and owner.get("id") != existing_id:
            suggestions = ", ".join(_username_suggestions(username, town=town))
            return False, f"That username is already in use. Try {suggestions}."
        owner = safe_select("chain_profiles", columns="id", filters={"username": username}, limit=1, order_by=None)
        if owner and owner[0].get("id") != existing_id:
            suggestions = ", ".join(_username_suggestions(username, town=town))
            return False, f"That username is already in use. Try {suggestions}."

    if email:
        owner = _neon_get_profile_by("email", email)
        if owner and owner.get("id") != existing_id:
            return False, "That email is already connected to another CHAIN profile."
        for field in ("normalized_email", "email"):
            owner = safe_select("chain_profiles", columns="id", filters={field: email}, limit=1, order_by=None)
            if owner and owner[0].get("id") != existing_id:
                return False, "That email is already connected to another CHAIN profile."

    if phone:
        for field in ("normalized_phone", "phone"):
            owner = safe_select("chain_profiles", columns="id", filters={field: phone}, limit=1, order_by=None)
            if owner and owner[0].get("id") != existing_id:
                return False, "That phone number is already connected to another CHAIN profile."

    return True, None


def bootstrap_profile_for_current_user():
    uid = session.get("auth_user_id")
    if not uid:
        return False, "Missing authenticated session."

    current = get_current_profile()
    if current:
        return True, current

    email = _clean_email(session.get("email"))
    base_username = normalize_username(session.get("username") or ((email or "chain").split("@")[0]))
    username = base_username if _username_valid(base_username) else "chainuser"

    while _neon_get_profile_by("username", username) or safe_select("chain_profiles", columns="id", filters={"username": username}, limit=1, order_by=None):
        username = _username_suggestions(base_username)[0]

    payload = {
        "full_name": session.get("full_name") or username.replace("_", " ").title(),
        "username": username,
        "email": email,
        "phone": session.get("phone"),
        "profile_type": "member",
    }
    ok, result = ensure_neon_profile(
        uid,
        {
            "email": email,
            "username": username,
            "full_name": session.get("full_name") or username.replace("_", " ").title(),
            "profile_completed": False,
            "profile_type": "member",
        },
    )
    if ok and result:
        session["profile_id"] = result.get("id")
        session["username"] = result.get("username")
        delete_cache(cache_key("current_profile", uid))
        return True, result
    return False, result


def create_or_update_profile(data, auth_user_id=None):
    try:
        uid = auth_user_id or session.get("auth_user_id")
        payload = _profile_payload_from_form(data, auth_user_id=uid)
        if not payload.get("username") or not payload.get("full_name"):
            return False, "Username and full name are required."
        if not _username_valid(payload.get("username")):
            return False, "Use 3 to 30 lowercase letters, numbers or underscores only."

        existing = _neon_get_profile_by("auth_user_id", uid) or _find_existing_profile(
            uid=uid,
            profile_id=session.get("profile_id"),
            username=payload.get("username"),
            email=payload.get("normalized_email"),
        )
        is_valid, duplicate_error = _check_duplicate_identity(payload, existing_id=(existing or {}).get("id"))
        if not is_valid:
            return False, duplicate_error

        if existing:
            neon_payload = {
                "email": payload.get("email"),
                "username": payload.get("username"),
                "display_name": payload.get("full_name"),
                "full_name": payload.get("full_name"),
                "bio": payload.get("bio"),
                "phone": payload.get("phone"),
                "town": payload.get("town"),
                "region": payload.get("region"),
                "current_location": payload.get("current_location"),
                "country_origin": payload.get("country_origin"),
                "avatar_url": payload.get("avatar_url"),
                "creator_category": payload.get("creator_category"),
                "profile_completed": False,
                "dating_mode_enabled": payload.get("dating_mode_enabled"),
                "is_creator": payload.get("is_creator"),
            }
            _neon_update_profile(existing["id"], {key: value for key, value in neon_payload.items() if key in NEON_PROFILE_COLUMNS})
        else:
            ok, profile_or_error = ensure_neon_profile(
                uid,
                {
                    "email": payload.get("email"),
                    "username": payload.get("username"),
                    "full_name": payload.get("full_name"),
                    "display_name": payload.get("full_name"),
                    "dating_mode_enabled": payload.get("dating_mode_enabled"),
                    "profile_type": payload.get("profile_type"),
                },
            )
            if not ok:
                return False, profile_or_error

        profile = _neon_get_profile_by("auth_user_id", uid)
        if profile:
            session["profile_id"] = profile["id"]
            session["username"] = profile["username"]
            delete_cache(cache_key("current_profile", uid))
            delete_cache(cache_key("profile_username", profile["username"]))
            delete_cache(cache_key("profile_id", profile["id"]))
            delete_cache(cache_key("public_profiles", 20))
            return True, profile["username"]

        return False, "Profile could not be saved yet."
    except Exception as error:
        print(f"[profile_service] create_or_update_profile failed: {error}")
        return False, str(error)


def update_profile_setup(profile_id, form):
    try:
        profile = get_profile_by_id(profile_id)
        if not profile:
            return False, "Profile not found."

        payload = _profile_payload_from_form(form, auth_user_id=profile.get("auth_user_id"))
        if not payload.get("username") or not payload.get("full_name"):
            return False, "Full name and username are required."
        if not _username_valid(payload.get("username")):
            return False, "Use 3 to 30 lowercase letters, numbers or underscores only."

        is_valid, duplicate_error = _check_duplicate_identity(payload, existing_id=profile_id)
        if not is_valid:
            return False, duplicate_error

        neon_payload = {
            "email": payload.get("email"),
            "username": payload.get("username"),
            "display_name": payload.get("full_name"),
            "full_name": payload.get("full_name"),
            "bio": payload.get("bio"),
            "phone": payload.get("phone"),
            "date_of_birth": payload.get("date_of_birth"),
            "residential_address": payload.get("residential_address"),
            "town": payload.get("town"),
            "region": payload.get("region"),
            "current_location": payload.get("current_location"),
            "country_origin": payload.get("country_origin"),
            "preferred_language": payload.get("preferred_language"),
            "avatar_url": payload.get("avatar_url"),
            "cover_url": payload.get("cover_url"),
            "interests": payload.get("interests"),
            "activities": payload.get("activities"),
            "looking_for": payload.get("looking_for"),
            "gender": payload.get("gender"),
            "relationship_status": payload.get("relationship_status"),
            "creator_category": payload.get("creator_category"),
            "dating_mode_enabled": payload.get("dating_mode_enabled"),
            "is_creator": payload.get("is_creator"),
            "allow_messages": _bool_value(form.get("allow_messages"), True),
            "allow_dating": _bool_value(form.get("allow_dating")),
            "allow_gifts": _bool_value(form.get("allow_gifts"), True),
            "visibility": form.get("visibility") or form.get("profile_visibility") or "public",
            "tour_seen": _bool_value(form.get("tour_seen")),
            "onboarding_step": form.get("onboarding_step") or "profile",
        }
        _neon_update_profile(profile_id, {key: value for key, value in neon_payload.items() if key in NEON_PROFILE_COLUMNS})
        _save_onboarding_foundations(profile_id, form, payload)
        delete_cache(cache_key("profile_id", profile_id))
        delete_cache(cache_key("profile_username", profile.get("username")))
        delete_cache(cache_key("current_profile", profile.get("auth_user_id")))
        return complete_profile_setup(profile_id)
    except Exception as error:
        print(f"[profile_service] update_profile_setup failed: {error}")
        return False, str(error)


def _save_onboarding_foundations(profile_id, form, profile_payload):
    preferences_payload = {
        "live_categories": _normalize_list(form.get("live_categories")),
        "post_categories": _normalize_list(form.get("post_categories")),
        "language_preferences": _normalize_list(form.get("language_preferences") or form.get("languages")),
        "dating_interest": _normalize_list(form.get("dating_interest")),
        "creator_interest": _bool_value(form.get("creator_mode_enabled")),
        "seller_interest": _bool_value(form.get("seller_mode_enabled")),
        "preferred_regions": _normalize_list(form.get("preferred_regions") or form.get("region")),
        "updated_at": _utcnow_iso(),
    }
    if table_exists("chain_user_preferences"):
        _upsert_single(
            "chain_user_preferences",
            "profile_id",
            profile_id,
            preferences_payload,
            fallback_columns={"profile_id", "live_categories", "post_categories", "language_preferences", "dating_interest", "creator_interest", "seller_interest", "preferred_regions", "updated_at", "created_at"},
        )

    privacy_payload = {
        "profile_visibility": form.get("profile_visibility", "public"),
        "who_can_view_profile": form.get("who_can_view_profile", "everyone"),
        "allow_profile_discovery": _bool_value(form.get("allow_profile_discovery"), True),
        "allow_contact_from": form.get("allow_contact_from", "everyone"),
        "updated_at": _utcnow_iso(),
    }
    if table_exists("chain_user_privacy_settings"):
        _upsert_single(
            "chain_user_privacy_settings",
            "profile_id",
            profile_id,
            privacy_payload,
            fallback_columns={"profile_id", "profile_visibility", "who_can_view_profile", "allow_profile_discovery", "allow_contact_from", "updated_at", "created_at"},
        )

    call_payload = {
        "allow_messages": _bool_value(form.get("allow_messages"), True),
        "allow_audio_calls": _bool_value(form.get("allow_audio_calls"), True),
        "allow_video_calls": _bool_value(form.get("allow_video_calls"), True),
        "allow_high_quality_media": _bool_value(form.get("allow_high_quality_media"), True),
        "allow_status_video": _bool_value(form.get("allow_status_video"), True),
        "allow_music_uploads": _bool_value(form.get("allow_music_uploads"), True),
        "updated_at": _utcnow_iso(),
    }
    if table_exists("chain_user_call_settings"):
        _upsert_single(
            "chain_user_call_settings",
            "profile_id",
            profile_id,
            call_payload,
            fallback_columns={"profile_id", "allow_messages", "allow_audio_calls", "allow_video_calls", "allow_high_quality_media", "allow_status_video", "allow_music_uploads", "updated_at", "created_at"},
        )

    verification_payload = {
        "consent_accepted": _bool_value(form.get("consent_accepted")),
        "real_person_confirmed": _bool_value(form.get("real_person_confirmed")),
        "verification_status": "pending" if form.get("verification_selfie_url") else "self-attested",
        "selfie_url": form.get("verification_selfie_url"),
        "updated_at": _utcnow_iso(),
    }
    if table_exists("chain_user_verifications"):
        _upsert_single(
            "chain_user_verifications",
            "profile_id",
            profile_id,
            verification_payload,
            fallback_columns={"profile_id", "consent_accepted", "real_person_confirmed", "verification_status", "selfie_url", "updated_at", "created_at"},
        )

    avatar_payload = {
        "avatar_mode": form.get("avatar_mode", "upload"),
        "avatar_url": profile_payload.get("avatar_url"),
        "system_avatar_key": form.get("system_avatar_key"),
        "is_anonymous": _bool_value(form.get("is_anonymous_avatar")),
        "updated_at": _utcnow_iso(),
    }
    if table_exists("chain_profile_avatars"):
        _upsert_single(
            "chain_profile_avatars",
            "profile_id",
            profile_id,
            avatar_payload,
            fallback_columns={"profile_id", "avatar_mode", "avatar_url", "system_avatar_key", "is_anonymous", "updated_at", "created_at"},
        )

    if _bool_value(form.get("dating_mode_enabled")):
        dating_payload = {
            "is_enabled": True,
            "dating_intent": form.get("dating_intent", "open_to_meeting"),
            "dating_interest": _normalize_list(form.get("dating_interest")),
            "updated_at": _utcnow_iso(),
        }
        if table_exists("chain_dating_profiles"):
            _upsert_single(
                "chain_dating_profiles",
                "profile_id",
                profile_id,
                dating_payload,
                fallback_columns={"profile_id", "is_enabled", "dating_intent", "dating_interest", "updated_at", "created_at"},
            )


def complete_profile_setup(profile_id):
    profile = get_profile_by_id(profile_id)
    if not profile:
        return False, "Profile not found."

    completed = is_profile_complete(profile)
    _neon_update_profile(profile_id, {"profile_completed": completed, "onboarding_step": "complete" if completed else "profile"})
    delete_cache(cache_key("profile_id", profile_id))
    delete_cache(cache_key("current_profile", profile.get("auth_user_id")))
    if profile.get("username"):
        delete_cache(cache_key("profile_username", profile.get("username")))
    refreshed = get_profile_by_id(profile_id)
    return True, refreshed


def get_profile_settings(profile_id):
    settings = (safe_select("chain_user_settings", filters={"profile_id": profile_id}, limit=1, order_by=None) or [None])[0]
    security = (safe_select("chain_account_security", filters={"profile_id": profile_id}, limit=1, order_by=None) or [None])[0]

    if not settings and table_exists("chain_user_settings"):
        safe_insert(
            "chain_user_settings",
            {
                "profile_id": profile_id,
                "allow_messages": True,
                "allow_video_calls": True,
                "show_online_status": True,
                "profile_visibility": "public",
            },
            fallback_columns={"profile_id", "allow_messages", "allow_video_calls", "show_online_status", "profile_visibility", "created_at", "updated_at"},
        )
        settings = (safe_select("chain_user_settings", filters={"profile_id": profile_id}, limit=1, order_by=None) or [None])[0]

    profile = get_profile_by_id(profile_id) or {}
    if not security and table_exists("chain_account_security"):
        safe_insert(
            "chain_account_security",
            {
                "profile_id": profile_id,
                "email": profile.get("email"),
                "password_set": bool(profile.get("password_set")),
                "recovery_enabled": True,
            },
            fallback_columns={"profile_id", "email", "password_set", "recovery_enabled", "created_at", "updated_at"},
        )
        security = (safe_select("chain_account_security", filters={"profile_id": profile_id}, limit=1, order_by=None) or [None])[0]

    return {
        "settings": settings or {
            "profile_id": profile_id,
            "allow_messages": True,
            "allow_video_calls": True,
            "show_online_status": True,
            "profile_visibility": "public",
        },
        "security": security or {
            "profile_id": profile_id,
            "email": profile.get("email"),
            "password_set": bool(profile.get("password_set")),
            "recovery_enabled": True,
        },
    }


def record_profile_view(profile_id, viewer_profile_id=None):
    try:
        viewer = viewer_profile_id or session.get("profile_id")
        if table_exists("chain_recent_views"):
            safe_insert(
                "chain_recent_views",
                {
                    "profile_id": viewer,
                    "viewer_profile_id": viewer,
                    "viewed_profile_id": profile_id,
                    "view_type": "profile",
                    "created_at": _utcnow_iso(),
                },
                fallback_columns={"profile_id", "viewer_profile_id", "viewed_profile_id", "view_type", "created_at"},
            )

        profile = get_profile_by_id(profile_id)
        if profile:
            safe_update(
                "chain_profiles",
                {"profile_views": int(profile.get("profile_views") or 0) + 1, "updated_at": _utcnow_iso()},
                eq={"id": profile_id},
                fallback_columns=PROFILE_COLUMNS,
            )
        return True
    except Exception as error:
        print(f"[profile_service] record_profile_view failed: {error}")
        return False


def get_profile_counts(profile_id):
    profile = get_profile_by_id(profile_id) or {}
    followers = safe_count("chain_followers", filters={"following_profile_id": profile_id})
    if followers == 0:
        followers = safe_count("chain_follows", filters={"following_profile_id": profile_id})

    following = safe_count("chain_followers", filters={"follower_profile_id": profile_id})
    if following == 0:
        following = safe_count("chain_followers", filters={"profile_id": profile_id})
    if following == 0:
        following = safe_count("chain_follows", filters={"follower_profile_id": profile_id})

    likes = safe_count("chain_profile_likes", filters={"profile_id": profile_id})
    favorites = safe_count("chain_favorites", filters={"target_profile_id": profile_id})
    views = safe_count("chain_recent_views", filters={"viewed_profile_id": profile_id})

    return {
        "followers": followers or safe_int(profile.get("followers_count"), 0),
        "following": following or safe_int(profile.get("following_count"), 0),
        "likes": likes,
        "favorites": favorites,
        "views": views or safe_int(profile.get("profile_views"), 0),
    }


def get_profile_stats(profile_id):
    try:
        profile = get_profile_by_id(profile_id) or {}
        rooms = safe_count("chain_live_rooms", filters={"host_profile_id": profile_id})
        if rooms == 0:
            rooms = safe_count("chain_live_rooms", filters={"profile_id": profile_id})

        posts = safe_count("chain_posts", filters={"profile_id": profile_id})
        stories = safe_count("chain_stories", filters={"profile_id": profile_id})
        reels = safe_count("chain_reels", filters={"profile_id": profile_id})
        counts = get_profile_counts(profile_id)
        return {
            "rooms": rooms or safe_int(profile.get("live_rooms_count"), 0),
            "posts": posts or safe_int(profile.get("posts_count"), 0),
            "reels": reels or safe_int(profile.get("reels_count"), 0),
            "stories": stories,
            "followers": counts["followers"],
            "following": counts["following"],
            "likes": counts["likes"],
            "favorites": counts["favorites"],
            "views": counts["views"],
        }
    except Exception as error:
        print(f"[profile_service] get_profile_stats failed: {error}")
        return {"rooms": 0, "posts": 0, "reels": 0, "stories": 0, "followers": 0, "following": 0, "likes": 0, "favorites": 0, "views": 0}


def get_profile_content(profile_id, limit=8):
    rooms = safe_select("chain_live_rooms", columns="id,title,profile_id,status,is_live,category,viewer_count,cover_url,created_at", filters={"profile_id": profile_id}, limit=limit)
    posts = safe_select("chain_posts", columns="id,profile_id,body,caption,category,media_url,created_at", filters={"profile_id": profile_id}, limit=limit)
    reels = safe_select("chain_reels", columns="id,profile_id,caption,media_url,thumbnail_url,created_at", filters={"profile_id": profile_id}, limit=limit)
    stories = safe_select("chain_stories", columns="id,profile_id,caption,media_url,created_at", filters={"profile_id": profile_id}, limit=limit)
    return {
        "rooms": rooms, 
        "posts": posts, 
        "stories": stories,
        "reels": reels,
        "marketplace": [],
        "albums": []
    }


def get_wallet_snapshot(profile_id):
    wallet = (safe_select("chain_wallets", filters={"profile_id": profile_id}, limit=1) or [None])[0]
    if wallet:
        return wallet

    profile = get_profile_by_id(profile_id) or {}
    return {
        "coin_balance": profile.get("wallet_balance", 0) or 0,
        "gift_earnings": 0,
        "pending_withdrawal": 0,
    }


def get_creator_tools(profile_id):
    tools = (safe_select("chain_creator_tools", filters={"profile_id": profile_id}, limit=1) or [None])[0]
    if tools:
        return tools
    return {
        "profile_id": profile_id,
        "studio_enabled": False,
        "creator_notes": "",
        "featured_links": [],
    }


def get_profile_activity(profile_id):
    try:
        content = get_profile_content(profile_id, limit=5)
        gifts = safe_select("chain_live_gifts", filters={"host_profile_id": profile_id}, limit=5)
        if not gifts:
            gifts = safe_select("chain_gift_events", filters={"receiver_profile_id": profile_id}, limit=5)
        favorites = safe_select("chain_favorites", filters={"profile_id": profile_id}, limit=5)
        recent_views = safe_select("chain_recent_views", filters={"profile_id": profile_id}, limit=5)
        return {
            "rooms": content["rooms"],
            "posts": content["posts"],
            "stories": content["stories"],
            "gifts": gifts,
            "favorites": favorites,
            "recent_views": recent_views,
        }
    except Exception as error:
        print(f"[profile_service] get_profile_activity failed: {error}")
        return {"rooms": [], "posts": [], "stories": [], "gifts": [], "favorites": [], "recent_views": []}


def get_profile_actions(profile, viewer=None):
    own_profile = viewer and profile and viewer.get("id") == profile.get("id")
    stored_actions = safe_select("chain_profile_actions", filters={"profile_id": profile.get("id")}, limit=10)
    if stored_actions:
        return stored_actions

    username = profile.get("username")
    if own_profile:
        return [
            {"label": "Edit Profile", "href": "/profile/edit", "icon": "fa-user-pen", "kind": "link"},
            {"label": "Upload profile picture", "href": "/profile/edit", "icon": "fa-camera", "kind": "link"},
            {"label": "Create post", "href": "/features/create-post", "icon": "fa-square-plus", "kind": "link"},
            {"label": "Upload reel", "href": "/features/upload-reel", "icon": "fa-film", "kind": "link"},
            {"label": "Go live", "href": "/live/studio", "icon": "fa-video", "kind": "link"},
            {"label": "Wallet", "href": "/wallet/", "icon": "fa-wallet", "kind": "link"},
            {"label": "Verification", "href": "/profile/verification", "icon": "fa-badge-check", "kind": "link"},
            {"label": "Privacy settings", "href": "/profile/settings", "icon": "fa-shield-halved", "kind": "link"},
            {"label": "Account settings", "href": "/profile/settings", "icon": "fa-gear", "kind": "link"},
        ]

    return [
        {"label": "Follow", "href": f"/profile/follow/{profile.get('id')}", "icon": "fa-user-plus", "kind": "post"},
        {"label": "Message", "href": "/messages/", "icon": "fa-comment-dots", "kind": "link"},
        {"label": "Gift", "href": "/wallet/", "icon": "fa-gift", "kind": "link"},
        {"label": "Start video call", "href": f"/calls/video/{username}" if username else "/messages/", "icon": "fa-video", "kind": "link"},
    ]


def get_profile_bundle(username=None, profile_id=None, viewer=None):
    profile = get_profile_by_username(username) if username else get_profile_by_id(profile_id)
    if not profile:
        return None
    if profile.get("deleted_at"):
        return None
    if not is_adult_profile(profile):
        return None
    if profile.get("visibility") == "private" and (not viewer or viewer.get("id") != profile.get("id")):
        profile = {
            key: value
            for key, value in profile.items()
            if key not in {"bio", "interests", "activities", "looking_for", "relationship_status", "residential_address", "phone", "email", "date_of_birth"}
        }

    stats = get_profile_stats(profile["id"])
    content = get_profile_content(profile["id"])
    activity = get_profile_activity(profile["id"])
    wallet = get_wallet_snapshot(profile["id"])
    creator_tools = get_creator_tools(profile["id"])
    actions = get_profile_actions(profile, viewer=viewer)
    
    # Phase 8: Real-time Presence
    presence_row = safe_select("chain_presence", filters={"profile_id": profile["id"]}, limit=1)
    presence = presence_row[0] if presence_row else {"status": "offline", "last_seen": None}
    
    # Phase 8: Follow Status
    is_following = False
    is_page_liked = False
    if viewer:
        res = safe_select("chain_follows", filters={"follower_profile_id": viewer["id"], "following_profile_id": profile["id"]}, limit=1)
        is_following = bool(res)
        
        if profile.get('is_page'):
            res_like = safe_select("chain_page_likes", filters={"profile_id": viewer["id"], "page_id": profile["id"]}, limit=1)
            is_page_liked = bool(res_like)

    return {
        "profile": profile,
        "stats": stats,
        "content": content,
        "activity": activity,
        "wallet": wallet,
        "creator_tools": creator_tools,
        "actions": actions,
        "presence": presence,
        "is_following": is_following,
        "is_page_liked": is_page_liked
    }


def update_profile(auth_user_id, data):
    profile = get_current_profile()
    if not profile or profile.get("auth_user_id") != auth_user_id:
        return False, "Profile not found."
    return update_profile_setup(profile["id"], data)


def upload_profile_avatar(auth_user_id, file_obj):
    profile = get_current_profile()
    if not profile or profile.get("auth_user_id") != auth_user_id:
        return False, "Profile not found."
    from services.media_storage_service import upload_media_file
    result, error = upload_media_file(file_obj, bucket_name="chain-avatars", profile_id=profile["id"], upload_type="avatar", public=True)
    if not result:
        return False, error
    updated = _neon_update_profile(profile["id"], {"avatar_url": result.get("public_url"), "storage_bucket": result.get("bucket"), "storage_path": result.get("file_path")})
    delete_cache(cache_key("current_profile", auth_user_id))
    return True, updated or profile


def upload_profile_cover(auth_user_id, file_obj):
    profile = get_current_profile()
    if not profile or profile.get("auth_user_id") != auth_user_id:
        return False, "Profile not found."
    from services.media_storage_service import upload_media_file
    result, error = upload_media_file(file_obj, bucket_name="chain-covers", profile_id=profile["id"], upload_type="cover", public=True)
    if not result:
        return False, error
    updated = _neon_update_profile(profile["id"], {"cover_url": result.get("public_url"), "storage_bucket": result.get("bucket"), "storage_path": result.get("file_path")})
    delete_cache(cache_key("current_profile", auth_user_id))
    return True, updated or profile


def _recount_and_store_profile_counts(profile_id):
    counts = get_profile_counts(profile_id)
    safe_update(
        "chain_profiles",
        {
            "followers_count": counts["followers"],
            "following_count": counts["following"],
            "total_likes": counts["likes"],
            "profile_views": counts["views"],
            "updated_at": _utcnow_iso(),
        },
        eq={"id": profile_id},
        fallback_columns=PROFILE_COLUMNS,
    )
    profile = get_profile_by_id(profile_id)
    if profile:
        delete_cache(cache_key("profile_username", profile.get("username")))
        delete_cache(cache_key("profile_id", profile_id))


def follow_profile(username):
    current = get_current_profile()
    target = get_profile_by_username(username)
    if not current or not target or current["id"] == target["id"]:
        return False

    existing = safe_select(
        "chain_followers",
        filters={"follower_profile_id": current["id"], "following_profile_id": target["id"]},
        limit=1,
        order_by=None,
    )
    if not existing:
        safe_insert(
            "chain_followers",
            {
                "profile_id": current["id"],
                "follower_profile_id": current["id"],
                "following_profile_id": target["id"],
                "created_at": _utcnow_iso(),
            },
            fallback_columns={"profile_id", "follower_profile_id", "following_profile_id", "created_at"},
        )
    _recount_and_store_profile_counts(target["id"])
    _recount_and_store_profile_counts(current["id"])
    return True


def like_profile(username):
    current = get_current_profile()
    target = get_profile_by_username(username)
    if not current or not target or current["id"] == target["id"]:
        return False

    existing = safe_select(
        "chain_profile_likes",
        filters={"profile_id": target["id"], "liker_key": current["id"]},
        limit=1,
        order_by=None,
    )
    if not existing:
        safe_insert(
            "chain_profile_likes",
            {"profile_id": target["id"], "liker_key": current["id"], "created_at": _utcnow_iso()},
            fallback_columns={"profile_id", "liker_key", "created_at"},
        )
    _recount_and_store_profile_counts(target["id"])
    return True


def favorite_profile(username):
    current = get_current_profile()
    target = get_profile_by_username(username)
    if not current or not target or current["id"] == target["id"]:
        return False

    existing = safe_select(
        "chain_favorites",
        filters={"profile_id": current["id"], "target_profile_id": target["id"]},
        limit=1,
        order_by=None,
    )
    if not existing:
        safe_insert(
            "chain_favorites",
            {"profile_id": current["id"], "target_profile_id": target["id"], "created_at": _utcnow_iso()},
            fallback_columns={"profile_id", "target_profile_id", "created_at"},
        )
    return True


def report_profile(username, reason=None):
    current = get_current_profile()
    target = get_profile_by_username(username)
    if not current or not target:
        return False

    safe_insert(
        "chain_reports",
        {
            "reporter_profile_id": current["id"],
            "reported_profile_id": target["id"],
            "reason": reason or "Profile report",
            "status": "open",
            "created_at": _utcnow_iso(),
        },
        fallback_columns={"reporter_profile_id", "reported_profile_id", "reason", "status", "created_at"},
    )
    return True


def block_profile(username):
    current = get_current_profile()
    target = get_profile_by_username(username)
    if not current or not target or current["id"] == target["id"]:
        return False

    existing = safe_select(
        "chain_blocks",
        filters={"blocker_profile_id": current["id"], "blocked_profile_id": target["id"]},
        limit=1,
        order_by=None,
    )
    if not existing:
        safe_insert(
            "chain_blocks",
            {"blocker_profile_id": current["id"], "blocked_profile_id": target["id"], "created_at": _utcnow_iso()},
            fallback_columns={"blocker_profile_id", "blocked_profile_id", "created_at"},
        )
    return True
