import random
import re
import os
import time
from collections import OrderedDict
from datetime import datetime, timezone
import uuid

from flask import g, has_request_context, session
from psycopg2.extras import Json, RealDictCursor

from engines.cache_engine import cache_key, delete_cache, get_cache, set_cache
from engines.performance_engine import normalize_username, profile_completion_score, safe_int
from services.neon_service import execute, fetch_one, write_query, fast_query, get_cached_table_columns, table_exists as neon_table_exists, get_connection, release_connection
from services.supabase_safe import column_safe_payload, safe_count, safe_insert, safe_update, table_exists
from services.logging_service import log_error, log_info, log_warning

_CHAIN_PROFILE_COLUMNS_CACHE = None
_NEON_PROFILES_ENABLED_CACHE = None
_PUBLIC_PROFILE_REF_MISS_CACHE = OrderedDict()
_PUBLIC_PROFILE_REF_MISS_CACHE_LIMIT = 1024
_PUBLIC_PROFILE_REF_POSITIVE_TTL = 30
_PUBLIC_PROFILE_REF_NEGATIVE_TTL = 15
NEON_JSON_COLUMNS = {"interests", "activities", "looking_for", "linked_providers", "oauth_metadata", "portfolio_projects", "business_opening_hours", "business_location_data", "business_services", "business_products"}

CHAIN_PROFILE_SAFE_COLUMNS = {
    "id",
    "auth_user_id",
    "username",
    "display_name",
    "full_name",
    "bio",
    "avatar_url",
    "town",
    "city",
    "location",
    "creator_category",
    "is_verified",
    "verified",
    "is_online",
    "is_creator",
    "dating_mode_enabled",
    "profile_completed",
    "created_at",
    "updated_at",
    "deleted_at",
    "phone",
    "date_of_birth",
    "residential_address",
    "preferred_language",
    "interests",
    "activities",
    "looking_for",
    "cover_url",
    "banner_url",
    "banner_path",
    "avatar_bucket",
    "avatar_path",
    "avatar_mime_type",
    "avatar_size_bytes",
    "avatar_storage_bucket",
    "avatar_storage_path",
    "avatar_updated_at",
    "cover_bucket",
    "cover_path",
    "cover_mime_type",
    "cover_size_bytes",
    "cover_storage_bucket",
    "cover_storage_path",
    "cover_updated_at",
    "wallet_balance",
    "onboarding_step",
    "current_location",
    "region",
    "country_origin",
    "is_premium",
    "premium_tier",
    "followers_count",
    "following_count",
    "posts_count",
    "reels_count",
    "saved_count",
    "tagged_count",
    "profile_views",
    "total_likes",
    "is_public",
    "gender",
    "age",
    "relationship_status",
    "languages",
    "email",
    "normalized_email",
    "normalized_phone",
    "account_type",
    "business_name",
    "business_website",
    "business_opening_hours",
    "business_location_data",
    "business_services",
    "business_products",
    "business_contact_email",
    "business_contact_phone",
    "trust_score",
}


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
    "current_country",
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
    "banner_url",
    "banner_path",
    "cover_upload_id",
    "avatar_bucket",
    "avatar_path",
    "avatar_mime_type",
    "avatar_size_bytes",
    "avatar_storage_bucket",
    "avatar_storage_path",
    "avatar_updated_at",
    "cover_bucket",
    "cover_path",
    "cover_mime_type",
    "cover_size_bytes",
    "cover_storage_bucket",
    "cover_storage_path",
    "cover_updated_at",
    "profile_photo",
    "profile_video_url",
    "video_intro_url",
    "relationship_status",
    "account_type",
    "business_name",
    "business_website",
    "business_opening_hours",
    "business_location_data",
    "business_services",
    "business_products",
    "business_contact_email",
    "business_contact_phone",
    "trust_score",
    "relationship_goal",
    "creator_category",
    "profile_type",
    "visibility",
    "interests",
    "languages",
    "is_public",
    "is_verified",
    "email_verified",
    "is_premium",
    "premium_tier",
    "followers_count",
    "following_count",
    "posts_count",
    "reels_count",
    "saved_count",
    "tagged_count",
    "profile_views",
    "total_likes",
    "wallet_balance",
    "profile_completion",
    "profile_completed",
    "onboarding_step",
    "website",
    "pronouns",
    "skills",
    "profile_theme",
    "rank",
    "chain_score",
    "trust_score",
    "portfolio_url",
    "portfolio_projects",
    "business_name",
    "video_intro_url",
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
    "current_country",
    "current_location",
    "country_origin",
    "avatar_url",
    "cover_url",
    "banner_url",
    "banner_path",
    "avatar_bucket",
    "avatar_path",
    "avatar_mime_type",
    "avatar_size_bytes",
    "avatar_storage_bucket",
    "avatar_storage_path",
    "avatar_updated_at",
    "cover_bucket",
    "cover_path",
    "cover_mime_type",
    "cover_size_bytes",
    "cover_storage_bucket",
    "cover_storage_path",
    "cover_updated_at",
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
    "saved_count",
    "tagged_count",
    "live_rooms_count",
    "profile_views",
    "total_achievements",
    "total_albums",
    "total_bookmarks",
    "total_collections",
    "total_comments",
    "total_likes",
    "total_profile_views",
    "total_shares",
    "wallet_balance",
    "verified",
    "email_verified",
    "visibility",
    "profile_visibility",
    "allow_messages",
    "allow_dating",
    "allow_gifts",
    "terms_accepted_at",
    "privacy_accepted_at",
    "privacy_accepted",
    "privacy_version",
    "terms_version",
    "who_can_message",
    "who_can_call",
    "who_can_see_status",
    "message_only_after_match",
    "tour_seen",
    "onboarding_step",
    "profile_completed",
    "website",
    "pronouns",
    "skills",
    "profile_theme",
    "profile_score",
    "profile_level",
    "rank",
    "chain_score",
    "trust_score",
    "occupation",
    "company",
    "school",
    "university",
    "mood_emoji",
    "mood_text",
    "current_activity",
    "quote_of_day",
    "activity_status",
    "member_since",
    "country_flag",
    "city_name",
    "premium_badge",
    "creator_badge",
    "business_badge",
    "government_badge",
    "ngo_badge",
    "student_badge",
    "medical_badge",
    "teacher_badge",
    "community_rating",
    "friendliness_score",
    "safety_score",
    "response_rate",
    "response_time",
    "popularity_score",
    "activity_level",
    "scam_protection",
    "identity_verified",
    "verification_type",
    "gold_badge",
    "local_time",
    "weather_emoji",
    "weather_temp",
    "portfolio_url",
    "portfolio_projects",
    "business_name",
    "premium_tier",
    "profile_completion",
    "relationship_goal",
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


def _chain_profile_columns_set(refresh=False):
    """
    Fast profile column cache.

    CHAIN now adds the required profile columns to Neon.
    This function avoids repeated schema discovery during /messages/.
    """
    global _CHAIN_PROFILE_COLUMNS_CACHE

    trust_schema = os.getenv("CHAIN_TRUST_PROFILE_SCHEMA", "1") != "0"

    if trust_schema and not refresh:
        if _CHAIN_PROFILE_COLUMNS_CACHE is None:
            try:
                actual = set(get_cached_table_columns("chain_profiles", timeout_ms=2000) or [])
                if actual:
                    _CHAIN_PROFILE_COLUMNS_CACHE = set(NEON_PROFILE_COLUMNS) & actual
                else:
                    _CHAIN_PROFILE_COLUMNS_CACHE = set(NEON_PROFILE_COLUMNS)
            except Exception:
                _CHAIN_PROFILE_COLUMNS_CACHE = set(NEON_PROFILE_COLUMNS)
        return _CHAIN_PROFILE_COLUMNS_CACHE

    if _CHAIN_PROFILE_COLUMNS_CACHE is not None and not refresh:
        return _CHAIN_PROFILE_COLUMNS_CACHE

    try:
        columns = set(get_cached_table_columns("chain_profiles", timeout_ms=800) or [])
        if columns:
            _CHAIN_PROFILE_COLUMNS_CACHE = columns
            return columns
    except Exception as e:
        print("[profile_service] profile column discovery failed:", e)

    _CHAIN_PROFILE_COLUMNS_CACHE = set(CHAIN_PROFILE_SAFE_COLUMNS)
    return _CHAIN_PROFILE_COLUMNS_CACHE

