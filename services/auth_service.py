import random
import re
import threading
from datetime import datetime, timezone
from types import SimpleNamespace

from flask import current_app, request, session

from engines.cache_engine import cache_key, delete_cache, get_cache, set_cache
from engines.performance_engine import clean_email, make_unique_username, normalize_username, profile_completion_score
from services.neon_service import write_query, fast_query, is_circuit_open
from services.supabase_safe import column_safe_payload, safe_count, safe_insert, safe_select, safe_update, table_exists
from utils.supabase_client import get_supabase, get_supabase_admin
from services.session_service import (
    store_auth_session, 
    clear_auth_session, 
    get_current_auth_user, 
    refresh_supabase_session_if_needed,
    K_USER_ID, K_EMAIL, K_PROFILE_ID, K_USERNAME, K_FULL_NAME, K_PROVIDER,
    K_PROFILE_WARNING, K_AGE_CHECK_REQUIRED, K_PENDING_DATE_OF_BIRTH
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
    "avatar_url",
    "oauth_metadata",
    "linked_providers",
    "last_login_at",
    "login_count",
    "profile_completed",
    "onboarding_step",
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


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


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
            taken = bool(safe_select("chain_profiles", columns="id", filters={"username": normalized}, limit=1, order_by=None))
            if taken:
                result = {
                    "available": False,
                    "field": field,
                    "message": "That username is already taken.",
                    "suggestions": username_suggestions(normalized, town=town),
                }

    elif field == "email":
        normalized = clean_email(raw_value)
        taken = bool(safe_select("chain_profiles", columns="id", filters={"normalized_email": normalized}, limit=1, order_by=None))
        if not taken:
            taken = bool(safe_select("chain_profiles", columns="id", filters={"email": normalized}, limit=1, order_by=None))
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
        taken = bool(safe_select("chain_profiles", columns="id", filters={"normalized_phone": normalized}, limit=1, order_by=None))
        if not taken:
            taken = bool(safe_select("chain_profiles", columns="id", filters={"phone": normalized}, limit=1, order_by=None))
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
    rows = safe_select("chain_profiles", columns="id", filters={"username": username}, limit=1, order_by=None)
    return bool(rows)


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
    if table_exists("chain_wallets"):
        existing_wallet = safe_select("chain_wallets", columns="id", filters={"profile_id": profile_id}, limit=1, order_by=None)
        if not existing_wallet:
            safe_insert(
                "chain_wallets",
                {"profile_id": profile_id, "coin_balance": 0, "gift_earnings": 0, "pending_withdrawal": 0, "status": "active"},
                fallback_columns={"profile_id", "coin_balance", "gift_earnings", "pending_withdrawal", "status", "created_at", "updated_at"},
            )
    if table_exists("chain_creator_tools"):
        existing_tools = safe_select("chain_creator_tools", columns="id", filters={"profile_id": profile_id}, limit=1, order_by=None)
        if not existing_tools:
            safe_insert(
                "chain_creator_tools",
                {"profile_id": profile_id, "studio_enabled": False, "monetization_enabled": False, "creator_notes": "", "featured_links": []},
                fallback_columns={"profile_id", "studio_enabled", "monetization_enabled", "creator_notes", "featured_links", "status", "created_at", "updated_at"},
            )
    if table_exists("chain_user_settings"):
        existing_settings = safe_select("chain_user_settings", columns="id", filters={"profile_id": profile_id}, limit=1, order_by=None)
        if not existing_settings:
            safe_insert(
                "chain_user_settings",
                {"profile_id": profile_id, "allow_messages": True, "allow_video_calls": True, "show_online_status": True, "profile_visibility": "public"},
                fallback_columns={"profile_id", "allow_messages", "allow_video_calls", "show_online_status", "profile_visibility", "created_at", "updated_at"},
            )
    if table_exists("chain_account_security"):
        existing_security = safe_select("chain_account_security", columns="id", filters={"profile_id": profile_id}, limit=1, order_by=None)
        if not existing_security:
            safe_insert(
                "chain_account_security",
                {"profile_id": profile_id, "password_set": False, "recovery_enabled": True},
                fallback_columns={"profile_id", "email", "password_set", "recovery_enabled", "created_at", "updated_at"},
            )


def _find_profile_for_user(user):
    from services.profile_service import ensure_neon_profile, get_profile_by_id
    user_id = getattr(user, "id", None)
    email = clean_email(getattr(user, "email", None))
    if user_id:
        ok, profile = ensure_neon_profile(
            user_id,
            {
                "email": email,
                "username": (_metadata_name(user) or email.split("@")[0] if email else "chainuser"),
                "full_name": _metadata_name(user) or email.split("@")[0] if email else "Chain User",
                "display_name": _metadata_name(user) or email.split("@")[0] if email else "Chain User",
                "profile_completed": False,
            },
        )
        if ok and profile:
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
    full_name = (_metadata_name(user) or email.split("@")[0] if email else "Chain User").strip()
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

    ok, synced_or_error = ensure_neon_profile(
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
    
    if not ok:
        print(f"[auth_service] sync_oauth_profile neon ensure failed (continuing): {synced_or_error}")
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
    
    normalized = synced_or_error
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


def _coerce_profile_row(row, user=None):
    if not row:
        return None
    full_name = row.get("full_name") or row.get("display_name") or _metadata_name(user)
    username = row.get("username") or (clean_email(getattr(user, "email", None)) or "chainuser").split("@")[0]
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
        or (email.split("@")[0] if email else "Chain User")
    )
    username = base.get("username") or normalize_username(metadata.get("username") or full_name or "chainuser")
    return {
        "id": base.get("id"),
        "auth_user_id": getattr(user, "id", None),
        "email": email,
        "username": username or "chainuser",
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
            timeout_ms=300,
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


def register_chain_user(email, password, username, full_name, extra=None):
    extra = extra or {}
    email = clean_email(email)
    username = normalize_username(username)
    phone = normalize_phone(extra.get("phone"))
    full_name = (full_name or "").strip()
    dob = extra.get("date_of_birth")
    age = _age_from_date(dob)
    
    if not email or not password or not username or not full_name or not phone or not dob:
        return False, "Please complete all required fields (Name, Email, Username, Phone, Birthday, Password)."
    if age is None or age < 18:
        return False, "CHAIN is only available to users 18 and older."
    if not _username_valid(username):
        return False, "Username must be 3 to 30 characters using lowercase letters, numbers or underscores only."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not extra.get("terms_accepted"):
        return False, "You must agree to the Terms and Privacy Policy."

    if safe_select("chain_profiles", columns="id", filters={"normalized_email": email}, limit=1, order_by=None):
        return False, "EMAIL_EXISTS"
    if _supabase_auth_email_exists(email):
        return False, "EMAIL_EXISTS"
    
    if _profile_exists_by_username(username):
        return False, f"Username is already taken. Try: {', '.join(username_suggestions(username, extra.get('town'))[:3])}"

    if safe_select("chain_profiles", columns="id", filters={"normalized_phone": phone}, limit=1, order_by=None):
        return False, "Phone number is already registered."

    final_username = username
    try:
        auth_res = get_supabase().auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {"data": {"full_name": full_name, "username": final_username}},
            }
        )
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
            return False, "Registration could not be completed. Please try again."
            
        if clean_email(getattr(user, "email", None)) != email:
            print(f"[auth_service.register] email mismatch: expected {email}, got {getattr(user, 'email', 'None')}")
            return False, "Registration failed. Email verification mismatch."

        profile = sync_oauth_profile(user, "password")
        if profile and profile.get("id"):
            from services.profile_service import _neon_update_profile
            # Minimal update for mandatory fields only
            _neon_update_profile(
                profile["id"],
                {
                    "email": email,
                    "phone": phone,
                    "date_of_birth": dob,
                    "country_origin": extra.get("country_origin"),
                    "preferred_language": extra.get("preferred_language"),
                    "town": extra.get("town"),
                    "region": extra.get("region"),
                    "terms_accepted_at": _utcnow_iso(),
                    "privacy_accepted_at": _utcnow_iso(),
                    "onboarding_step": "preferences",
                    "profile_completed": False,
                },
            )

        # Handle case where email confirmation is required
        if not auth_session:
            return True, "Account created. Check your email to confirm your account."

        # If we have a session, log them in immediately
        store_auth_session(auth_session, user, profile, provider="password")
        _log_login_event(profile, user, "password", "success")
        return True, _profile_redirect(profile)
    except Exception as error:
        err_msg = str(error).lower()
        if "user_already_exists" in err_msg or "already registered" in err_msg:
            return False, "EMAIL_EXISTS"
        print(f"[auth_service] register_chain_user failed: {error}")
        return False, "Registration failed. Please try again."


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

    resolved_email = login_id
    if "@" not in login_id:
        username = normalize_username(login_id)
        from services.profile_service import get_profile_by_username
        profile = get_profile_by_username(username)
        if not profile:
            # If Neon is down and they use username, we can't resolve it easily
            if is_circuit_open():
                return False, "Username login is temporarily unavailable. Please use your email."
            return False, "Username not found."
        resolved_email = clean_email(profile.get("email"))

    try:
        auth_res = get_supabase().auth.sign_in_with_password({"email": resolved_email, "password": password})
        user = getattr(auth_res, "user", None)
        auth_session = getattr(auth_res, "session", None)
        
        if not user or not auth_session:
            return False, "Invalid email or password."
        store_auth_session(auth_session, user, None, provider="password", remember=remember)

        profile = _quick_profile_snapshot(user, resolved_email=resolved_email, timeout_ms=300)
        session_profile = _build_session_profile(user, profile=profile)
        missing_profile_data = profile is None
        missing_dob = not session_profile.get("date_of_birth")

        _store_session_profile(session_profile, warning=missing_profile_data or is_circuit_open())
        session[K_AGE_CHECK_REQUIRED] = bool(missing_dob)
        if missing_dob:
            session.pop(K_PENDING_DATE_OF_BIRTH, None)

        from services.profile_service import verify_profile_age
        ok, result = verify_profile_age(session_profile)
        if not ok and result != "REDIRECT_AGE_CHECK":
            clear_auth_session()
            return False, result

        _schedule_profile_sync(user, "password")
        _log_login_event(profile or session_profile, user, "password", "success")
        if session.get(K_AGE_CHECK_REQUIRED):
            return True, "/profile/age-check"
        return True, "/profile/"
    except Exception as error:
        err_msg = str(error).lower()
        if "invalid login credentials" in err_msg:
            return False, "Invalid email or password."
        if "email not confirmed" in err_msg:
            return False, "Email not confirmed. Please check your inbox."
        print(f"[auth_service] login_chain_user failed: {error}")
        return False, "Invalid email or password."


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
