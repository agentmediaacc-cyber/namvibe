import json
import os
import random
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from flask import current_app, has_request_context, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from engines.cache_engine import cache_key, delete_cache, get_cache, set_cache
from engines.performance_engine import clean_email, make_unique_username, normalize_username, profile_completion_score
from services.neon_service import write_query, fast_query, is_circuit_open, get_cached_table_columns, table_exists as neon_table_exists
from services.supabase_safe import column_safe_payload, safe_count, safe_insert, safe_select, safe_update, table_exists
from services.logging_service import log_info, log_warning
from utils.supabase_client import get_supabase, get_supabase_admin
from services.session_service import (
    store_auth_session, 
    clear_auth_session, 
    get_current_auth_user, 
    refresh_supabase_session_if_needed,
    K_USER_ID, K_EMAIL, K_PROFILE_ID, K_USERNAME, K_FULL_NAME, K_PROVIDER,
    K_LOGIN_AT, K_PROFILE_WARNING, K_AGE_CHECK_REQUIRED, K_PENDING_DATE_OF_BIRTH
)


AUTH_PROFILE_COLUMNS = {
    "auth_user_id",
    "auth_provider",
    "provider_user_id",
    "email",
    "phone",
    "normalized_email",
    "normalized_phone",
    "full_name",
    "username",
    "username_slug",
    "date_of_birth",
    "avatar_url",
    "oauth_metadata",
    "linked_providers",
    "last_login_at",
    "login_count",
    "profile_completed",
    "onboarding_step",
    "email_verified",
    "is_verified",
    "password_set",
    "signup_method",
    "terms_accepted",
    "human_confirmed",
    "is_public",
    "profile_type",
    "premium_tier",
    "wallet_balance",
    "created_at",
    "updated_at",
}

LOGIN_PROFILE_FIELD_CANDIDATES = (
    "id",
    "auth_user_id",
    "username",
    "username_slug",
    "handle",
    "email",
    "normalized_email",
    "password_hash",
    "password",
    "password_digest",
    "hashed_password",
    "legacy_password_hash",
    "is_active",
    "is_blocked",
    "login_allowed",
    "profile_completed",
)
_LOGIN_PROFILE_COLUMNS_CACHE = None