def _filter_chain_profile_payload(payload):
    if not payload:
        return {}
    actual_columns = _chain_profile_columns_set()
    if not actual_columns:
        return {key: value for key, value in payload.items() if key in CHAIN_PROFILE_SAFE_COLUMNS}
    return {key: value for key, value in payload.items() if key in actual_columns}


def _adapt_neon_value(key, value):
    if key in NEON_JSON_COLUMNS and isinstance(value, (list, dict)):
        return Json(value)
    return value


def _is_production_env():
    if os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    return os.getenv("FLASK_ENV") == "production" or os.getenv("ENV") == "production"


def _extract_missing_column(error):
    text = str(error or "")
    match = re.search(r'column "([^"]+)" (?:of relation "[^"]+" )?does not exist', text, flags=re.I)
    return match.group(1) if match else None


def _safe_profile_save_log(event, payload=None, error=None, operation=None, auth_user_id=None):
    payload = payload or {}
    log_error(
        event,
        operation=operation,
        auth_user_id_present=bool(auth_user_id or payload.get("auth_user_id")),
        email_present=bool(payload.get("email")),
        username_present=bool(payload.get("username")),
        payload_keys=sorted(payload.keys()),
        missing_column=_extract_missing_column(error),
        error=str(error) if error else None,
    )


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


def normalize_dob(date_of_birth):
    if not date_of_birth:
        return None
    try:
        dob_str = str(date_of_birth).strip()
        # Try DD/MM/YYYY
        if "/" in dob_str:
            try:
                dt = datetime.strptime(dob_str, "%d/%m/%Y")
                return dt.date().isoformat()
            except ValueError:
                pass
        # Try ISO
        try:
            dt = datetime.fromisoformat(dob_str)
            return dt.date().isoformat()
        except ValueError:
            pass
        return dob_str
    except Exception:
        return str(date_of_birth)


def _age_from_dob(date_of_birth):
    if not date_of_birth:
        return None
    try:
        dob_str = str(date_of_birth).strip()
        dob = None

        # Try DD/MM/YYYY
        if "/" in dob_str:
            try:
                dob = datetime.strptime(dob_str, "%d/%m/%Y").date()
            except ValueError:
                pass

        # Try YYYY-MM-DD (ISO)
        if not dob:
            try:
                dob = datetime.fromisoformat(dob_str).date()
            except ValueError:
                pass

        if not dob:
            return None

        today = datetime.now(timezone.utc).date()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except (ValueError, TypeError):
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

    dob = profile.get("date_of_birth")
    if not dob and has_request_context():
        # Fallback to session if DB is stale/missing
        from services.session_service import K_PENDING_DATE_OF_BIRTH
        dob = session.get(K_PENDING_DATE_OF_BIRTH) or session.get("date_of_birth")

    return _age_from_dob(dob)


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
    if has_request_context():
        from services.session_service import K_AGE_CHECK_REQUIRED
        if not _is_production_env() and session.get("age_verified") is True:
            return True, None
        if session.get(K_AGE_CHECK_REQUIRED) is False:
            return True, None

    is_adult = is_adult_profile(profile)
    if is_adult is True:
        return True, None
    if is_adult is False:
        return False, "NamVibe is only available to users 18 and older."
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
    username = normalized.get("username") or (normalized.get("email", "").split("@")[0] if normalized.get("email") else "user")
    display_name = normalized.get("display_name") or normalized.get("full_name") or username.replace("_", " ").title()
    created_at = normalized.get("created_at") or _utcnow_iso()
    normalized["username"] = username
    normalized["display_name"] = display_name
    normalized["full_name"] = normalized.get("full_name") or display_name
    normalized["bio"] = normalized.get("bio") or ""
    normalized["avatar_url"] = normalized.get("avatar_url") or normalized.get("profile_photo")
    normalized["cover_url"] = normalized.get("cover_url") or normalized.get("cover_photo")
    normalized["profile_video_url"] = normalized.get("profile_video_url") or normalized.get("video_intro_url")
    parts = [normalized.get("town"), normalized.get("region"), normalized.get("country_origin")]
    parts = [p for p in parts if p]
    assembled = ", ".join(parts) if parts else ""
    normalized["location"] = normalized.get("location") or normalized.get("current_location") or assembled
    normalized["current_location"] = normalized.get("current_location") or normalized.get("location") or assembled
    normalized["website"] = normalized.get("website") or normalized.get("portfolio_url") or ""
    normalized["created_at"] = created_at
    normalized["last_login_at"] = normalized.get("last_login_at") or normalized.get("last_active") or normalized.get("updated_at") or created_at
    normalized["profile_type"] = normalized.get("profile_type") or ("creator" if normalized.get("is_creator") else "member")
    normalized["creator_category"] = normalized.get("creator_category") or normalized.get("profile_type")
    normalized["premium_tier"] = normalized.get("premium_tier") or ("premium" if normalized.get("is_premium") else "free")
    normalized["is_premium"] = bool(normalized.get("is_premium") or normalized.get("premium_tier") not in {None, "", "free"})
    normalized["email_verified"] = _bool_value(normalized.get("email_verified"))
    normalized["is_verified"] = _bool_value(normalized.get("is_verified") or normalized.get("verified") or normalized.get("email_verified"))
    normalized["verified"] = _bool_value(normalized.get("verified") or normalized.get("is_verified"))
    normalized["wallet_balance"] = normalized.get("wallet_balance") or 0
    normalized["followers_count"] = safe_int(normalized.get("followers_count"), 0)
    normalized["following_count"] = safe_int(normalized.get("following_count"), 0)
    normalized["posts_count"] = safe_int(normalized.get("posts_count"), 0)
    normalized["reels_count"] = safe_int(normalized.get("reels_count"), 0)
    normalized["total_likes"] = safe_int(normalized.get("total_likes"), 0)
    normalized["profile_views"] = safe_int(normalized.get("profile_views"), 0)
    normalized["chain_score"] = safe_int(normalized.get("chain_score"), 0)
    normalized["trust_score"] = safe_int(normalized.get("trust_score"), 0)
    normalized["rank"] = normalized.get("rank") or "New Member"
    normalized["interests"] = _normalize_list(normalized.get("interests"))
    normalized["skills"] = _normalize_list(normalized.get("skills"))
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
    global _NEON_PROFILES_ENABLED_CACHE
    if _NEON_PROFILES_ENABLED_CACHE is True:
        return True
    if os.getenv("CHAIN_TRUST_PROFILE_SCHEMA", "1") != "0":
        _NEON_PROFILES_ENABLED_CACHE = True
        return True
    enabled = neon_table_exists("chain_profiles")
    if enabled:
        _NEON_PROFILES_ENABLED_CACHE = True
    return enabled


def _drop_missing_profile_column(column):
    global _CHAIN_PROFILE_COLUMNS_CACHE
    if not column:
        return
    NEON_PROFILE_COLUMNS.discard(column)
    if _CHAIN_PROFILE_COLUMNS_CACHE:
        _CHAIN_PROFILE_COLUMNS_CACHE.discard(column)


def _public_profile_ref_missing_marker():
    return {"__profile_public_ref_missing__": True}


def _public_profile_ref_cache_key(username=None, profile_id=None):
    if profile_id:
        return cache_key("profile_public_ref", "v2", "id", profile_id)
    normalized = _normalize_public_profile_handle(username)
    return cache_key("profile_public_ref", "v2", "username", normalized)


def _normalize_public_profile_handle(username):
    raw = str(username or "").strip().lstrip("@")
    if not raw or len(raw) > 64 or not re.search(r"[A-Za-z0-9]", raw):
        return None
    return normalize_username(raw)


def _public_profile_ref_cache_store(*, username=None, profile_id=None, profile=None, missing=False):
    key = _public_profile_ref_cache_key(username=username, profile_id=profile_id)
    if not key:
        return None
    if missing:
        marker = _public_profile_ref_missing_marker()
        set_cache(key, marker, ttl=_PUBLIC_PROFILE_REF_NEGATIVE_TTL)
        _PUBLIC_PROFILE_REF_MISS_CACHE[key] = {"value": marker, "expires_at": time.time() + _PUBLIC_PROFILE_REF_NEGATIVE_TTL}
        while len(_PUBLIC_PROFILE_REF_MISS_CACHE) > _PUBLIC_PROFILE_REF_MISS_CACHE_LIMIT:
            _PUBLIC_PROFILE_REF_MISS_CACHE.popitem(last=False)
        return None
    if profile is None:
        return None
    set_cache(key, profile, ttl=_PUBLIC_PROFILE_REF_POSITIVE_TTL)
    if key in _PUBLIC_PROFILE_REF_MISS_CACHE:
        _PUBLIC_PROFILE_REF_MISS_CACHE.pop(key, None)
    return profile


def _public_profile_ref_cache_get(*, username=None, profile_id=None):
    key = _public_profile_ref_cache_key(username=username, profile_id=profile_id)
    if not key:
        return None, key, False
    now = time.time()
    cached = _PUBLIC_PROFILE_REF_MISS_CACHE.get(key)
    if cached is not None:
        if cached.get("expires_at", 0) > now:
            _PUBLIC_PROFILE_REF_MISS_CACHE.move_to_end(key)
            return None, key, True
        _PUBLIC_PROFILE_REF_MISS_CACHE.pop(key, None)
    cached = get_cache(key)
    if cached is not None and isinstance(cached, dict) and cached.get("__profile_public_ref_missing__"):
        _PUBLIC_PROFILE_REF_MISS_CACHE[key] = {"value": cached, "expires_at": now + _PUBLIC_PROFILE_REF_NEGATIVE_TTL}
        while len(_PUBLIC_PROFILE_REF_MISS_CACHE) > _PUBLIC_PROFILE_REF_MISS_CACHE_LIMIT:
            _PUBLIC_PROFILE_REF_MISS_CACHE.popitem(last=False)
        return None, key, True
    return cached, key, False


def _fetch_public_profile_reference(sql_text, params, timeout_ms=1200):
    conn = None
    try:
        conn = get_connection(timeout_ms=timeout_ms)
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SET statement_timeout = {int(timeout_ms)}")
                cur.execute(sql_text, params)
                row = cur.fetchone()
                return dict(row) if row else None
    finally:
        if conn:
            release_connection(conn)


def invalidate_public_profile_reference_cache(profile=None, profile_id=None, username=None, previous_username=None):
    candidates = []
    if profile and isinstance(profile, dict):
        profile_id = profile_id or profile.get("id")
        username = username or profile.get("username")
        previous_username = previous_username or profile.get("previous_username")
    if profile_id:
        candidates.append(_public_profile_ref_cache_key(profile_id=profile_id))
    for candidate_username in (username, previous_username):
        if candidate_username:
            candidates.append(_public_profile_ref_cache_key(username=candidate_username))
    for key in candidates:
        if key:
            delete_cache(key)
            _PUBLIC_PROFILE_REF_MISS_CACHE.pop(key, None)


def _neon_profile_columns():
    """Return optimized set of profile columns for lookups.

    Uses lightweight columns by default to reduce query overhead.
    Full profile with all columns is only returned when explicitly needed.
    """
    columns = [column for column in _chain_profile_columns_set() if column in NEON_PROFILE_COLUMNS]
    if not columns:
        columns = ["id", "auth_user_id", "email", "username", "display_name", "full_name", "profile_completed", "created_at", "updated_at"]
    return ", ".join(columns)


# Lightweight profile columns for fast lookups (only essential fields)
_LIGHTWEIGHT_FULL_COLUMNS = "id, auth_user_id, username, display_name, full_name, avatar_url, cover_url, bio, is_verified, email, email_verified, is_premium, premium_tier, is_public, followers_count, following_count, profile_completed, created_at, updated_at, deleted_at"


# Lightweight profile columns for fast lookups (username, avatar, verification)
_LIGHTWEIGHT_PROFILE_COLUMNS = "id, username, full_name, avatar_url, is_verified, verification_level, deleted_at"


def _test_fallback_profile(auth_user_id=None, profile_id=None, email=None):
    fallback_id = profile_id or auth_user_id or str(uuid.uuid4())
    try:
        uuid.UUID(str(fallback_id))
    except (ValueError, TypeError):
        fallback_id = str(uuid.uuid4())
    fallback_auth_user_id = auth_user_id or fallback_id
    try:
        uuid.UUID(str(fallback_auth_user_id))
    except (ValueError, TypeError):
        fallback_auth_user_id = fallback_id
    return normalize_profile({
        "id": str(fallback_id),
        "auth_user_id": str(fallback_auth_user_id),
        "username": session.get("username") or "",
        "full_name": session.get("full_name") or "",
        "email": email or "",
        "is_verified": False,
        "email_verified": False,
        "profile_completed": False,
    })


def get_lightweight_profile(profile_id):
    """Get minimal profile data for lists (username, avatar, verified) with caching."""
    if not profile_id:
        return None

    cache_key_str = cache_key("profile_light", profile_id, 60, 0)
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached

    try:
        row = fetch_one(
            f"SELECT {_LIGHTWEIGHT_PROFILE_COLUMNS} FROM chain_profiles WHERE id = %s AND deleted_at IS NULL LIMIT 1",
            [profile_id],
            timeout_ms=1000,
        )
        if row:
            result = {
                "id": row.get("id"),
                "username": row.get("username"),
                "full_name": row.get("full_name"),
                "avatar_url": row.get("avatar_url"),
                "is_verified": row.get("is_verified"),
                "verification_level": row.get("verification_level", 0),
            }
            set_cache(cache_key_str, result, ttl=60)
            return result
    except Exception as error:
        print(f"[profile_service] lightweight profile lookup failed: {error}")

    return None


def _direct_profile_lookup(field, value, timeout_ms=4000):
    if not _neon_profiles_enabled() or value in (None, ""):
        return None
    if field in {"id", "auth_user_id"}:
        try:
            uuid.UUID(str(value))
        except (ValueError, TypeError):
            return None
    try:
        row = fetch_one(
            f"SELECT {_neon_profile_columns()} FROM chain_profiles WHERE {field} = %s AND deleted_at IS NULL LIMIT 1",
            [value],
            timeout_ms=timeout_ms,
        )
        return normalize_profile(row) if row else None
    except Exception as error:
        print(f"[profile_service] direct neon lookup failed for {field}: {error}")
        missing_column = _extract_missing_column(error)
        if missing_column:
            _drop_missing_profile_column(missing_column)
            try:
                row = fetch_one(
                    f"SELECT {_neon_profile_columns()} FROM chain_profiles WHERE {field} = %s AND deleted_at IS NULL LIMIT 1",
                    [value],
                    timeout_ms=timeout_ms,
                )
                return normalize_profile(row) if row else None
            except Exception as retry_error:
                print(f"[profile_service] direct neon lookup retry failed for {field}: {retry_error}")
        return None


def _neon_get_profile_by(field, value, use_lightweight=False):
    """Get profile by field with caching and adaptive column selection.

    Args:
        field: Column to search by
        value: Value to search for
        use_lightweight: If True, only fetches essential columns for faster lookups.
                         Set to True when full profile normalization isn't needed
                         (e.g., for presence, lightweight UI components).
    """
    if not _neon_profiles_enabled() or value in (None, ""):
        return None
    if field in {"id", "auth_user_id"}:
        try:
            uuid.UUID(str(value))
        except (ValueError, TypeError):
            return None

    # Use lightweight columns when full profile isn't needed
    columns = _LIGHTWEIGHT_FULL_COLUMNS if use_lightweight else _neon_profile_columns()
    timeout = 2000 if use_lightweight else 10000

    try:
        rows = fast_query(
            f"SELECT {columns} FROM chain_profiles WHERE {field} = %s AND deleted_at IS NULL LIMIT 1",
            [value],
            timeout_ms=timeout,
        )
        row = rows[0] if rows else None
        if row:
            if use_lightweight:
                return row
            return normalize_profile(row)
        return None
    except Exception as error:
        print(f"[profile_service] neon lookup failed for {field}: {error}")
        missing_column = _extract_missing_column(error)
        if missing_column:
            _drop_missing_profile_column(missing_column)
            try:
                rows = fast_query(
                    f"SELECT {_neon_profile_columns()} FROM chain_profiles WHERE {field} = %s AND deleted_at IS NULL LIMIT 1",
                    [value],
                    timeout_ms=2000,
                )
                row = rows[0] if rows else None
                if row:
                    return normalize_profile(row)
            except Exception as retry_error:
                print(f"[profile_service] neon lookup retry failed for {field}: {retry_error}")
        return _direct_profile_lookup(field, value, timeout_ms=2000)