def _login_profile_columns():
    global _LOGIN_PROFILE_COLUMNS_CACHE
    if _LOGIN_PROFILE_COLUMNS_CACHE:
        return _LOGIN_PROFILE_COLUMNS_CACHE
    try:
        rows = fast_query(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'chain_profiles'
              AND column_name = ANY(%s)
            """,
            (list(LOGIN_PROFILE_FIELD_CANDIDATES),),
            timeout_ms=800,
            default=[],
        )
        found = {row.get("column_name") for row in rows if row.get("column_name")}
        selected = [column for column in LOGIN_PROFILE_FIELD_CANDIDATES if column in found]
    except Exception:
        selected = ["id", "auth_user_id", "username", "email", "password_hash", "profile_completed"]
    if "id" not in selected:
        selected.insert(0, "id")
    _LOGIN_PROFILE_COLUMNS_CACHE = ", ".join(selected)
    return _LOGIN_PROFILE_COLUMNS_CACHE


_DEV_REGISTRATION_CREDENTIALS = {}


def _load_test_credentials():
    global _DEV_REGISTRATION_CREDENTIALS
    try:
        _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        creds_path = os.path.join(_base, "secrets", "test_credentials.json")
        if os.path.isfile(creds_path):
            with open(creds_path) as f:
                creds = json.load(f)
            for key, val in creds.items():
                if isinstance(val, dict) and val.get("username"):
                    _DEV_REGISTRATION_CREDENTIALS[str(key).lower()] = val
    except Exception:
        pass


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _is_production_env():
    if os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    if os.getenv("FLASK_ENV") != "production":
        return False
    return os.getenv("ENV") == "production"


_load_test_credentials()


def _registration_result(ok=False, dev_fallback=False, profile=None, auth_user_id=None, redirect_to=None, error=None, access_token=None, auth_provider=None):
    return {
        "ok": bool(ok),
        "dev_fallback": bool(dev_fallback),
        "profile": profile,
        "auth_user_id": auth_user_id,
        "redirect_to": redirect_to,
        "error": error,
        "access_token": access_token,
        "auth_provider": auth_provider or ("local_fallback" if dev_fallback else "supabase"),
    }


def _safe_auth_trace(event, **data):
    safe = {}
    for key, value in data.items():
        if key in {"email", "username"} and value:
            safe[key] = str(value)
        elif key.endswith("_exists") or key in {"ok", "dev_fallback"}:
            safe[key] = bool(value)
        elif key in {"redirect_to", "error"}:
            safe[key] = value
        elif value is None:
            safe[key] = None
        else:
            safe[key] = "[set]" if value else None
    print(f"[auth_trace] {event} {safe}")


def _remember_dev_registration_credential(email, username, password, auth_user_id=None, profile_id=None, profile=None):
    if _is_production_env() or not password:
        return
    credential = {
        "email": clean_email(email),
        "username": normalize_username(username),
        "password_hash": generate_password_hash(password),
        "auth_user_id": auth_user_id,
        "profile_id": profile_id,
        "profile": profile,
    }
    for key in {credential.get("email"), credential.get("username"), credential.get("auth_user_id")}:
        if key:
            _DEV_REGISTRATION_CREDENTIALS[str(key).lower()] = credential


def _get_dev_registration_credential(login_id, profile=None):
    if _is_production_env():
        return None
    # Reload from disk if in-memory store is empty (server started before seed)
    loaded_now = False
    if not _DEV_REGISTRATION_CREDENTIALS:
        _load_test_credentials()
        loaded_now = True
    candidates = {str(login_id or "").lower()}
    if profile:
        candidates.update(
            str(value).lower()
            for value in (
                profile.get("email"),
                profile.get("username"),
                profile.get("auth_user_id"),
            )
            if value
        )
    for candidate in candidates:
        credential = _DEV_REGISTRATION_CREDENTIALS.get(candidate)
        if credential:
            return credential
    return None


def _build_local_dev_profile(auth_user_id, email, username, full_name, phone, dob, extra, email_verified=False, save_error=None):
    if _is_production_env():
        return None
    profile = {
        **_registration_profile_payload(
            email,
            username,
            full_name,
            phone,
            dob,
            {**(extra or {}), "auth_user_id": auth_user_id},
            email_verified=email_verified,
        ),
        "id": str(uuid.uuid4()),
        "auth_user_id": auth_user_id,
        "setup_warning": True,
        "dev_profile": True,
        "profile_save_error": str(save_error or ""),
    }
    _safe_auth_trace(
        "local_dev_profile_created",
        auth_user_id=auth_user_id,
        email=email,
        username=username,
        profile_id=profile.get("id"),
        error=str(save_error or ""),
    )
    return profile


def _age_from_date(date_of_birth):
    if not date_of_birth:
        return None
    try:
        dob = datetime.fromisoformat(str(date_of_birth)).date()
    except ValueError:
        return None
    today = datetime.now(timezone.utc).date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def normalize_phone(phone):
    cleaned = "".join(ch for ch in str(phone or "") if ch.isdigit() or ch == "+")
    if cleaned.startswith("00"):
        cleaned = f"+{cleaned[2:]}"
    if cleaned and not cleaned.startswith("+"):
        cleaned = f"+{cleaned}"
    return cleaned or None


def username_suggestions(username, town=None):
    base = normalize_username(username or "chain")
    year_suffix = str(datetime.now(timezone.utc).year)[-2:]
    place = normalize_username(town or "world")
    candidates = [base, f"{base}{random.randint(10, 99)}", f"{base}{place}", f"{base}{year_suffix}"]
    seen = set()
    result = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            result.append(candidate[:30])
    return result[:4]


def _username_valid(username):
    if not re.fullmatch(r"[a-z0-9_]{3,30}", username or ""):
        return False
    return True


def _email_exists_in_profiles(email):
    normalized = clean_email(email)
    if not normalized:
        return False
    try:
        rows = fast_query(
            """
            SELECT id
            FROM chain_profiles
            WHERE lower(coalesce(normalized_email, email, '')) = lower(%s)
               OR lower(coalesce(email, '')) = lower(%s)
            LIMIT 1
            """,
            (normalized, normalized),
            timeout_ms=800,
            default=[],
        )
        if rows:
            return True
    except Exception as error:
        print(f"[auth_service] profile email lookup failed: {error}")
    return bool(safe_select("chain_profiles", columns="id", filters={"normalized_email": normalized}, limit=1, order_by=None))


def _username_exists_in_profiles(username):
    normalized = normalize_username(username)
    if not normalized:
        return False
    try:
        rows = fast_query(
            """
            SELECT id
            FROM chain_profiles
            WHERE lower(coalesce(username, '')) = lower(%s)
               OR lower(coalesce(username_slug, '')) = lower(%s)
            LIMIT 1
            """,
            (normalized, normalized),
            timeout_ms=800,
            default=[],
        )
        if rows:
            return True
    except Exception as error:
        print(f"[auth_service] profile username lookup failed: {error}")
    return bool(safe_select("chain_profiles", columns="id", filters={"username": normalized}, limit=1, order_by=None))


def _phone_exists_in_profiles(phone):
    normalized = normalize_phone(phone)
    if not normalized:
        return False
    collapsed = "".join(ch for ch in normalized if ch.isdigit() or ch == "+")
    try:
        rows = fast_query(
            """
            SELECT id
            FROM chain_profiles
            WHERE regexp_replace(coalesce(normalized_phone, phone, ''), '\\s+', '', 'g') = %s
               OR regexp_replace(coalesce(phone, ''), '\\s+', '', 'g') = %s
            LIMIT 1
            """,
            (collapsed, collapsed),
            timeout_ms=800,
            default=[],
        )
        if rows:
            return True
    except Exception as error:
        print(f"[auth_service] profile phone lookup failed: {error}")
    return bool(safe_select("chain_profiles", columns="id", filters={"normalized_phone": normalized}, limit=1, order_by=None))


def _supabase_auth_email_exists(email):
    normalized = clean_email(email)
    if not normalized:
        return False
    user = get_auth_user_by_email(normalized)
    return user is not None


def get_auth_user_by_email(email):
    """
    Lookup user in Supabase Auth by email using service role.
    """
    normalized = clean_email(email)
    if not normalized:
        return None
    try:
        # Admin list users has limits, but for specific lookup it's better than nothing 
        # if we don't have a direct "get by email" in the community client admin.
        # Note: some versions of supabase-py have auth.admin.list_users()
        admin_client = get_supabase_admin()
        users = admin_client.auth.admin.list_users()
        for user in users:
            if clean_email(getattr(user, "email", None)) == normalized:
                return user
    except Exception as error:
        print(f"[auth_service] get_auth_user_by_email failed: {error}")
    return None


def check_account_availability(field, value, town=None):
    field = (field or "").strip()
    raw_value = (value or "").strip()
    if field not in {"username", "email", "phone"}:
        return {"available": False, "field": field, "message": "Unsupported field.", "suggestions": []}
    if not raw_value:
        return {"available": False, "field": field, "message": "Enter a value first.", "suggestions": []}

    # Optimization: Cache results for 15 seconds
    ckey = cache_key("availability", field, raw_value)
    cached = get_cache(ckey)
    if cached:
        return cached

    # Optimization: If Neon circuit is open, assume available but warn
    if is_circuit_open():
        return {
            "available": True,
            "field": field,
            "message": "We will verify this during signup.",
            "warning": "High traffic mode: verifying availability during submission.",
            "suggestions": []
        }

    result = {"available": True, "field": field, "message": f"{field.title()} is available.", "suggestions": []}

    if field == "username":
        normalized = normalize_username(raw_value)
        if not _username_valid(normalized):
            result = {
                "available": False,
                "field": field,
                "message": "Use 3 to 30 lowercase letters, numbers or underscores only.",
                "suggestions": username_suggestions(normalized or "chain", town=town),
            }
        else:
            taken = _username_exists_in_profiles(normalized)
            if taken:
                result = {
                    "available": False,
                    "field": field,
                    "message": "That username is already taken.",
                    "suggestions": username_suggestions(normalized, town=town),
                }

    elif field == "email":
        normalized = clean_email(raw_value)
        taken = _email_exists_in_profiles(normalized)
        if not taken:
            # Supabase auth lookup can be slow, only do it if not found in profiles
            taken = _supabase_auth_email_exists(normalized)
        if taken:
            result = {
                "available": False,
                "field": field,
                "message": "That email is already in use.",
                "suggestions": [],
            }

    elif field == "phone":
        normalized = normalize_phone(raw_value)
        taken = _phone_exists_in_profiles(normalized)
        if taken:
            result = {
                "available": False,
                "field": field,
                "message": "That phone number is already in use.",
                "suggestions": [],
            }

    set_cache(ckey, result, ttl=15)
    return result


def _base_url():
    configured = current_app.config.get("APP_BASE_URL")
    if configured:
        return configured.rstrip("/")
    return request.url_root.rstrip("/")


def _oauth_redirect_to(provider):
    return f"{_base_url()}/auth/{provider}/callback"


def _provider_user_id(user, provider=None):
    identities = getattr(user, "identities", None) or []
    for identity in identities:
        if provider and identity.provider == provider:
            return identity.id
    metadata = getattr(user, "user_metadata", None) or {}
    return metadata.get("sub") or metadata.get("provider_id") or getattr(user, "id", None)


def _metadata_name(user):
    metadata = getattr(user, "user_metadata", None) or {}
    return (
        metadata.get("full_name")
        or metadata.get("name")
        or metadata.get("user_name")
        or metadata.get("preferred_username")
        or metadata.get("nickname")
    )


def _metadata_avatar(user):
    metadata = getattr(user, "user_metadata", None) or {}
    return metadata.get("avatar_url") or metadata.get("picture")


def _profile_exists_by_username(username):
    from services.profile_service import get_profile_by_username
    if get_profile_by_username(username):
        return True
    return _username_exists_in_profiles(username)


def _find_login_profile(login_id, columns=None):
    """
    Robust profile lookup for login.
    Handles email, username, and handles with/without @.
    Cached 30s to avoid repeated slow lookups.
    """
    raw_login_id = (login_id or "").strip()
    normalized_login_id = raw_login_id.lower()
    if not normalized_login_id:
        return None

    cache_key_str = f"login_profile_lookup:{normalized_login_id}"
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached

    lookup_id = normalized_login_id[1:] if normalized_login_id.startswith("@") else normalized_login_id
    normalized_username = normalize_username(lookup_id)
    is_email = "@" in normalized_login_id
    
    selected_columns = columns or _login_profile_columns()
    profile = None
    auth_user_found = False
    reason = "not_found"

    try:
        available_columns = set(get_cached_table_columns("chain_profiles", timeout_ms=500) or [])
    except Exception:
        available_columns = set(LOGIN_PROFILE_FIELD_CANDIDATES)

    def _select_first(sql_text, params):
        rows = fast_query(sql_text, params, timeout_ms=1000, default=[])
        return rows[0] if rows else None
    
    # 1. Try by email
    if is_email:
        try:
            profile = _select_first(
                f"SELECT {selected_columns} FROM chain_profiles WHERE lower(coalesce(normalized_email, email, '')) = %s OR lower(coalesce(email, '')) = %s LIMIT 1",
                (clean_email(normalized_login_id), clean_email(normalized_login_id)),
            )
        except Exception as error:
            reason = "email_lookup_error"
            print(f"[auth_service] email login profile lookup failed: {error}")
            
    # 2. Try by username/handle
    if not profile:
        try:
            predicates = ["lower(coalesce(username, '')) = %s"]
            params = [lookup_id]
            if normalized_username and normalized_username != lookup_id:
                predicates.append("lower(coalesce(username, '')) = %s")
                params.append(normalized_username)
            if "username_slug" in available_columns:
                predicates.append("lower(coalesce(username_slug, '')) = %s")
                params.append(normalized_username or lookup_id)
            if "handle" in available_columns:
                predicates.append("lower(trim(leading '@' from coalesce(handle, ''))) = %s")
                params.append(lookup_id)
                if normalized_username and normalized_username != lookup_id:
                    predicates.append("lower(trim(leading '@' from coalesce(handle, ''))) = %s")
                    params.append(normalized_username)
            profile = _select_first(
                f"SELECT {selected_columns} FROM chain_profiles WHERE {' OR '.join(predicates)} LIMIT 1",
                tuple(params),
            )
        except Exception as error:
            reason = "username_lookup_error"
            print(f"[auth_service] username login profile lookup failed: {error}")

    # 3. Fallback to safe_select for redundancy
    if not profile:
        if is_email:
            rows = safe_select("chain_profiles", columns=selected_columns, filters={"normalized_email": clean_email(normalized_login_id)}, limit=1)
            if not rows:
                rows = safe_select("chain_profiles", columns=selected_columns, filters={"email": clean_email(normalized_login_id)}, limit=1)
            profile = rows[0] if rows else None
        else:
            rows = safe_select("chain_profiles", columns=selected_columns, filters={"username": lookup_id}, limit=1)
            if not rows:
                rows = safe_select("chain_profiles", columns=selected_columns, filters={"username": normalized_username}, limit=1)
            if not rows and "handle" in available_columns:
                rows = safe_select("chain_profiles", columns=selected_columns, filters={"handle": lookup_id}, limit=1)
            profile = rows[0] if rows else None

    if profile:
        reason = "profile_found"
        auth_user_found = bool(profile.get("auth_user_id"))
        set_cache(cache_key_str, profile, ttl=30)
    elif is_email:
        try:
            auth_user_found = bool(get_auth_user_by_email(normalized_login_id))
            reason = "auth_user_found_profile_missing" if auth_user_found else reason
        except Exception:
            pass

    log_info(
        "login_lookup_debug",
        login_type="email" if is_email else "username",
        neon_profile_found=bool(profile),
        auth_user_found=auth_user_found,
        reason=reason,
    )
             
    return profile


def _ensure_username(candidate, ignore_profile_id=None):
    base = normalize_username(candidate)

    def exists(username):
        rows = safe_select("chain_profiles", columns="id,username", filters={"username": username}, limit=1, order_by=None)
        if not rows:
            return False
        if ignore_profile_id and rows[0].get("id") == ignore_profile_id:
            return False
        return True

    return make_unique_username(base, exists)



def _is_profile_complete(profile):
    if not profile:
        return False
    if profile.get("profile_completed") is not None:
        return bool(profile.get("profile_completed"))
    return profile_completion_score(profile) >= 55


def _log_login_event(profile, user, provider, status="success"):
    if not table_exists("chain_login_events"):
        return
    safe_insert(
        "chain_login_events",
        {
            "profile_id": (profile or {}).get("id"),
            "auth_user_id": getattr(user, "id", None),
            "provider": provider,
            "email": getattr(user, "email", None),
            "ip_address": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": request.headers.get("User-Agent"),
            "status": status,
            "created_at": _utcnow_iso(),
        },
        fallback_columns={"profile_id", "auth_user_id", "provider", "email", "ip_address", "user_agent", "status", "created_at"},
    )


def _ensure_profile_dependencies(profile_id):
    if not profile_id:
        return
    if os.getenv("CHAIN_FAST_LOCAL") == "1":
        try:
            write_query(
                """
                INSERT INTO chain_wallets (profile_id, coin_balance)
                VALUES (%s, 0)
                ON CONFLICT DO NOTHING
                """,
                (profile_id,),
                timeout_ms=800,
            )
        except Exception:
            pass
    else:
        wallet_columns = set(get_cached_table_columns("chain_wallets", timeout_ms=500) or [])
        if wallet_columns:
            try:
                if {"profile_id", "coin_balance", "gift_earnings", "pending_withdrawal", "status"}.issubset(wallet_columns):
                    write_query(
                        """
                        INSERT INTO chain_wallets (profile_id, coin_balance, gift_earnings, pending_withdrawal, status)
                        VALUES (%s, 0, 0, 0, 'active')
                        ON CONFLICT DO NOTHING
                        """,
                        (profile_id,),
                        timeout_ms=800,
                    )
                elif {"profile_id", "coin_balance", "status"}.issubset(wallet_columns):
                    write_query(
                        """
                        INSERT INTO chain_wallets (profile_id, coin_balance, status)
                        VALUES (%s, 0, 'active')
                        ON CONFLICT DO NOTHING
                        """,
                        (profile_id,),
                        timeout_ms=800,
                    )
                elif {"profile_id", "coin_balance"}.issubset(wallet_columns):
                    write_query(
                        """
                        INSERT INTO chain_wallets (profile_id, coin_balance)
                        VALUES (%s, 0)
                        ON CONFLICT DO NOTHING
                        """,
                        (profile_id,),
                        timeout_ms=800,
                    )
            except Exception as error:
                log_warning("auth_profile_wallet_bootstrap_optional_skipped", profile_id=profile_id, error=str(error))
    if table_exists("chain_creator_tools"):
        try:
            write_query(
                """
                INSERT INTO chain_creator_tools (profile_id, studio_enabled, monetization_enabled, creator_notes, featured_links)
                VALUES (%s, FALSE, FALSE, '', '[]'::jsonb)
                ON CONFLICT DO NOTHING
                """,
                (profile_id,),
                timeout_ms=800,
            )
        except Exception as error:
            log_warning("auth_profile_creator_tools_bootstrap_failed", profile_id=profile_id, error=str(error))
    if os.getenv("CHAIN_FAST_LOCAL") != "1":
        settings_columns = set(get_cached_table_columns("chain_user_settings", timeout_ms=500) or [])
        if {"profile_id", "allow_messages", "allow_video_calls", "show_online_status", "profile_visibility"}.issubset(settings_columns):
            try:
                write_query(
                    """
                    INSERT INTO chain_user_settings (profile_id, allow_messages, allow_video_calls, show_online_status, profile_visibility)
                    VALUES (%s, TRUE, TRUE, TRUE, 'public')
                    ON CONFLICT DO NOTHING
                    """,
                    (profile_id,),
                    timeout_ms=800,
                )
            except Exception as error:
                log_warning("auth_profile_settings_bootstrap_optional_skipped", profile_id=profile_id, error=str(error))
        security_columns = set(get_cached_table_columns("chain_account_security", timeout_ms=500) or [])
        if {"profile_id", "password_set", "recovery_enabled"}.issubset(security_columns):
            try:
                write_query(
                    """
                    INSERT INTO chain_account_security (profile_id, password_set, recovery_enabled)
                    VALUES (%s, FALSE, TRUE)
                    ON CONFLICT DO NOTHING
                    """,
                    (profile_id,),
                    timeout_ms=800,
                )
            except Exception as error:
                log_warning("auth_profile_security_bootstrap_optional_skipped", profile_id=profile_id, error=str(error))


def _find_profile_for_user(user):
    from services.profile_service import ensure_profile_for_user
    user_id = getattr(user, "id", None)
    email = clean_email(getattr(user, "email", None))
    if user_id:
        profile, error = ensure_profile_for_user(
            user_id,
            email=email,
            username=_metadata_name(user) or (email.split("@")[0] if email else None),
        )
        if profile:
            return profile
    if email:
        rows = safe_select("chain_profiles", filters={"email": email}, columns="*", limit=1, order_by=None)
        if rows:
            return rows[0]
    return None


from services.neon_service import write_query, fast_query
from services.profile_service import ensure_neon_profile, get_profile_completion, is_profile_complete, is_adult_profile

def sync_oauth_profile(user, provider):
    email = clean_email(getattr(user, "email", None))
    full_name = (_metadata_name(user) or email.split("@")[0] if email else "user").strip()
    avatar_url = _metadata_avatar(user)
    provider_user_id = _provider_user_id(user, provider=provider)
    profile = _find_profile_for_user(user)
    profile_id = (profile or {}).get("id")
    username_seed = (profile or {}).get("username") or email.split("@")[0] if email else full_name
    username = _ensure_username(username_seed, ignore_profile_id=profile_id)
    oauth_metadata = getattr(user, "user_metadata", None) or {}
    
    # Extract DOB from metadata if missing in Neon
    date_of_birth = (profile or {}).get("date_of_birth")
    if not date_of_birth:
        date_of_birth = oauth_metadata.get("date_of_birth") or oauth_metadata.get("dob") or oauth_metadata.get("birthdate")

    existing_count = int((profile or {}).get("login_count") or 0)
    existing_linked = (profile or {}).get("linked_providers") or []
    if isinstance(existing_linked, str):
        existing_linked = [item.strip() for item in existing_linked.split(",") if item.strip()]
    linked_providers = list(dict.fromkeys([*existing_linked, provider]))
    draft_profile = {
        **(profile or {}),
        "full_name": full_name,
        "username": username,
        "avatar_url": avatar_url,
        "date_of_birth": date_of_birth,
    }
    profile_completed = is_profile_complete(draft_profile)

    synced_profile, sync_error = ensure_neon_profile(
        getattr(user, "id", None),
        {
            "email": email,
            "username": username,
            "display_name": full_name,
            "full_name": full_name,
            "profile_completed": profile_completed,
            "profile_type": "member",
            "date_of_birth": date_of_birth,
            "phone": (profile or {}).get("phone"),
            "preferred_language": (profile or {}).get("preferred_language"),
        },
    )
    
    if not synced_profile:
        print(f"[auth_service] sync_oauth_profile neon ensure failed (continuing): {sync_error}")
        # Return best-effort profile from metadata if Neon is down
        return {
            **(profile or {}),
            "id": (profile or {}).get("id"),
            "auth_user_id": getattr(user, "id", None),
            "email": email,
            "username": username,
            "full_name": full_name,
            "display_name": full_name,
            "avatar_url": avatar_url,
            "date_of_birth": date_of_birth,
            "profile_completed": profile_completed,
            "setup_warning": True
        }
    
    normalized = synced_profile
    if normalized:
        from services.profile_service import _neon_update_profile
        login_count = int(normalized.get("login_count") or 0) + 1
        # Use write_query indirectly via _neon_update_profile or directly here
        normalized = _neon_update_profile(
            normalized["id"],
            {
                "email": email,
                "full_name": full_name,
                "display_name": full_name,
                "username": username,
                "avatar_url": avatar_url,
                "last_login_at": _utcnow_iso(),
                "login_count": login_count,
                "onboarding_step": "complete" if profile_completed else (normalized.get("onboarding_step") or "account"),
            },
        ) or normalized
        
    if normalized:
        _ensure_profile_dependencies(normalized["id"])
        delete_cache(cache_key("profile_username", normalized.get("username")))
        delete_cache(cache_key("profile_id", normalized.get("id")))
        delete_cache(cache_key("public_profiles", 20))
    return normalized


def _profile_redirect(profile):
    if not profile:
        return "/profile/onboarding"
    return "/profile/" if _is_profile_complete(profile) else "/profile/onboarding"


def _registration_profile_payload(email, username, full_name, phone, dob, extra, email_verified=False):
    payload = {
        "auth_user_id": extra.get("auth_user_id"),
        "email": email,
        "normalized_email": email,
        "full_name": full_name,
        "display_name": full_name,
        "username": username,
        "username_slug": username,
        "phone": phone,
        "normalized_phone": phone,
        "date_of_birth": dob,
        "country_origin": extra.get("country_origin") or extra.get("country") or None,
        "country_of_birth": extra.get("country_origin") or extra.get("country") or None,
        "country": extra.get("current_country") or extra.get("country") or extra.get("country_origin") or None,
        "current_country": extra.get("current_country") or extra.get("country") or None,
        "current_residential_location": extra.get("current_country") or extra.get("current_location") or extra.get("town") or None,
        "current_location": extra.get("town") or extra.get("current_location") or None,
        "preferred_language": extra.get("preferred_language"),
        "town": extra.get("town"),
        "region": extra.get("region"),
        "terms_accepted": bool(extra.get("terms_accepted")),
        "human_confirmed": bool(extra.get("human_confirmed")),
        "profile_type": extra.get("profile_type") or "member",
        "terms_accepted_at": _utcnow_iso(),
        "privacy_accepted_at": _utcnow_iso(),
        "email_verified": bool(email_verified),
        "is_verified": False,
    }
    pw_hash = extra.get("password_hash")
    if pw_hash:
        payload["password_hash"] = pw_hash
    payload["profile_completion"] = 0
    payload["onboarding_step"] = "profile"
    payload["profile_completed"] = False
    return payload


def _bootstrap_registration_profile(auth_user_id, email, username, full_name, phone, dob, extra, email_verified=False):
    extra = {**(extra or {}), "auth_user_id": auth_user_id}
    from services.profile_service import ensure_profile_for_user

    profile_defaults = {
        **_registration_profile_payload(email, username, full_name, phone, dob, extra, email_verified=email_verified),
        "profile_type": extra.get("profile_type") or "member",
    }
    return ensure_profile_for_user(auth_user_id, email=email, username=username, defaults=profile_defaults)


def _store_login_session(profile, auth_user_id=None):
    pid = profile.get("id")
    auid = profile.get("auth_user_id") or auth_user_id
    email = profile.get("email")
    username = profile.get("username")
    session["logged_in"] = True
    session["profile_id"] = pid
    session["auth_user_id"] = auid
    session["user_id"] = auid
    session["email"] = email
    session["username"] = username
    session.permanent = True
    session.modified = True


def _store_registration_session(user_id, email, profile):
    session[K_USER_ID] = user_id
    session["user_id"] = user_id
    session[K_EMAIL] = email
    session["email"] = email
    session[K_PROVIDER] = "password"
    session[K_LOGIN_AT] = int(datetime.now(timezone.utc).timestamp())
    _store_session_profile(profile, warning=False)
    dob = (profile or {}).get("date_of_birth")
    if dob:
        session[K_PENDING_DATE_OF_BIRTH] = dob
        session["date_of_birth"] = dob
        session["age_verified"] = True
    session[K_AGE_CHECK_REQUIRED] = False
    session["logged_in"] = True
    session.modified = True


def _coerce_profile_row(row, user=None):
    if not row:
        return None
    full_name = row.get("full_name") or row.get("display_name") or _metadata_name(user)
    username = row.get("username") or (clean_email(getattr(user, "email", None)) or "user").split("@")[0]
    return {
        "id": row.get("id"),
        "auth_user_id": row.get("auth_user_id") or getattr(user, "id", None),
        "email": row.get("email") or clean_email(getattr(user, "email", None)),
        "username": username,
        "full_name": full_name or username,
        "display_name": row.get("display_name") or full_name or username,
        "avatar_url": row.get("avatar_url") or _metadata_avatar(user),
        "date_of_birth": row.get("date_of_birth"),
        "profile_completed": row.get("profile_completed"),
    }


def _build_session_profile(user, profile=None):
    email = clean_email(getattr(user, "email", None))
    metadata = getattr(user, "user_metadata", None) or {}
    base = profile or {}
    full_name = (
        base.get("full_name")
        or base.get("display_name")
        or _metadata_name(user)
        or (email.split("@")[0] if email else "user")
    )
    username = base.get("username") or normalize_username(metadata.get("username") or full_name or "user")
    return {
        "id": base.get("id"),
        "auth_user_id": getattr(user, "id", None),
        "email": email,
        "username": username or "user",
        "full_name": full_name,
        "display_name": base.get("display_name") or full_name,
        "avatar_url": base.get("avatar_url") or _metadata_avatar(user),
        "date_of_birth": base.get("date_of_birth") or metadata.get("date_of_birth") or metadata.get("dob") or metadata.get("birthdate"),
        "profile_completed": base.get("profile_completed"),
    }


def _quick_profile_snapshot(user, resolved_email=None, timeout_ms=300):
    if is_circuit_open():
        return None
    auth_user_id = getattr(user, "id", None)
    email = clean_email(resolved_email or getattr(user, "email", None))
    if auth_user_id:
        rows = fast_query(
            """
            SELECT id, auth_user_id, email, username, display_name, full_name, avatar_url, date_of_birth, profile_completed
            FROM chain_profiles
            WHERE auth_user_id = %s AND deleted_at IS NULL
            LIMIT 1
            """,
            (auth_user_id,),
            timeout_ms=timeout_ms,
            default=[],
        )
        profile = _coerce_profile_row(rows[0], user=user) if rows else None
        if profile:
            return profile
    if email:
        rows = fast_query(
            """
            SELECT id, auth_user_id, email, username, display_name, full_name, avatar_url, date_of_birth, profile_completed
            FROM chain_profiles
            WHERE email = %s AND deleted_at IS NULL
            LIMIT 1
            """,
            (email,),
            timeout_ms=timeout_ms,
            default=[],
        )
        return _coerce_profile_row(rows[0], user=user) if rows else None
    return None


def _store_session_profile(profile, warning=False):
    if not profile:
        return
    session[K_PROFILE_ID] = profile.get("id")
    session[K_USERNAME] = profile.get("username")
    session[K_FULL_NAME] = profile.get("full_name") or profile.get("display_name")
    session[K_PROFILE_WARNING] = bool(warning)
    if profile.get("date_of_birth"):
        session[K_PENDING_DATE_OF_BIRTH] = profile.get("date_of_birth")
    if profile.get("email"):
        session["email"] = profile.get("email")
    if profile.get("auth_user_id"):
        session["user_id"] = profile.get("auth_user_id")
    session.modified = True


def _schedule_profile_sync(user, provider):
    payload = {
        "id": getattr(user, "id", None),
        "email": getattr(user, "email", None),
        "provider": provider,
        "user_metadata": getattr(user, "user_metadata", None) or {},
        "identities": [
            {"id": getattr(identity, "id", None), "provider": getattr(identity, "provider", None)}
            for identity in (getattr(user, "identities", None) or [])
        ],
    }

    def _worker():
        try:
            try:
                from services.job_engine import enqueue_job

                enqueue_job("auth_profile_sync", payload, queue_name="default")
                return
            except Exception as error:
                print(f"[auth_service] enqueue profile sync failed, falling back to thread: {error}")

            thread_user = SimpleNamespace(
                id=payload.get("id"),
                email=payload.get("email"),
                user_metadata=payload.get("user_metadata") or {},
                identities=[
                    SimpleNamespace(id=item.get("id"), provider=item.get("provider"))
                    for item in payload.get("identities", [])
                ],
            )
            sync_oauth_profile(thread_user, provider)
        except Exception as error:
            print(f"[auth_service] background profile sync failed: {error}")

    threading.Thread(target=_worker, daemon=True).start()


def best_effort_age_dob_update(profile_id, auth_user_id, dob):
    if not dob:
        return False
    if not profile_id or is_circuit_open():
        return False

    try:
        write_query(
            "UPDATE chain_profiles SET date_of_birth = %s, updated_at = now() WHERE id = %s",
            (dob, profile_id),
            timeout_ms=1000,
        )
        return True
    except Exception as error:
        print(f"[auth_service] best_effort_age_dob_update failed: {error}")
        _schedule_profile_sync(
            SimpleNamespace(
                id=auth_user_id,
                email=session.get(K_EMAIL),
                user_metadata={"date_of_birth": dob, "full_name": session.get(K_FULL_NAME), "username": session.get(K_USERNAME)},
                identities=[],
            ),
            "password",
        )
        return False


def _email_valid_format(email):
    if not email:
        return False
    email = email.strip()
    if " " in email:
        return False
    if "@" not in email:
        return False
    local, at, domain = email.partition("@")
    if not local or not domain:
        return False
    if "." not in domain:
        return False
    if len(local) > 64 or len(domain) > 255 or len(email) > 320:
        return False
    return True


def _log_timing(step, duration):
    if duration > 0.05:
        print(f"[timing] {step}: {duration*1000:.0f} ms")


def _check_email_username_phone_taken(email, username, phone):
    sql = """
        SELECT 'email' AS taken_type FROM chain_profiles WHERE normalized_email = %s
        UNION ALL
        SELECT 'username' AS taken_type FROM chain_profiles WHERE username = %s
        UNION ALL
        SELECT 'phone' AS taken_type FROM chain_profiles WHERE normalized_phone = %s AND %s IS NOT NULL
        LIMIT 1
    """
    try:
        results = fast_query(sql, (email, username, phone, phone), timeout_ms=1000)
        if results:
            first = results[0]
            taken_type = first.get("taken_type") if isinstance(first, dict) else first[0]
            if taken_type == "email":
                return "EMAIL_EXISTS"
            elif taken_type == "username":
                suggestions = username_suggestions(username, None)
                return f"Username is already taken. Try: {', '.join(suggestions[:3])}"
            elif taken_type == "phone":
                return "Phone number is already registered."
    except Exception:
        pass
    return None


def _local_registration_network_fallback(email, password, username, full_name, phone, dob, extra, error):
    if _is_production_env():
        return None
    auth_user_id = str(uuid.uuid4())
    extra = {**(extra or {}), "password_hash": generate_password_hash(password)}
    profile, profile_error = _bootstrap_registration_profile(
        auth_user_id,
        email,
        username,
        full_name,
        phone,
        dob,
        extra,
        email_verified=False,
    )
    if not profile:
        profile = _build_local_dev_profile(
            auth_user_id,
            email,
            username,
            full_name,
            phone,
            dob,
            extra,
            email_verified=False,
            save_error=profile_error or error,
        )
    if not profile:
        return None
    _remember_dev_registration_credential(
        email,
        username,
        password,
        auth_user_id=auth_user_id,
        profile_id=profile.get("id"),
        profile=profile,
    )
    log_warning(
        "auth_register_local_network_fallback",
        auth_user_id=auth_user_id,
        email=email,
        error=str(error),
    )
    return _registration_result(
        ok=True,
        dev_fallback=True,
        profile=profile,
        auth_user_id=auth_user_id,
        redirect_to="/profile/",
        auth_provider="local_fallback",
    )


def _allow_local_registration_fallback():
    is_prod = os.getenv("FLASK_ENV") == "production"
    explicit_allow = os.getenv("ALLOW_LOCAL_AUTH_FALLBACK", "").lower() in ("1", "true", "yes")

    if is_prod and not explicit_allow:
        return False

    if explicit_allow:
        log_warning("auth_local_fallback", reason="explicit_allow", env=os.getenv("FLASK_ENV", "unknown"))
        return True

    if os.getenv("CHAIN_FAST_LOCAL") == "1":
        log_warning("auth_local_fallback", reason="chain_fast_local", env=os.getenv("FLASK_ENV", "unknown"))
        return True
    if os.getenv("CHAIN_AUTH_EMAIL_OPTIONAL") == "1":
        log_warning("auth_local_fallback", reason="email_optional", env=os.getenv("FLASK_ENV", "unknown"))
        return True
    if not is_prod:
        log_warning("auth_local_fallback", reason="non_production_env", env=os.getenv("FLASK_ENV", "unknown"))
        return True
    if has_request_context():
        ua = (request.headers.get("User-Agent") or "").lower()
        if any(x in ua for x in ("android", "capacitor", "wv", "namvibe")):
            log_warning("auth_local_fallback", reason="client_ua", ua=ua[:60], env="production")
            return True
        host = request.host.split(":")[0]
        if host.startswith("127.0.0.1") or host.startswith("192.168."):
            log_warning("auth_local_fallback", reason="local_host", host=host, env="production")
            return True
    return False


def register_chain_user(email, password, username, full_name, extra=None):
    extra = extra or {}
    raw_email = email
    email = clean_email(email)
    display_seed = (full_name or username or (email.split("@", 1)[0] if email else "")).strip()
    username = normalize_username(username or display_seed or (email.split("@", 1)[0] if email else "user"))
    raw_phone = str(extra.get("phone") or "").strip()
    phone_code = str(extra.get("phone_code") or "").strip()
    phone = normalize_phone(raw_phone if raw_phone.startswith("+") else f"{phone_code}{raw_phone}")
    full_name = (full_name or display_seed or username).strip()
    dob = extra.get("date_of_birth")
    country_origin = (extra.get("country_origin") or extra.get("country") or "").strip()
    current_country = (extra.get("current_country") or extra.get("country") or "").strip()
    region = (extra.get("region") or "").strip()
    town = (extra.get("town") or "").strip()
    
    if has_request_context():
        try:
            log_warning(
                "auth_register_apk_input",
                user_agent=request.headers.get("User-Agent", ""),
                host=request.host,
                form_email_received=str(raw_email or "").strip(),
                normalized_email=email,
                csrf_valid=bool(extra.get("csrf_valid", True)),
                auth_provider_used="pending",
            )
        except Exception:
            pass

    if not email or not password or not username:
        return _registration_result(error="Enter a name or username, email, and password.")
    if not _email_valid_format(email):
        return _registration_result(error="Please enter a valid email address.")
    if not _username_valid(username):
        return _registration_result(error="Username must be 3 to 30 characters using lowercase letters, numbers or underscores only.")
    if len(password) < 8:
        return _registration_result(error="Password must be at least 8 characters.")
    if not extra.get("terms_accepted"):
        return _registration_result(error="You must accept the terms before creating your account.")

    local_email_valid = _email_valid_format(email)
    registration_result_debug = {
        "local_email_valid": local_email_valid,
        "supabase_attempted": False,
        "supabase_rejected_valid_email": False,
        "fallback_used": False,
        "profile_created": False,
        "redirect_to": None,
    }

    def _finish_local_registration(reason):
        auth_user_id = str(uuid.uuid4())
        pw_extra = {**(extra or {}), "password_hash": generate_password_hash(password), "phone": phone, "date_of_birth": dob}
        profile, profile_error = _bootstrap_registration_profile(
            auth_user_id, email, final_username, full_name, phone, dob,
            pw_extra, email_verified=False,
        )
        if not profile or not profile.get("id"):
            profile = _build_local_dev_profile(
                auth_user_id, email, final_username, full_name, phone, dob,
                pw_extra, email_verified=False,
                save_error=profile_error or f"finish_local_registration:{reason}",
            )
        if not profile or not profile.get("id"):
            return _registration_result(error="Your account could not be created yet.")
        _remember_dev_registration_credential(
            email, final_username, password,
            auth_user_id=auth_user_id, profile_id=profile.get("id"), profile=profile,
        )
        _store_registration_session(auth_user_id, email, profile)
        session["logged_in"] = True
        session.modified = True
        registration_result_debug["fallback_used"] = True
        registration_result_debug["profile_created"] = True
        registration_result_debug["redirect_to"] = "/profile/"
        print(f"[registration_result_debug fallback={reason}] {registration_result_debug}")
        return _registration_result(
            ok=True, dev_fallback=True, profile=profile,
            auth_user_id=auth_user_id, redirect_to="/profile/",
            auth_provider="local_fallback",
        )

    _start = time.time()
    taken_result = _check_email_username_phone_taken(email, username, phone if phone else None)
    _log_timing("register_chain_user.duplicate_check", time.time() - _start)
    if taken_result == "EMAIL_EXISTS":
        return _registration_result(error="EMAIL_EXISTS")
    elif taken_result and taken_result.startswith("Username"):
        return _registration_result(error=taken_result)
    elif taken_result:
        return _registration_result(error=taken_result)

    final_username = username
    _auth_timings = {}
    _supabase_start = time.time()
    registration_result_debug["supabase_attempted"] = True
    auth_res = None
    # --- Supabase sign_up with 10s timeout ---
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutureTimeout
    _supa_exec = ThreadPoolExecutor(max_workers=1)
    try:
        _supa_future = _supa_exec.submit(
            get_supabase().auth.sign_up,
            {
                "email": email,
                "password": password,
                "options": {
                        "data": {
                            "full_name": full_name,
                            "username": final_username,
                        }
                },
            }
        )
        auth_res = _supa_future.result(timeout=10)
        _auth_timings["supabase_ms"] = round((time.time() - _supabase_start) * 1000, 1)
        print(f"[auth_service.register] supabase sign_up completed in {_auth_timings['supabase_ms']}ms")
    except _FutureTimeout:
        _auth_timings["supabase_ms"] = round((time.time() - _supabase_start) * 1000, 1)
        _supa_future.cancel()
        print(f"[auth_service.register] supabase sign_up TIMED OUT after {_auth_timings['supabase_ms']}ms")
        if local_email_valid and _allow_local_registration_fallback():
            return _finish_local_registration("supabase_handshake_timeout")
        return _registration_result(error="Registration service is temporarily unreachable. Please try again.")
    except Exception as _supa_err:
        _auth_timings["supabase_ms"] = round((time.time() - _supabase_start) * 1000, 1)
        _err_msg = str(_supa_err).lower()
        print(f"[auth_service.register] supabase sign_up FAILED after {_auth_timings['supabase_ms']}ms: {_err_msg[:120]}")
        if "rate limit" in _err_msg or "rate_limit" in _err_msg:
            if local_email_valid and _allow_local_registration_fallback():
                return _finish_local_registration("supabase_rate_limited")
            return _registration_result(error="Registration email service is temporarily rate limited. Please try again later.")
        if "user_already_exists" in _err_msg or "already registered" in _err_msg:
            if local_email_valid and _allow_local_registration_fallback():
                return _finish_local_registration("supabase_failed_already_exists")
            return _registration_result(error="EMAIL_EXISTS")
        if "email invalid" in _err_msg or ("email" in _err_msg and "invalid" in _err_msg):
            if local_email_valid and _allow_local_registration_fallback():
                return _finish_local_registration("supabase_failed_email_invalid")
            return _registration_result(error="Registration service is temporarily unavailable. Please try again later.")
        if local_email_valid and _allow_local_registration_fallback():
            return _finish_local_registration("supabase_async_failed")
        return _registration_result(error=f"Registration failed: {_supa_err}")
    finally:
        _supa_exec.shutdown(wait=False)
    _log_timing("register_chain_user.supabase_sign_up", _auth_timings.get("supabase_ms", 0) / 1000.0)

    try:
        _start = time.time()
        user = getattr(auth_res, "user", None)
        auth_session = getattr(auth_res, "session", None)
        
        # Diagnostic logging (Safe)
        print(f"[auth_service.register] signup result: has_user={bool(user)}, user_id={getattr(user, 'id', 'None')}, has_session={bool(auth_session)}")
        
        # Fallback verification if signup response is weak but no exception occurred
        if not user or not getattr(user, "id", None):
            print(f"[auth_service.register] weak signup response for {email}, checking admin fallback...")
            user = get_auth_user_by_email(email)
            if user:
                print(f"[auth_service.register] fallback found user_id={user.id}")
            else:
                print(f"[auth_service.register] fallback NOT found for {email}")

        # Final Truth Validation
        if not user or not getattr(user, "id", None):
            if local_email_valid and _allow_local_registration_fallback():
                return _finish_local_registration("supabase_failed_no_user")
            return _registration_result(error="Registration could not be completed. Please try again.")
            
        if clean_email(getattr(user, "email", None)) != email:
            print(f"[auth_service.register] email mismatch: expected {email}, got {getattr(user, 'email', 'None')}")
            if local_email_valid and _allow_local_registration_fallback():
                return _finish_local_registration("supabase_failed_email_mismatch")
            return _registration_result(error="Registration failed. Please try again.")

        auth_user_id = getattr(user, "id", None)
        email_verified = bool(getattr(user, "email_confirmed_at", None) or getattr(user, "confirmed_at", None))
        _start = time.time()
        profile, profile_error = _bootstrap_registration_profile(
            auth_user_id,
            email,
            final_username,
            full_name,
            phone,
            dob,
            extra,
            email_verified=email_verified,
        )
        _log_timing("register_chain_user.profile_bootstrap", time.time() - _start)
        if not profile or not profile.get("id"):
            log_warning("auth_register_profile_bootstrap_failed", auth_user_id=auth_user_id, email=email, error=profile_error)
            dev_profile = _build_local_dev_profile(
                auth_user_id,
                email,
                final_username,
                full_name,
                phone,
                dob,
                {**extra, "password_hash": generate_password_hash(password)},
                email_verified=email_verified,
                save_error=profile_error,
            )
            if not dev_profile:
                return _registration_result(error="Your account was created, but your profile could not be saved yet. Please try logging in.")
            _remember_dev_registration_credential(
                email,
                final_username,
                password,
                auth_user_id=auth_user_id,
                profile_id=dev_profile.get("id"),
                profile=dev_profile,
            )
            registration_result_debug["profile_created"] = True
            registration_result_debug["redirect_to"] = "/profile/"
            print(f"[registration_result_debug] {registration_result_debug}")
            return _registration_result(
                ok=True,
                dev_fallback=True,
                profile=dev_profile,
                auth_user_id=auth_user_id,
                redirect_to="/profile/",
                auth_provider="local_fallback",
            )
        threading.Thread(target=_ensure_profile_dependencies, args=(profile.get("id"),), daemon=True).start()
        _remember_dev_registration_credential(
            email,
            final_username,
            password,
            auth_user_id=auth_user_id,
            profile_id=profile.get("id"),
            profile=profile,
        )

        # Handle case where email confirmation is required
        if not auth_session:
            registration_result_debug["profile_created"] = True
            registration_result_debug["redirect_to"] = "/profile/"
            print(f"[registration_result_debug] {registration_result_debug}")
            return _registration_result(
                ok=True,
                profile=profile,
                auth_user_id=auth_user_id,
                redirect_to="/profile/",
                access_token=None,
            )

        # If we have a session, log them in immediately
        _start = time.time()
        store_auth_session(auth_session, user, profile, provider="password")
        _log_timing("register_chain_user.store_session", time.time() - _start)
        _log_login_event(profile, user, "password", "success")
        registration_result_debug["profile_created"] = True
        registration_result_debug["redirect_to"] = "/profile/"
        print(f"[registration_result_debug] {registration_result_debug}")
        return _registration_result(
            ok=True,
            profile=profile,
            auth_user_id=auth_user_id,
            redirect_to="/profile/",
            access_token=getattr(auth_session, "access_token", None),
        )
    except Exception as error:
        err_msg = str(error).lower()
        if "user_already_exists" in err_msg or "already registered" in err_msg:
            if local_email_valid and _allow_local_registration_fallback():
                return _finish_local_registration("supabase_failed_already_exists")
            return _registration_result(error="EMAIL_EXISTS")
        if "email rate limit" in err_msg:
            if local_email_valid and _allow_local_registration_fallback():
                return _finish_local_registration("supabase_failed_rate_limited")
            if _is_production_env():
                log_warning("auth_register_email_rate_limited", email=email)
                return _registration_result(error="Email service is temporarily rate limited. Please try again later.")

            auth_user_id = None
            try:
                fallback_user = get_auth_user_by_email(email)
                auth_user_id = getattr(fallback_user, "id", None)
            except Exception as lookup_error:
                log_warning("auth_register_email_rate_limited_lookup_failed", email=email, error=str(lookup_error))

            if not auth_user_id:
                auth_user_id = str(uuid.uuid4())

            extra = {**(extra or {}), "password_hash": generate_password_hash(password)}
            profile, profile_error = _bootstrap_registration_profile(
                auth_user_id,
                email,
                final_username,
                full_name,
                phone,
                dob,
                extra,
                email_verified=False,
            )
            if not profile:
                log_warning("auth_register_email_rate_limited_dev_fallback_failed", email=email, error=profile_error)
                dev_profile = _build_local_dev_profile(
                    auth_user_id,
                    email,
                    final_username,
                    full_name,
                    phone,
                    dob,
                    extra,
                    email_verified=False,
                    save_error=profile_error,
                )
                if not dev_profile:
                    return _registration_result(error="Your account was created, but your profile could not be saved yet. Please try logging in.")
                _remember_dev_registration_credential(
                    email,
                    final_username,
                    password,
                    auth_user_id=auth_user_id,
                    profile_id=dev_profile.get("id"),
                    profile=dev_profile,
                )
                registration_result_debug["fallback_used"] = True
                registration_result_debug["profile_created"] = True
                registration_result_debug["redirect_to"] = "/profile/"
                print(f"[registration_result_debug] {registration_result_debug}")
                return _registration_result(
                    ok=True,
                    dev_fallback=True,
                    profile=dev_profile,
                    auth_user_id=auth_user_id,
                    redirect_to="/profile/",
                )
            threading.Thread(target=_ensure_profile_dependencies, args=(profile.get("id"),), daemon=True).start()
            _remember_dev_registration_credential(
                email,
                final_username,
                password,
                auth_user_id=auth_user_id,
                profile_id=profile.get("id"),
                profile=profile,
            )

            log_warning(
                "auth_register_email_rate_limited_dev_fallback",
                auth_user_id=auth_user_id,
                profile_id=profile.get("id"),
                email=email,
            )
            registration_result_debug["fallback_used"] = True
            registration_result_debug["profile_created"] = True
            registration_result_debug["redirect_to"] = "/profile/"
            print(f"[registration_result_debug] {registration_result_debug}")
            return _registration_result(
                ok=True,
                dev_fallback=True,
                profile=profile,
                auth_user_id=auth_user_id,
                redirect_to="/profile/",
                auth_provider="local_fallback",
            )
        if any(fragment in err_msg for fragment in ("nodename nor servname", "name or service not known", "temporary failure in name resolution", "failed to establish a new connection", "connection refused")):
            if _allow_local_registration_fallback():
                return _finish_local_registration("supabase_failed_network")
            fallback = _local_registration_network_fallback(email, password, final_username, full_name, phone, dob, extra, error)
            if fallback:
                registration_result_debug["fallback_used"] = True
                registration_result_debug["profile_created"] = bool(fallback.get("profile"))
                registration_result_debug["redirect_to"] = fallback.get("redirect_to")
                print(f"[registration_result_debug] {registration_result_debug}")
                return fallback
        if "email invalid" in err_msg or "invalid email" in err_msg or ("email" in err_msg and "invalid" in err_msg):
            log_warning(
                "auth_register_supabase_email_invalid",
                email=email,
                local_email_valid=local_email_valid,
                error=str(error),
            )
            if local_email_valid:
                # Supabase says invalid but our regex says valid → use local fallback
                if _allow_local_registration_fallback():
                    return _finish_local_registration("supabase_failed_email_invalid")
                fallback = _local_registration_network_fallback(email, password, final_username, full_name, phone, dob, extra, error)
                if fallback:
                    registration_result_debug["fallback_used"] = True
                    registration_result_debug["profile_created"] = bool(fallback.get("profile"))
                    registration_result_debug["redirect_to"] = fallback.get("redirect_to")
                    print(f"[registration_result_debug] {registration_result_debug}")
                    return fallback
                # As a last resort, build local dev profile directly (avoids "invalid email" error)
                if not _is_production_env():
                    auth_user_id = str(uuid.uuid4())
                    profile = _build_local_dev_profile(auth_user_id, email, final_username, full_name, phone, dob, {**extra, "password_hash": generate_password_hash(password)}, email_verified=False, save_error=str(error))
                    if profile:
                        _remember_dev_registration_credential(email, final_username, password, auth_user_id=auth_user_id, profile_id=profile.get("id"), profile=profile)
                        registration_result_debug["fallback_used"] = True
                        registration_result_debug["profile_created"] = True
                        registration_result_debug["redirect_to"] = "/profile/"
                        print(f"[registration_result_debug] {registration_result_debug}")
                        return _registration_result(ok=True, dev_fallback=True, profile=profile, auth_user_id=auth_user_id, redirect_to="/profile/", auth_provider="local_fallback")
                # In production, never say "invalid email" when email IS valid locally
                registration_result_debug["supabase_rejected_valid_email"] = True
                print(f"[registration_result_debug] {registration_result_debug}")
                return _registration_result(error="Registration is temporarily unavailable. Please try again later.")
            else:
                # Email is truly malformed locally too
                print(f"[registration_result_debug] {registration_result_debug}")
                return _registration_result(error="Please enter a valid email address.")
        if local_email_valid and _allow_local_registration_fallback():
            return _finish_local_registration("supabase_failed_generic")
        print(f"[auth_service] register_chain_user failed: {error}")
        return _registration_result(error=f"Registration failed: {error}")

    # Final safety net (should never reach here during normal flow)
    if local_email_valid and _allow_local_registration_fallback():
        return _finish_local_registration("final_safety_net")
    return _registration_result(error="Registration could not be completed.")


def _dev_credential_profile(credential):
    """Reconstruct a minimal profile dict from a dev credential.
    Handles both 'profile' key format and legacy field-only format."""
    if not credential:
        return None
    profile = credential.get("profile")
    if profile and profile.get("id") and profile.get("auth_user_id"):
        return profile
    pid = credential.get("profile_id")
    auth_uid = credential.get("auth_user_id")
    email = credential.get("email")
    username = credential.get("username")
    full_name = credential.get("full_name")
    if pid and auth_uid:
        return {
            "id": str(pid),
            "auth_user_id": str(auth_uid),
            "email": email or "",
            "username": username or "",
            "full_name": full_name or username or "",
            "display_name": full_name or username or "",
        }
    return None


def _get_local_auth_credential(profile):
    if not profile or not profile.get("id"):
        return None
    try:
        if not neon_table_exists("chain_local_auth_credentials"):
            return None
        rows = fast_query(
            """
            SELECT profile_id, username, email, password_hash
            FROM chain_local_auth_credentials
            WHERE profile_id = %s
            LIMIT 1
            """,
            (profile.get("id"),),
            timeout_ms=1000,
            default=[],
        )
        return rows[0] if rows else None
    except Exception as error:
        log_warning("local_auth_credential_lookup_failed", profile_id=profile.get("id"), error=str(error))
        return None


def _mark_local_auth_used(profile_id):
    if not profile_id:
        return
    try:
        write_query(
            "UPDATE chain_local_auth_credentials SET last_used_at = now(), updated_at = now() WHERE profile_id = %s",
            (profile_id,),
            timeout_ms=1000,
        )
    except Exception as error:
        log_warning("local_auth_last_used_update_failed", profile_id=profile_id, error=str(error))


def login_chain_user(email, password=None, remember=False):
    if isinstance(email, dict):
        payload = email
        login_id = (payload.get("login_id") or "").strip().lower()
        password = payload.get("password")
        remember = bool(payload.get("remember_me"))
    else:
        login_id = (email or "").strip().lower()

    if not login_id or not password:
        return False, "Enter your email or username and password."

    login_id = login_id[1:] if login_id.startswith("@") and "@" not in login_id[1:] else login_id
    resolved_email = clean_email(login_id) if "@" in login_id else login_id
    login_profile = None
    dev_credential = _get_dev_registration_credential(login_id)

    login_result_debug = {
        "profile_found": False,
        "password_checked": False,
        "supabase_attempted": False,
        "local_fallback_attempted": False,
        "success": False,
        "redirect_to": None,
        "local_auth_table_checked": False,
        "local_auth_found": False,
        "local_auth_success": False,
    }

    # --- 1. Account lookup ---
    if "@" in login_id:
        login_profile = _find_login_profile(login_id)
    else:
        username = normalize_username(login_id)
        dev_profile = _dev_credential_profile(dev_credential) if dev_credential else None
        if dev_profile and dev_profile.get("email"):
            login_profile = dev_profile
            resolved_email = clean_email(dev_profile.get("email"))
        else:
            login_profile = _find_login_profile(username)
        if not login_profile:
            if is_circuit_open():
                return False, "Username login is temporarily unavailable. Please use your email."
            login_result_debug["state"] = "account_not_found"
            print(f"[login_result_debug] {login_result_debug}")
            return False, "Account not found."
        else:
            resolved_email = clean_email(login_profile.get("email"))
        if not resolved_email:
            login_result_debug["state"] = "account_not_found"
            print(f"[login_result_debug] {login_result_debug}")
            return False, "Account not found."

    # --- 2. Check local password hash (all possible columns) ---
    def _get_password_hash(profile):
        for col in ("password_hash", "password", "password_digest", "hashed_password", "legacy_password_hash"):
            val = profile.get(col)
            if val:
                return val
        return None

    login_result_debug["profile_found"] = bool(login_profile)
    login_result_debug["password_checked"] = True
    password_hash = _get_password_hash(login_profile) if login_profile else None
    login_result_debug["verifier_available"] = bool(password_hash)

    if password_hash and check_password_hash(password_hash, password):
        _store_login_session(login_profile, auth_user_id=login_profile.get("auth_user_id"))
        login_result_debug["state"] = "login_success"
        login_result_debug["success"] = True
        login_result_debug["redirect_to"] = "/profile/"
        print(f"[login_result_debug] {login_result_debug}")
        return True, "/profile/"

    local_auth_credential = None

    def _check_local_auth_table():
        nonlocal local_auth_credential
        if not login_profile or password_hash:
            return None
        login_result_debug["local_auth_table_checked"] = True
        if local_auth_credential is None:
            local_auth_credential = _get_local_auth_credential(login_profile)
        login_result_debug["local_auth_found"] = bool(local_auth_credential)
        local_hash = (local_auth_credential or {}).get("password_hash") or ""
        if local_hash and check_password_hash(local_hash, password):
            _store_login_session(login_profile, auth_user_id=login_profile.get("auth_user_id"))
            _mark_local_auth_used(login_profile.get("id"))
            login_result_debug["local_auth_success"] = True
            login_result_debug["state"] = "login_success"
            login_result_debug["success"] = True
            login_result_debug["redirect_to"] = "/profile/"
            print(f"[login_result_debug] {login_result_debug}")
            return True
        login_result_debug["local_auth_success"] = False
        return False if local_auth_credential else None

    local_auth_result = _check_local_auth_table()
    if local_auth_result is True:
        return True, "/profile/"

    # --- 3. Check dev credential (in-memory) before Supabase ---
    if dev_credential and check_password_hash(dev_credential.get("password_hash", ""), password):
        profile = login_profile or _dev_credential_profile(dev_credential)
        if profile and profile.get("auth_user_id"):
            _store_login_session(profile, auth_user_id=profile.get("auth_user_id"))
            login_result_debug["state"] = "login_success"
            login_result_debug["success"] = True
            login_result_debug["redirect_to"] = "/profile/"
            print(f"[login_result_debug] {login_result_debug}")
            return True, "/profile/"

    # --- 4. Try Supabase auth ---
    try:
        login_result_debug["supabase_attempted"] = True
        auth_res = get_supabase().auth.sign_in_with_password({"email": resolved_email, "password": password})
        user = getattr(auth_res, "user", None)
        auth_session = getattr(auth_res, "session", None)

        if not user or not auth_session:
            login_result_debug["state"] = "supabase_auth_failed"
            print(f"[login_result_debug] {login_result_debug}")
            return False, "Password is incorrect, or this account needs password reset."

        store_auth_session(auth_session, user, None, provider="password", remember=remember)

        profile = _quick_profile_snapshot(user, resolved_email=resolved_email, timeout_ms=300) or login_profile
        from services.profile_service import ensure_profile_for_user
        ensured_profile, ensure_error = ensure_profile_for_user(
            getattr(user, "id", None),
            email=resolved_email,
            username=(profile or {}).get("username") or resolved_email.split("@", 1)[0],
        )
        if ensured_profile:
            profile = ensured_profile
        elif ensure_error:
            log_warning("auth_login_profile_ensure_failed", email=resolved_email, error=ensure_error)
        session_profile = _build_session_profile(user, profile=profile)
        missing_profile_data = profile is None
        missing_dob = not session_profile.get("date_of_birth")

        _store_session_profile(session_profile, warning=missing_profile_data or is_circuit_open())
        if session_profile.get("date_of_birth"):
            session[K_PENDING_DATE_OF_BIRTH] = session_profile.get("date_of_birth")
            session["date_of_birth"] = session_profile.get("date_of_birth")
            session["age_verified"] = True
        session[K_AGE_CHECK_REQUIRED] = False
        if missing_dob:
            session.pop(K_PENDING_DATE_OF_BIRTH, None)

        _store_login_session(session_profile or profile or login_profile, auth_user_id=getattr(user, "id", None))
        _schedule_profile_sync(user, "password")
        _log_login_event(profile or session_profile, user, "password", "success")
        login_result_debug["state"] = "login_success"
        login_result_debug["success"] = True
        login_result_debug["redirect_to"] = "/profile/"
        print(f"[login_result_debug] {login_result_debug}")
        return True, "/profile/"

    except Exception as error:
        err_msg = str(error).lower()

        # --- 5a. Invalid login credentials (Supabase) ---
        if "invalid login credentials" in err_msg:
            login_result_debug["local_fallback_attempted"] = True
            if password_hash and check_password_hash(password_hash, password):
                _store_login_session(login_profile, auth_user_id=login_profile.get("auth_user_id"))
                login_result_debug["state"] = "login_success"
                login_result_debug["success"] = True
                login_result_debug["redirect_to"] = "/profile/"
                print(f"[login_result_debug] {login_result_debug}")
                return True, "/profile/"
            if dev_credential and check_password_hash(dev_credential.get("password_hash", ""), password):
                profile = login_profile or _find_login_profile(resolved_email) or _dev_credential_profile(dev_credential)
                if profile and profile.get("auth_user_id"):
                    _store_login_session(profile, auth_user_id=profile.get("auth_user_id"))
                    login_result_debug["state"] = "login_success"
                    login_result_debug["success"] = True
                    login_result_debug["redirect_to"] = "/profile/"
                    print(f"[login_result_debug] {login_result_debug}")
                    return True, "/profile/"
            if login_profile is None and "@" in login_id:
                login_profile = _find_login_profile(resolved_email)
            local_auth_result = _check_local_auth_table()
            if local_auth_result is True:
                return True, "/profile/"
            login_result_debug["state"] = "password_invalid"
            print(f"[login_result_debug] {login_result_debug}")
            if login_profile and not _get_password_hash(login_profile):
                if local_auth_result is None:
                    login_result_debug["state"] = "password_reset_required"
                    print(f"[login_result_debug] {login_result_debug}")
                    return False, "This account needs password reset."
                else:
                    login_result_debug["state"] = "password_invalid"
                    print(f"[login_result_debug] {login_result_debug}")
                    return False, "Password is incorrect."
            return False, "Password is incorrect." if login_profile else "Account not found."

        # --- 5b. Email not confirmed ---
        if "email not confirmed" in err_msg:
            profile = login_profile or _find_login_profile(resolved_email) or _dev_credential_profile(dev_credential)
            if profile and profile.get("auth_user_id"):
                _store_login_session(profile, auth_user_id=profile.get("auth_user_id"))
                login_result_debug["state"] = "login_success"
                login_result_debug["success"] = True
                login_result_debug["redirect_to"] = "/profile/"
                print(f"[login_result_debug] {login_result_debug}")
                return True, "/profile/"
            login_result_debug["state"] = "account_not_found"
            print(f"[login_result_debug] {login_result_debug}")
            return False, "Account not found."

        # --- 5c. Other errors ---
        login_result_debug["local_fallback_attempted"] = True
        print(f"[auth_service] login_chain_user failed: {error}")
        if password_hash and check_password_hash(password_hash, password):
            _store_login_session(login_profile, auth_user_id=login_profile.get("auth_user_id"))
            login_result_debug["state"] = "login_success"
            login_result_debug["success"] = True
            login_result_debug["redirect_to"] = "/profile/"
            print(f"[login_result_debug] {login_result_debug}")
            return True, "/profile/"
        if dev_credential and check_password_hash(dev_credential.get("password_hash", ""), password):
            profile = login_profile or _find_login_profile(resolved_email) or _dev_credential_profile(dev_credential)
            if profile and profile.get("auth_user_id"):
                _store_login_session(profile, auth_user_id=profile.get("auth_user_id"))
                login_result_debug["state"] = "login_success"
                login_result_debug["success"] = True
                login_result_debug["redirect_to"] = "/profile/"
                print(f"[login_result_debug] {login_result_debug}")
                return True, "/profile/"
        local_auth_result = _check_local_auth_table()
        if local_auth_result is True:
            return True, "/profile/"
        if local_auth_result is None and login_profile and not _get_password_hash(login_profile):
            login_result_debug["state"] = "password_reset_required"
            print(f"[login_result_debug] {login_result_debug}")
            return False, "This account needs password reset."
        login_result_debug["state"] = "password_invalid" if login_profile else "account_not_found"
        print(f"[login_result_debug] {login_result_debug}")
        return False, "Password is incorrect, or this account needs password reset." if login_profile else "Account not found."


def get_oauth_url(provider):
    redirect_to = f"{_base_url()}/auth/{provider}/callback"
    print(f"[auth_service] oauth provider={provider} redirect_to={redirect_to}")

    try:
        response = get_supabase().auth.sign_in_with_oauth(
            {
                "provider": provider,
                "options": {
                    "redirect_to": redirect_to,
                },
            }
        )

        print("[auth_service] OAuth raw response:", response)
        print("[auth_service] OAuth response type:", type(response))

        # New supabase-py style
        url = getattr(response, "url", None)
        if url:
            return url

        # Dict style
        if isinstance(response, dict):
            url = response.get("url")
            if url:
                return url
            data = response.get("data")
            if isinstance(data, dict) and data.get("url"):
                return data.get("url")

        # Nested data object style
        data = getattr(response, "data", None)
        if data:
            url = getattr(data, "url", None)
            if url:
                return url
            if isinstance(data, dict) and data.get("url"):
                return data.get("url")

        print("[auth_service] No OAuth URL found in response")
        return None

    except Exception as error:
        print(f"[auth_service] get_oauth_url failed for {provider}: {error}")
        return None


def handle_oauth_callback(provider, request_args, mode="login"):
    try:
        if request_args.get("error_description") or request_args.get("error"):
            return False, request_args.get("error_description") or "OAuth login failed."

        code = request_args.get("code") or request_args.get("auth_code")
        if not code:
            return False, "Missing OAuth authorization code."

        auth_res = get_supabase().auth.exchange_code_for_session({"auth_code": code})
        user = getattr(auth_res, "user", None)
        auth_session = getattr(auth_res, "session", None)
        if not user or not auth_session:
            return False, "OAuth login could not be completed."

        email = clean_email(getattr(user, "email", None))
        
        # Mode-based checks
        if mode == "login":
            # Check if user exists in Neon or Supabase Auth already
            existing_profile = _find_profile_for_user(user)
            if not existing_profile:
                # If we are in login mode but no profile exists, redirect to signup
                return False, "OAUTH_SIGNUP_REQUIRED"

        profile = sync_oauth_profile(user, provider)
        store_auth_session(auth_session, user, profile, provider=provider)
        
        if profile:
            from services.profile_service import verify_profile_age
            ok, result = verify_profile_age(profile)
            if not ok:
                if result == "REDIRECT_AGE_CHECK":
                    session["age_check_required"] = True
                    return True, "/profile/age-check"
                # If explicit underage
                clear_auth_session()
                return False, result

        _log_login_event(profile, user, provider, "success")
        return True, _profile_redirect(profile)
    except Exception as error:
        print(f"[auth_service] handle_oauth_callback failed for {provider}: {error}")
        return False, "OAuth login failed. Please try again."


def get_current_user():
    return get_current_auth_user()


def get_current_profile():
    from services.profile_service import get_current_profile as _get_current_profile
    return _get_current_profile()


def logout_chain_user():
    try:
        token = session.get("access_token")
        if token:
            try:
                get_supabase().auth.sign_out()
            except Exception:
                pass
    finally:
        clear_auth_session()
    return True


def refresh_chain_session():
    return refresh_supabase_session_if_needed()


def resend_confirmation_email(email):
    email = clean_email(email)
    if not email or "@" not in email:
        return False, "Enter a valid email address."
    try:
        get_supabase().auth.resend({"type": "signup", "email": email})
        return True, "Confirmation email sent. Please check your inbox."
    except Exception as error:
        print(f"[auth_service] resend_confirmation_email failed: {error}")
        return True, "If an account exists for this email, a confirmation link has been sent."


def send_password_reset(email):
    email = clean_email(email)
    if not email or "@" not in email:
        return False, "Enter a valid email address."
    try:
        # We always redirect to /auth/callback which will then route to /auth/reset-password
        # This allows us to handle both query params and hash fragments centrally
        redirect_url = f"{_base_url()}/auth/callback"
        get_supabase().auth.reset_password_for_email(email, {"redirect_to": redirect_url})
        return True, "If this email exists, password reset instructions have been sent."
    except Exception as error:
        print(f"[auth_service] send_password_reset failed: {error}")
        # Always return generic success for security
        return True, "If this email exists, password reset instructions have been sent."


def verify_recovery_token(request_args):
    """
    Verify a recovery token or code from Supabase.
    Supports both 'code' and 'token_hash' (PKCE and Implicit).
    """
    code = request_args.get("code")
    token_hash = request_args.get("token_hash")
    type_param = request_args.get("type")
    
    if not code and not token_hash:
        return False, "Missing recovery token."
        
    try:
        client = get_supabase()
        if code:
            auth_res = client.auth.exchange_code_for_session({"auth_code": code})
        elif token_hash and type_param == "recovery":
            auth_res = client.auth.verify_otp({"token_hash": token_hash, "type": "recovery"})
        else:
            return False, "Invalid recovery parameters."
            
        user = getattr(auth_res, "user", None)
        auth_session = getattr(auth_res, "session", None)
        
        if not user or not auth_session:
            return False, "Recovery link is invalid or has expired."
            
        profile = sync_oauth_profile(user, "recovery")
        from services.session_service import store_auth_session
        store_auth_session(auth_session, user, profile, provider="recovery")
        return True, profile
    except Exception as e:
        print(f"[auth_service] verify_recovery_token failed: {e}")
        return False, "Recovery link could not be verified or has expired."


def update_password_from_recovery(new_password):
    """
    Updates password using the current recovery session.
    """
    return set_current_user_password(new_password)


def update_current_user_password(new_password):
    """
    Alias for set_current_user_password as requested.
    """
    return set_current_user_password(new_password)


def set_current_user_password(new_password):
    """
    Updates the password for the current user in Supabase and local DB.
    Requires an active access_token in the session (standard or recovery).
    """
    profile = get_current_profile()
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    
    if not access_token:
        print("[auth_service.set_current_user_password] update failed: no access token in session")
        return False, "Session expired or invalid. Please request a new reset link."

    try:
        client = get_supabase()
        # Ensure the client is using the current session tokens
        client.auth.set_session(access_token, refresh_token or "")
        
        # 1. Update in Supabase Auth
        res = client.auth.update_user({"password": new_password})
        if not getattr(res, "user", None):
            print(f"[auth_service.set_current_user_password] Supabase update returned no user: {res}")
            return False, "Failed to update password in authentication system."
        
        # 2. Update local Profile status
        if profile:
            safe_update(
                "chain_profiles",
                {"password_set": True, "updated_at": _utcnow_iso()},
                eq={"id": profile["id"]},
                fallback_columns=AUTH_PROFILE_COLUMNS,
            )
            
            # 3. Update local Account Security log
            if table_exists("chain_account_security"):
                existing = safe_select("chain_account_security", columns="id", filters={"profile_id": profile["id"]}, limit=1, order_by=None)
                payload = {
                    "profile_id": profile["id"],
                    "email": profile.get("email"),
                    "password_set": True,
                    "last_password_change": _utcnow_iso(),
                    "recovery_enabled": True,
                    "updated_at": _utcnow_iso(),
                }
                if existing:
                    safe_update(
                        "chain_account_security",
                        payload,
                        eq={"id": existing[0]["id"]},
                        fallback_columns={"profile_id", "email", "password_set", "last_password_change", "recovery_enabled", "updated_at"},
                    )
                else:
                    safe_insert(
                        "chain_account_security",
                        {**payload, "created_at": _utcnow_iso()},
                        fallback_columns={"profile_id", "email", "password_set", "last_password_change", "recovery_enabled", "created_at", "updated_at"},
                    )
        
        return True, "Password updated successfully. You can now log in."
    except Exception as error:
        print(f"[auth_service] set_current_user_password failed: {error}")
        return False, "Password update failed. Your reset link may have expired or is invalid."