def _neon_insert_profile(payload):
    payload = _filter_chain_profile_payload(payload)
    if not payload:
        _safe_profile_save_log("profile_insert_empty_payload", payload=payload, operation="insert")
        return None
    columns = list(payload.keys())
    placeholders = ", ".join(["%s"] * len(columns))

    # Use ON CONFLICT to ensure one user = one profile
    sql = f"""
        INSERT INTO chain_profiles ({', '.join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (auth_user_id) DO UPDATE
        SET updated_at = now()
        RETURNING {_neon_profile_columns()}
    """
    try:
        results = write_query(sql, [_adapt_neon_value(key, value) for key, value in payload.items()], timeout_ms=3000)
        return normalize_profile(results[0]) if results else None
    except Exception as error:
        missing_column = _extract_missing_column(error)
        if missing_column and missing_column in payload:
            _drop_missing_profile_column(missing_column)
            retry_payload = {key: value for key, value in payload.items() if key != missing_column}
            if retry_payload:
                return _neon_insert_profile(retry_payload)
        _safe_profile_save_log(
            "profile_insert_failed",
            payload=payload,
            error=error,
            operation="insert",
            auth_user_id=payload.get("auth_user_id"),
        )
        print(f"[profile_service] _neon_insert_profile failed: {error}")
        raise


def _neon_update_profile(profile_id, payload):
    payload = _filter_chain_profile_payload(payload)
    if not payload:
        _safe_profile_save_log("profile_update_empty_payload", payload=payload, operation="update")
        return None
    assignments = ", ".join(f"{key} = %s" for key in payload.keys())
    params = [_adapt_neon_value(key, value) for key, value in payload.items()] + [profile_id]
    try:
        results = write_query(
            f"UPDATE chain_profiles SET {assignments}, updated_at = now() WHERE id = %s RETURNING {_neon_profile_columns()}",
            params,
            timeout_ms=3000,
        )
        return normalize_profile(results[0]) if results else None
    except Exception as error:
        missing_column = _extract_missing_column(error)
        if missing_column and missing_column in payload:
            _drop_missing_profile_column(missing_column)
            retry_payload = {key: value for key, value in payload.items() if key != missing_column}
            if retry_payload:
                return _neon_update_profile(profile_id, retry_payload)
        _safe_profile_save_log(
            "profile_update_failed",
            payload=payload,
            error=error,
            operation="update",
            auth_user_id=payload.get("auth_user_id"),
        )
        print(f"[profile_service] _neon_update_profile failed: {error}")
        return None


def bootstrap_profile_for_current_user(defaults=None):
    """Backward-compatible wrapper: ensure profile for the current session user."""
    if not has_request_context():
        return None, "No request context"
    auth_user_id = session.get("auth_user_id")
    if not auth_user_id:
        return None, "No auth_user_id in session"
    return ensure_neon_profile(auth_user_id, defaults=defaults)


def create_or_update_profile(profile_id, updates=None):
    """Backward-compatible wrapper: update profile by ID."""
    updates = updates or {}
    if not profile_id:
        return None
    try:
        uuid.UUID(str(profile_id))
    except (ValueError, TypeError):
        return None
    return _neon_update_profile(profile_id, updates)


def ensure_neon_profile(auth_user_id, defaults=None):
    defaults = defaults or {}
    try:
        uuid.UUID(str(auth_user_id))
    except (TypeError, ValueError):
        _safe_profile_save_log(
            "ensure_neon_profile_invalid_auth_user_id",
            payload=defaults,
            operation="validate",
            auth_user_id=auth_user_id,
        )
        return None, "Profile save failed: auth_user_id is not a valid UUID."
    profile = _neon_get_profile_by("auth_user_id", auth_user_id)
    if profile:
        return profile, None
    fallback_existing = _find_existing_profile(
        uid=auth_user_id,
        profile_id=session.get("profile_id") if has_request_context() else None,
        username=normalize_username(defaults.get("username") or session.get("username") or "") if has_request_context() else normalize_username(defaults.get("username") or ""),
        email=_clean_email(defaults.get("email") or (session.get("email") if has_request_context() else None)),
    )
    if fallback_existing and fallback_existing.get("id"):
        update_payload = _filter_chain_profile_payload({
            **defaults,
            "auth_user_id": auth_user_id,
            "email": _clean_email(defaults.get("email") or fallback_existing.get("email")),
            "username": normalize_username(defaults.get("username") or fallback_existing.get("username") or ""),
            "display_name": defaults.get("display_name") or defaults.get("full_name") or fallback_existing.get("full_name"),
            "full_name": defaults.get("full_name") or defaults.get("display_name") or fallback_existing.get("full_name"),
        })
        if update_payload:
            updated = _neon_update_profile(fallback_existing["id"], update_payload)
            if updated:
                return updated, None
            _safe_profile_save_log(
                "ensure_neon_profile_existing_update_failed",
                payload=update_payload,
                operation="update",
                auth_user_id=auth_user_id,
            )
            return None, "Profile update failed for existing profile."
        return normalize_profile(fallback_existing), None
    username = normalize_username(defaults.get("username") or session.get("username") or "user")
    if not _username_valid(username):
        username = "user"
    while _neon_get_profile_by("username", username):
        username = _username_suggestions(username, defaults.get("town"))[0]
    payload = _filter_chain_profile_payload({
        **defaults,
        "auth_user_id": auth_user_id,
        "email": _clean_email(defaults.get("email") or session.get("email")),
        "normalized_email": _clean_email(defaults.get("normalized_email") or defaults.get("email") or session.get("email")),
        "username": username,
        "username_slug": username,
        "display_name": (defaults.get("display_name") or defaults.get("full_name") or username).strip(),
        "full_name": (defaults.get("full_name") or defaults.get("display_name") or username).strip(),
        "phone": defaults.get("phone") or (session.get("phone") if has_request_context() else None),
        "normalized_phone": defaults.get("normalized_phone") or _normalize_phone(defaults.get("phone") or session.get("phone")),
        "date_of_birth": defaults.get("date_of_birth"),
        "residential_address": defaults.get("residential_address"),
        "preferred_language": defaults.get("preferred_language"),
        "interests": defaults.get("interests") or [],
        "activities": defaults.get("activities") or [],
        "looking_for": defaults.get("looking_for") or [],
        "bio": defaults.get("bio") or "",
        "town": defaults.get("town"),
        "region": defaults.get("region"),
        "country_origin": defaults.get("country_origin"),
        "country": defaults.get("country"),
        "current_country": defaults.get("current_country") or defaults.get("country"),
        "current_location": defaults.get("current_location") or defaults.get("town"),
        "profile_completed": bool(defaults.get("profile_completed", False)),
        "email_verified": bool(defaults.get("email_verified", False)),
        "is_verified": bool(defaults.get("is_verified", False)),
        "dating_mode_enabled": bool(defaults.get("dating_mode_enabled", False)),
        "is_creator": bool(defaults.get("profile_type") in {"creator", "host"}),
        "creator_category": defaults.get("profile_type"),
        "onboarding_step": defaults.get("onboarding_step") or "account",
    })
    required_after_filter = {"auth_user_id", "email", "username"}
    missing_required = sorted(required_after_filter - set(payload.keys()))
    if missing_required:
        _safe_profile_save_log(
            "ensure_neon_profile_missing_required_columns",
            payload=payload,
            error=f"missing required columns after schema filtering: {', '.join(missing_required)}",
            operation="insert",
            auth_user_id=auth_user_id,
        )
        return None, f"Profile save failed: missing required profile columns ({', '.join(missing_required)})."
    try:
        inserted = _neon_insert_profile(payload)
        if inserted:
            return normalize_profile({**payload, **inserted}), None
        _safe_profile_save_log(
            "ensure_neon_profile_insert_empty_result",
            payload=payload,
            operation="insert",
            auth_user_id=auth_user_id,
        )
        return None, "Profile insert returned no row."
    except Exception as error:
        _safe_profile_save_log(
            "ensure_neon_profile_failed",
            payload=payload,
            error=error,
            operation="insert",
            auth_user_id=auth_user_id,
        )
        return None, f"Profile insert failed: {error}"


def ensure_profile_for_user(user_id, email=None, username=None, defaults=None):
    defaults = dict(defaults or {})
    cleaned_email = _clean_email(email or defaults.get("email") or (session.get("email") if has_request_context() else None))
    username_seed = normalize_username(username or defaults.get("username") or ((cleaned_email or "user").split("@", 1)[0]))
    if not _username_valid(username_seed):
        username_seed = normalize_username((cleaned_email or "user").split("@", 1)[0])
    if not _username_valid(username_seed):
        username_seed = "user"

    profile = _neon_get_profile_by("auth_user_id", user_id)
    if not profile and cleaned_email:
        profile = _neon_get_profile_by("email", cleaned_email) or _neon_get_profile_by("normalized_email", cleaned_email)
    if profile:
        update_payload = {
            "auth_user_id": user_id,
            "email": cleaned_email or profile.get("email"),
            "normalized_email": cleaned_email or profile.get("normalized_email") or profile.get("email"),
            "username": profile.get("username") or username_seed,
            "display_name": profile.get("display_name") or profile.get("full_name") or username_seed,
            "full_name": profile.get("full_name") or profile.get("display_name") or username_seed,
            "profile_completed": bool(profile.get("profile_completed")),
            "email_verified": bool(profile.get("email_verified")),
            "is_verified": bool(profile.get("is_verified")),
        }
        updated = _neon_update_profile(profile["id"], update_payload)
        return updated or profile, None

    while _neon_get_profile_by("username", username_seed):
        username_seed = _username_suggestions(username_seed)[0]

    minimal_defaults = {
        **defaults,
        "email": cleaned_email,
        "normalized_email": cleaned_email,
        "username": username_seed,
        "username_slug": username_seed,
        "display_name": defaults.get("display_name") or defaults.get("full_name") or username_seed,
        "full_name": defaults.get("full_name") or defaults.get("display_name") or username_seed,
        "bio": defaults.get("bio") or "",
        "phone": defaults.get("phone") or None,
        "normalized_phone": defaults.get("normalized_phone") or None,
        "avatar_url": defaults.get("avatar_url") or None,
        "town": defaults.get("town") or None,
        "region": defaults.get("region") or None,
        "current_location": defaults.get("current_location") or None,
        "country_origin": defaults.get("country_origin") or None,
        "country": defaults.get("country") or None,
        "profile_type": defaults.get("profile_type") or "member",
        "profile_completion": defaults.get("profile_completion") or 0,
        "profile_completed": False,
        "onboarding_step": defaults.get("onboarding_step") or "profile",
        "email_verified": bool(defaults.get("email_verified", False)),
        "is_verified": bool(defaults.get("is_verified", False)),
    }
    return ensure_neon_profile(user_id, minimal_defaults)


def get_current_profile():
    try:
        if not has_request_context():
            print("[profile_service] get_current_profile called without request context")
            return None

        auth_user_id = session.get("auth_user_id") or session.get("user_id")
        profile_id = session.get("profile_id")
        email = session.get("auth_email") or session.get("email")

        if not profile_id and not auth_user_id:
            return None

        # Try to get from session cache first
        profile = session.get("profile_data")
        if profile and isinstance(profile, dict):
            return normalize_profile(profile)

        # Try lightweight lookup first for performance
        if profile_id:
            profile = get_lightweight_profile(profile_id)
            if profile:
                return profile

        # Fallback to full lookup by auth_user_id
        if auth_user_id:
            profile = _neon_get_profile_by("auth_user_id", auth_user_id)
            if profile:
                session["profile_data"] = profile
                return profile

        # Last resort: lookup by email
        if email:
            profile = _neon_get_profile_by("email", email)
            if profile:
                session["profile_data"] = profile
                return profile

        return None
    except Exception as e:
        print(f"[profile_service] get_current_profile error: {e}")
        return None


def get_profile_by_id(profile_id):
    """Get full profile by ID with caching."""
    if not profile_id:
        return None

    cache_key_str = cache_key("profile_full", profile_id, 60, 0)
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached

    try:
        uuid.UUID(str(profile_id))
    except (ValueError, TypeError):
        return None

    profile = _neon_get_profile_by("id", profile_id)
    if profile:
        set_cache(cache_key_str, profile, ttl=60)
    return profile


def get_profile_by_username(username):
    """Get profile by username with caching."""
    if not username:
        return None
    normalized_username = normalize_username(username)
    cache_key_str = cache_key("profile_username", normalized_username or username, 60, 0)
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached

    candidates = []
    for candidate in (username, normalized_username):
        candidate_str = str(candidate or "").strip().lower()
        if candidate_str and candidate_str not in candidates:
            candidates.append(candidate_str)
    if normalized_username:
        if normalized_username.endswith("_user"):
            trimmed = normalized_username[: -len("_user")]
            if trimmed and trimmed not in candidates:
                candidates.append(trimmed)
        else:
            suffixed = f"{normalized_username}_user"
            if suffixed not in candidates:
                candidates.append(suffixed)

    profile = None
    for candidate in candidates:
        profile = _neon_get_profile_by("username", candidate)
        if profile:
            break
    if not profile:
        for candidate in candidates:
            profile = _neon_get_profile_by("username_slug", candidate)
            if profile:
                break
    if not profile:
        try:
            predicates = []
            params = []
            for candidate in candidates:
                predicates.append("lower(split_part(coalesce(email, ''), '@', 1)) = %s")
                params.append(candidate)
            rows = fast_query(
                f"""
                SELECT {_neon_profile_columns()}
                FROM chain_profiles
                WHERE deleted_at IS NULL
                  AND ({' OR '.join(predicates)})
                LIMIT 1
                """,
                params,
                timeout_ms=1200,
                default=[],
            )
            if rows:
                profile = normalize_profile(rows[0])
        except Exception as error:
            print(f"[profile_service] email-local username lookup failed: {error}")
    if profile:
        set_cache(cache_key_str, profile, ttl=60)
    return profile


def get_public_profile_reference(username=None, profile_id=None):
    """Return a lightweight public-profile reference for routing and existence checks.

    This intentionally avoids the broader username fallbacks used by
    get_profile_by_username() so public profile routes can fail fast on a miss
    before any expensive hydration work starts.
    """
    if not username and not profile_id:
        return None

    if profile_id:
        try:
            uuid.UUID(str(profile_id))
        except (ValueError, TypeError):
            return None
        cached, cache_key_str, is_cached = _public_profile_ref_cache_get(profile_id=profile_id)
        if is_cached or cached is not None:
            return cached
        row = _fetch_public_profile_reference(
            "SELECT id, username, display_name, full_name, avatar_url, cover_url, bio, is_verified, verified, is_public, visibility, deleted_at "
            "FROM chain_profiles WHERE id = %s AND deleted_at IS NULL LIMIT 1",
            [profile_id],
            timeout_ms=1200,
        )
        if row:
            ref = normalize_profile(row)
            return _public_profile_ref_cache_store(profile_id=profile_id, profile=ref)
        if cache_key_str:
            _public_profile_ref_cache_store(profile_id=profile_id, missing=True)
        return None

    normalized_username = _normalize_public_profile_handle(username)
    if not normalized_username:
        return None

    cached, cache_key_str, is_cached = _public_profile_ref_cache_get(username=normalized_username)
    if is_cached or cached is not None:
        return cached

    row = _fetch_public_profile_reference(
        "SELECT id, username, display_name, full_name, avatar_url, cover_url, bio, is_verified, verified, is_public, visibility, deleted_at "
        "FROM chain_profiles WHERE deleted_at IS NULL AND username = %s LIMIT 1",
        [normalized_username],
        timeout_ms=1200,
    )

    if row:
        ref = normalize_profile(row)
        return _public_profile_ref_cache_store(username=normalized_username, profile=ref)
    _public_profile_ref_cache_store(username=normalized_username, missing=True)
    return None


def update_profile(profile_id, updates):
    """Update profile and invalidate caches."""
    if not profile_id or not updates:
        return None

    previous = None
    try:
        previous = get_profile_by_id(profile_id)
    except Exception:
        previous = None
    updated = _neon_update_profile(profile_id, updates)
    if updated:
        # Invalidate all profile caches
        delete_cache(cache_key("profile_full", profile_id, 60, 0))
        delete_cache(cache_key("profile_light", profile_id, 60, 0))
        delete_cache(cache_key("profile_username", updated.get("username", ""), 60, 0))
        invalidate_public_profile_reference_cache(
            profile_id=profile_id,
            username=updated.get("username"),
            previous_username=(previous or {}).get("username"),
        )
        if has_request_context():
            session.pop("profile_data", None)
    return updated


def _find_existing_profile(uid=None, profile_id=None, username=None, email=None):
    """Find existing profile by various identifiers."""
    # Try by ID first
    if profile_id:
        profile = _neon_get_profile_by("id", profile_id)
        if profile:
            return profile

    # Try by auth_user_id
    if uid:
        profile = _neon_get_profile_by("auth_user_id", uid)
        if profile:
            return profile

    # Try by email
    if email:
        profile = _neon_get_profile_by("email", email)
        if profile:
            return profile

    # Try by username
    if username:
        profile = _neon_get_profile_by("username", username)
        if profile:
            return profile

    return None


def calculate_completion(profile):
    """Calculate profile completion percentage."""
    if not profile:
        return 0

    fields = [
        "username", "full_name", "bio", "avatar_url", "date_of_birth",
        "phone", "email", "town", "region", "country_origin"
    ]

    filled = sum(1 for field in fields if profile.get(field))
    return int((filled / len(fields)) * 100)


def is_profile_complete(profile):
    """Check if profile meets minimum completion threshold."""
    if not profile:
        return False
    return calculate_completion(profile) >= 55


def get_profile_stats(profile_id):
    """Get aggregated stats for a profile."""
    if not profile_id:
        return {}

    cache_key_str = cache_key("profile_stats", profile_id, 300, 0)
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached

    try:
        stats = {}

        # Follower count
        followers = fast_query(
            "SELECT COUNT(*) as count FROM chain_follows WHERE following_profile_id = %s AND deleted_at IS NULL",
            (profile_id,),
            timeout_ms=1000,
            default=[{"count": 0}]
        )
        stats["followers_count"] = followers[0]["count"] if followers else 0

        # Following count
        following = fast_query(
            "SELECT COUNT(*) as count FROM chain_follows WHERE follower_profile_id = %s AND deleted_at IS NULL",
            (profile_id,),
            timeout_ms=1000,
            default=[{"count": 0}]
        )
        stats["following_count"] = following[0]["count"] if following else 0

        # Posts count
        posts = fast_query(
            "SELECT COUNT(*) as count FROM chain_posts WHERE profile_id = %s AND deleted_at IS NULL",
            (profile_id,),
            timeout_ms=1000,
            default=[{"count": 0}]
        )
        stats["posts_count"] = posts[0]["count"] if posts else 0

        set_cache(cache_key_str, stats, ttl=300)
        return stats
    except Exception as e:
        print(f"[profile_service] get_profile_stats error: {e}")
        return {}


def search_profiles(query, limit=20):
    """Search profiles by username or full_name."""
    if not query or len(query) < 2:
        return []

    cache_key_str = cache_key("profile_search", query, 60, 0)
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached[:limit] if len(cached) > limit else cached

    try:
        results = fast_query(
            """
            SELECT id, username, full_name, avatar_url, is_verified
            FROM chain_profiles
            WHERE (username ILIKE %s OR full_name ILIKE %s)
              AND deleted_at IS NULL
            ORDER BY
                CASE
                    WHEN username = %s THEN 1
                    WHEN username ILIKE %s THEN 2
                    ELSE 3
                END,
                followers_count DESC
            LIMIT %s
            """,
            (f"%{query}%", f"%{query}%", query, f"{query}%", limit),
            timeout_ms=2000,
            default=[]
        )

        set_cache(cache_key_str, results, ttl=60)
        return results
    except Exception as e:
        print(f"[profile_service] search_profiles error: {e}")
        return []


# Re-export friend request functions from friendship_service for backward compatibility
def accept_friend_request(viewer_id, request_id):
    """Re-exported from friendship_service for backward compatibility."""
    from services.friendship_service import accept_friend_request as _accept
    return _accept(request_id, viewer_id)


def decline_friend_request(viewer_id, request_id):
    """Re-exported from social_relationship_service for backward compatibility."""
    from services.social_relationship_service import decline_friend_request as _decline
    return _decline(viewer_id, request_id)


def cancel_friend_request(viewer_id, request_id):
    """Re-exported from social_relationship_service for backward compatibility."""
    from services.social_relationship_service import cancel_friend_request as _cancel
    return _cancel(viewer_id, request_id)


def block_profile(blocker_profile_id, blocked_profile_id):
    """Re-exported from moderation_engine for backward compatibility."""
    from services.moderation_engine import block_profile as _block
    return _block(blocker_profile_id, blocked_profile_id)


def delete_post(post_id, profile_id):
    """Re-exported from post_service for backward compatibility."""
    from services.post_service import delete_post as _delete
    return _delete(post_id, profile_id)


def delete_reel(reel_id, profile_id):
    """Re-exported from reels_engine for backward compatibility."""
    from services.reels_engine import delete_reel as _delete
    return _delete(reel_id, profile_id)


def invalidate_profile_cache(pid):
    """Re-exported from profile_2026_service for backward compatibility."""
    from services.profile_2026_service import invalidate_profile_cache as _invalidate
    result = _invalidate(pid)
    try:
        invalidate_public_profile_reference_cache(profile_id=pid)
    except Exception:
        pass
    return result


def batch_get_profiles(profile_ids):
    """Efficiently fetch multiple profiles at once."""
    if not profile_ids:
        return {}

    # Remove duplicates and invalid IDs before hitting uuid-typed SQL.
    valid_ids = []
    for pid in profile_ids:
        if not pid:
            continue
        try:
            from uuid import UUID
            UUID(str(pid))
        except Exception:
            continue
        valid_ids.append(str(pid))
    valid_ids = list(dict.fromkeys(valid_ids))

    if not valid_ids:
        return {}

    cache_key_str = cache_key("profiles_batch", ",".join(valid_ids[:50]), 60, 0)
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached

    try:
        placeholders = ",".join("%s" for _ in valid_ids)
        rows = fast_query(
            f"SELECT id, username, full_name, avatar_url, is_verified FROM chain_profiles WHERE id IN ({placeholders}) AND deleted_at IS NULL",
            valid_ids,
            timeout_ms=2000,
            default=[]
        )

        result = {row["id"]: row for row in rows}
        set_cache(cache_key_str, result, ttl=60)
        return result
    except Exception as e:
        print(f"[profile_service] batch_get_profiles error: {e}")
        return {}


def get_wallet_snapshot(profile_id):
    """Re-exported from wallet_service for backward compatibility."""
    from services.wallet_service import get_or_create_wallet as _f
    return _f(profile_id)


def get_profile_activity(profile_id):
    """Safe stub: profile activity aggregation not yet implemented."""
    log_warning(
        "profile_activity_disabled",
        operation="get_profile_activity",
        profile_id=profile_id,
    )
    return {"posts": [], "reels": [], "stories": []}


def get_creator_tools(profile_id):
    """Safe stub: creator tools config not yet implemented."""
    log_warning(
        "creator_tools_disabled",
        operation="get_creator_tools",
        profile_id=profile_id,
    )
    return {
        "studio_enabled": False,
        "creator_notes": "",
        "featured_links": [],
    }


def get_profile_counts(profile_id):
    """Return bounded profile counters for bundle builders."""
    profile = get_profile_by_id(profile_id) or {}
    return {
        "posts": safe_int(profile.get("posts_count"), 0),
        "reels": safe_int(profile.get("reels_count"), 0),
        "stories": safe_int(profile.get("stories_count"), 0),
        "followers": safe_int(profile.get("followers_count"), 0),
        "following": safe_int(profile.get("following_count"), 0),
        "friends": safe_int(profile.get("friends_count"), 0),
        "likes": safe_int(profile.get("likes_count") or profile.get("total_likes"), 0),
        "views": safe_int(profile.get("views_count") or profile.get("profile_views"), 0),
    }


def build_profile_strength(profile, stats=None):
    """Return a lightweight completion score for profile surfaces."""
    source_profile = profile or {}
    completion = safe_int(source_profile.get("profile_completion"), 0)
    if not completion:
        completion = calculate_completion(source_profile)
    return completion


def get_mutual_friends_summary(viewer_id, profile_id, limit=6):
    """Provide a small mutual friends payload without expensive fan-out."""
    from services.friend_service import get_mutual_friends as _f

    items = _f(viewer_id, profile_id, limit, 0) if viewer_id and profile_id else []
    return {
        "count": len(items or []),
        "items": items or [],
    }


def get_recently_active_friends(profile_id, limit=6):
    """Best-effort recently active friends placeholder."""
    return []


def get_public_profiles(limit=20, offset=0, exclude_ids=None):
    """Get public profiles for matching/discovery."""
    exclude_ids = exclude_ids or []
    cache_key_str = cache_key("public_profiles", limit, offset, ",".join(exclude_ids[:10]))
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached

    try:
        params = []
        sql = """
            SELECT id, username, full_name, avatar_url, is_verified, bio, location, created_at
            FROM chain_profiles
            WHERE is_public = true AND deleted_at IS NULL
        """
        if exclude_ids:
            placeholders = ",".join("%s" for _ in exclude_ids)
            sql += f" AND id NOT IN ({placeholders})"
            params.extend(exclude_ids)
        sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        results = fast_query(sql, params, timeout_ms=2000, default=[])
        set_cache(cache_key_str, results, ttl=60)
        return results
    except Exception as e:
        print(f"[profile_service] get_public_profiles error: {e}")
        return []


# Backward-compatible stubs for profile_routes imports
# These delegate to the appropriate service modules
def favorite_profile(viewer_id, target_id):
    try:
        execute(
            "INSERT INTO chain_favorites (viewer_id, target_id, created_at) VALUES (%s, %s, NOW()) ON CONFLICT DO NOTHING",
            (viewer_id, target_id)
        )
        return True
    except Exception:
        return False

def follow_profile(follower_id, following_id, toggle=True):
    from services.engagement_service import follow_profile as _f
    return _f(follower_id, following_id, toggle=toggle)

def get_followers_page(profile_id, page=1, per_page=20):
    from services.social_service import list_followers as _f
    cursor = None if page <= 1 else None
    result = _f(profile_id, limit=per_page, cursor=cursor) or {}
    result["total"] = len(result.get("followers", []))
    return result

def get_following_page(profile_id, page=1, per_page=20):
    from services.social_service import list_following as _f
    cursor = None if page <= 1 else None
    result = _f(profile_id, limit=per_page, cursor=cursor) or {}
    result["total"] = len(result.get("following", []))
    return result

def get_following_types(profile_id):
    page = get_following_page(profile_id, page=1, per_page=100) or {}
    items = page.get("following", [])
    counts = {"all": len(items), "users": 0, "creators": 0, "businesses": 0}
    for item in items:
        profile_type = (item.get("profile_type") or "users").lower()
        if profile_type in ("creator", "creators"):
            counts["creators"] += 1
        elif profile_type in ("business", "businesses"):
            counts["businesses"] += 1
        else:
            counts["users"] += 1
    return counts

def get_friend_requests(profile_id, page=1, per_page=20):
    from services.friend_service import list_friend_requests as _f
    cursor = None if page <= 1 else None
    return _f(profile_id, direction="received", limit=per_page, cursor=cursor)

def get_friend_status(profile_id, other_id):
    from services.friendship_service import get_friendship_status as _f
    return _f(profile_id, other_id)

def get_friends(profile_id, page=1, per_page=20):
    from services.friend_service import list_friends as _f
    cursor = None if page <= 1 else None
    result = _f(profile_id, limit=per_page, cursor=cursor) or {}
    result["total"] = len(result.get("friends", []))
    return result

def get_profile_bundle(profile_id=None, viewer_id=None, viewer=None, username=None):
    if viewer_id is None and viewer is not None:
        if isinstance(viewer, dict):
            viewer_id = viewer.get("id")
        else:
            viewer_id = viewer

    profile = None
    if username:
        profile = get_profile_by_username(username)
    elif profile_id:
        profile = get_profile_by_id(profile_id)

    if not profile:
        return {}

    pid = profile.get("id")
    stats = get_profile_stats(pid) or {}
    is_owner = bool(viewer_id and str(viewer_id) == str(pid))

    from services.presence_service import get_presence
    presence = get_presence(pid) or {}

    from services.friend_service import get_mutual_friends
    mutual_friends = get_mutual_friends(viewer_id or pid, pid) if viewer_id else {}

    from services.stories_engine import get_stories_by_creator, get_highlights
    stories = get_stories_by_creator(pid, viewer_id=viewer_id) if pid else []
    highlights = get_highlights(pid, viewer_id=viewer_id) if pid else []

    live_rooms = []
    if pid and neon_table_exists("chain_live_rooms"):
        room_columns = set(get_cached_table_columns("chain_live_rooms", timeout_ms=1500) or [])
        owner_column = None
        for candidate in ("profile_id", "host_profile_id", "host_id", "creator_id"):
            if candidate in room_columns:
                owner_column = candidate
                break
        if owner_column:
            owner_clause = f"(r.{owner_column} = %s)"
            live_rows = fast_query(
                f"""
                SELECT r.id, r.{owner_column} AS owner_profile_id, r.title, r.category, r.is_live, r.status,
                       r.viewer_count, r.cover_url, r.thumbnail_url, r.created_at
                FROM chain_live_rooms r
                WHERE {owner_clause}
                  AND (COALESCE(r.is_live, FALSE) = TRUE OR COALESCE(r.status, '') = 'live')
                ORDER BY COALESCE(r.viewer_count, 0) DESC
                LIMIT 5
                """,
                (pid,),
                timeout_ms=2000,
                default=[],
            ) or []
            live_rooms = [
                {
                    **row,
                    "profile_id": row.get("owner_profile_id") or row.get("profile_id"),
                }
                for row in live_rows
                if row and row.get("id")
            ]

    content = {
        "posts": [],
        "reels": [],
        "rooms": live_rooms,
        "stories": stories,
        "highlights": highlights,
        "mutual_friends": mutual_friends if isinstance(mutual_friends, dict) else {"count": 0, "items": []},
    }

    recently_active = get_recently_active_friends(pid, limit=6) if is_owner else []
    profile_strength = build_profile_strength(profile, stats=stats)
    wallet = (get_wallet_snapshot(pid) or {}) if is_owner else {}
    creator_tools = (get_creator_tools(pid) or {}) if is_owner else {}

    from services.relationship_cache_service import get_relationship_state
    from services.relationship_gate_service import can_message, can_call
    viewer_rel = get_relationship_state(viewer_id or pid, pid) if viewer_id and not is_owner else {}
    actions = [{"can_message": can_message(viewer_id or pid, pid) if viewer_id else False}]

    return {
        "profile": profile,
        "stats": stats,
        "content": content,
        "wallet": wallet,
        "creator_tools": creator_tools,
        "activity": [],
        "actions": actions,
        "presence": presence,
        "mutual_friends": mutual_friends if isinstance(mutual_friends, dict) else {"count": 0, "items": []},
        "profile_strength": profile_strength,
        "recently_active_friends": recently_active,
    }

def get_profile_content(viewer_id, target_id, content_type, page=1, per_page=12):
    from services.profile_2026_service import get_profile_content_section as _f
    return _f(viewer_id, target_id, content_type, page=page, per_page=per_page)

def get_profile_posts(profile_id, viewer_id=None, page=1, per_page=20):
    from services.profile_2026_service import get_profile_content_section as _f
    return _f(viewer_id, profile_id, "posts", page=page, per_page=per_page)

def get_profile_privacy(profile_id):
    if not profile_id:
        return {}
    try:
        from services.neon_service import fast_query
        rows = fast_query(
            "SELECT profile_visibility, show_online_status, show_email, show_phone, "
            "show_location, show_website, who_can_see_posts, who_can_see_reels, "
            "who_can_see_stories, who_can_follow_me, who_can_message_me, who_can_call, "
            "who_can_see_followers, who_can_see_following, who_can_send_friend_requests "
            "FROM chain_profiles WHERE id = %s LIMIT 1",
            (profile_id,),
            timeout_ms=5000,
            default=[],
        )
        if rows:
            return {k: v for k, v in rows[0].items() if v is not None}
        return {}
    except Exception:
        return {}

def get_profile_reels(profile_id, viewer_id=None, page=1, per_page=20):
    from services.profile_2026_service import get_profile_content_section as _f
    return _f(viewer_id, profile_id, "reels", page=page, per_page=per_page)

def get_profile_settings(profile_id):
    if not profile_id:
        return {"settings": {}, "security": {}}
    from services.profile_dashboard_service import _safe_select_if_exists
    settings_row = (_safe_select_if_exists("chain_user_settings", filters={"profile_id": profile_id}, limit=1, order_by=None) or [{}])[0]
    security_row = (_safe_select_if_exists("chain_account_security", filters={"profile_id": profile_id}, limit=1, order_by=None) or [{}])[0]
    return {"settings": settings_row, "security": security_row}

def get_reel_analytics(reel_id, profile_id):
    from services.reels_engine import get_reel_analytics as _f
    return _f(reel_id, profile_id)

def get_sent_friend_requests(profile_id, page=1, per_page=20):
    from services.friend_service import list_friend_requests as _f
    cursor = None if page <= 1 else None
    return _f(profile_id, direction="sent", limit=per_page, cursor=cursor)

def like_profile(actor_id, target_id):
    from services.dating_service import like_profile as _f
    return _f(actor_id, target_id)

def mute_profile(muter_profile_id, muted_profile_id):
    from services.moderation_engine import mute_profile as _f
    return _f(muter_profile_id, muted_profile_id)

def record_profile_view(viewer_id, target_id):
    try:
        execute(
            "INSERT INTO chain_profile_views (viewer_id, target_id, viewed_at) VALUES (%s, %s, NOW()) ON CONFLICT DO NOTHING",
            (viewer_id, target_id)
        )
        return True
    except Exception:
        return False

def remove_follower(profile_id, follower_id):
    from services.social_relationship_service import remove_follower as _f
    return _f(profile_id, follower_id)

def remove_friend(profile_id, friend_id):
    from services.friend_service import remove_friend as _f
    return _f(profile_id, friend_id)

def report_profile(reporter_id, target_id, reason, details=None):
    try:
        from services.moderation_engine import report_entity
        return report_entity(reporter_id, "profile", target_id, reason, details=details, target_profile_id=target_id)
    except Exception:
        return False

def send_friend_request(sender_id, recipient_id, message=None):
    from services.friendship_service import send_friend_request as _f
    return _f(sender_id, recipient_id, message=message)

def toggle_post_comments(post_id, profile_id, enabled):
    try:
        execute(
            "UPDATE chain_posts SET comments_enabled = %s WHERE id = %s AND profile_id = %s",
            (bool(enabled), post_id, profile_id)
        )
        return True
    except Exception:
        return False

def toggle_post_pin(post_id, profile_id, pinned):
    try:
        execute(
            "UPDATE chain_posts SET is_pinned = %s WHERE id = %s AND profile_id = %s",
            (bool(pinned), post_id, profile_id)
        )
        return True
    except Exception:
        return False

def toggle_post_sharing(post_id, profile_id, enabled):
    try:
        execute(
            "UPDATE chain_posts SET sharing_enabled = %s WHERE id = %s AND profile_id = %s",
            (bool(enabled), post_id, profile_id)
        )
        return True
    except Exception:
        return False

def toggle_reel_comments(reel_id, profile_id, enabled):
    try:
        execute(
            "UPDATE chain_reels SET comments_enabled = %s WHERE id = %s AND profile_id = %s",
            (bool(enabled), reel_id, profile_id)
        )
        return True
    except Exception:
        return False

def toggle_reel_pin(reel_id, profile_id, pinned):
    try:
        execute(
            "UPDATE chain_reels SET is_pinned = %s WHERE id = %s AND profile_id = %s",
            (bool(pinned), reel_id, profile_id)
        )
        return True
    except Exception:
        return False

def toggle_reel_sharing(reel_id, profile_id, enabled):
    try:
        execute(
            "UPDATE chain_reels SET sharing_enabled = %s WHERE id = %s AND profile_id = %s",
            (bool(enabled), reel_id, profile_id)
        )
        return True
    except Exception:
        return False

def unmute_profile(unmuter_profile_id, muted_profile_id):
    from services.moderation_engine import unmute_profile as _f
    return _f(unmuter_profile_id, muted_profile_id)

def update_post_visibility(post_id, profile_id, visibility):
    from services.post_service import update_post_visibility as _f
    return _f(post_id, profile_id, visibility)

def update_profile_privacy(profile_id, privacy_settings):
    try:
        import json
        previous = None
        try:
            previous = get_profile_by_id(profile_id)
        except Exception:
            previous = None
        execute(
            "UPDATE chain_profiles SET privacy_settings = %s, updated_at = NOW() WHERE id = %s",
            (json.dumps(privacy_settings) if isinstance(privacy_settings, dict) else privacy_settings, profile_id)
        )
        invalidate_public_profile_reference_cache(profile_id=profile_id, username=(previous or {}).get("username"))
        return True
    except Exception:
        return False

def update_profile_setup(profile_id, setup_data, current_profile=None):
    try:
        allowed = {"display_name", "bio", "location", "website", "avatar_url", "cover_url",
                    "date_of_birth", "gender", "phone", "full_name", "username"}
        updates = {k: v for k, v in setup_data.items() if k in allowed and v is not None}
        if not updates:
            return True, current_profile
        updates["updated_at"] = "NOW()"
        set_clause = ", ".join(f"{k} = %s" for k in updates if k != "updated_at")
        vals = [v for k, v in updates.items() if k != "updated_at"]
        if set_clause:
            execute(
                f"UPDATE chain_profiles SET {set_clause}, updated_at = NOW() WHERE id = %s",
                (*vals, profile_id)
            )
        invalidate_public_profile_reference_cache(
            profile_id=profile_id,
            username=(current_profile or {}).get("username"),
            previous_username=(current_profile or {}).get("previous_username"),
        )
        return True, current_profile
    except Exception as e:
        return False, str(e)

def update_reel_visibility(reel_id, profile_id, visibility):
    from services.reels_engine import update_reel_visibility as _f
    return _f(reel_id, profile_id, visibility)

def upload_profile_avatar(profile_id, file):
    try:
        from services.storage_service import upload_avatar
        url = upload_avatar(profile_id, file)
        if url:
            execute("UPDATE chain_profiles SET avatar_url = %s, updated_at = NOW() WHERE id = %s", (url, profile_id))
        return url
    except Exception:
        return None

def upload_profile_cover(profile_id, file):
    try:
        from services.storage_service import upload_cover
        url = upload_cover(profile_id, file)
        if url:
            execute("UPDATE chain_profiles SET cover_url = %s, updated_at = NOW() WHERE id = %s", (url, profile_id))
        return url
    except Exception:
        return None
