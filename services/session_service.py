import time
from datetime import datetime, timezone
from flask import session, request, current_app
from services.supabase_safe import safe_select, safe_update
from utils.supabase_client import get_supabase

# Session keys
K_USER_ID = "auth_user_id"
K_EMAIL = "auth_email"
K_PROVIDER = "auth_provider"
K_ACCESS_TOKEN = "access_token"
K_REFRESH_TOKEN = "refresh_token"
K_EXPIRES_AT = "expires_at"
K_PROFILE_ID = "profile_id"
K_USERNAME = "username"
K_FULL_NAME = "full_name"
K_LOGIN_AT = "login_at"
K_REMEMBER = "remember_me"
K_PROFILE_WARNING = "profile_warning"
K_AGE_CHECK_REQUIRED = "age_check_required"
K_PENDING_DATE_OF_BIRTH = "pending_date_of_birth"

def store_auth_session(auth_session, user, profile=None, provider='password', remember=False):
    """
    Store Supabase auth session and user details in Flask session.
    """
    now = int(time.time())
    
    # Supabase session details
    access_token = getattr(auth_session, "access_token", None) if auth_session else None
    refresh_token = getattr(auth_session, "refresh_token", None) if auth_session else None
    expires_in = getattr(auth_session, "expires_in", 3600) if auth_session else 3600
    
    session[K_ACCESS_TOKEN] = access_token
    session[K_REFRESH_TOKEN] = refresh_token
    session[K_EXPIRES_AT] = now + expires_in
    
    # User details
    session[K_USER_ID] = getattr(user, "id", None)
    session[K_EMAIL] = getattr(user, "email", None)
    session[K_PROVIDER] = provider
    session[K_LOGIN_AT] = now
    session[K_REMEMBER] = remember
    
    if remember:
        session.permanent = True
    
    # Profile details
    if profile:
        session[K_PROFILE_ID] = profile.get("id")
        session[K_USERNAME] = profile.get("username")
        session[K_FULL_NAME] = profile.get("full_name") or profile.get("display_name")
        session[K_PROFILE_WARNING] = bool(profile.get("setup_warning"))
    else:
        # Clear profile keys if no profile provided
        session.pop(K_PROFILE_ID, None)
        session.pop(K_USERNAME, None)
        session.pop(K_FULL_NAME, None)
        session.pop(K_PROFILE_WARNING, None)

def get_current_auth_user():
    """
    Get current Supabase auth user using stored access token.
    Attempts refresh if needed.
    """
    token = session.get(K_ACCESS_TOKEN)
    if not token:
        return None
        
    # Check if refresh needed
    expires_at = session.get(K_EXPIRES_AT, 0)
    if expires_at and (expires_at - time.time()) < 300: # Refresh if < 5 mins left
        refresh_supabase_session_if_needed()
        token = session.get(K_ACCESS_TOKEN)
        
    if not token:
        return None
        
    try:
        response = get_supabase().auth.get_user(token)
        return getattr(response, "user", None)
    except Exception:
        # One last try to refresh if get_user failed (token might be invalid)
        if refresh_supabase_session_if_needed():
            token = session.get(K_ACCESS_TOKEN)
            try:
                response = get_supabase().auth.get_user(token)
                return getattr(response, "user", None)
            except Exception:
                pass
        return None

def refresh_supabase_session_if_needed():
    """
    Use refresh token to get a new Supabase session.
    """
    refresh_token = session.get(K_REFRESH_TOKEN)
    if not refresh_token:
        return False
        
    try:
        response = get_supabase().auth.refresh_session(refresh_token)
        user = getattr(response, "user", None)
        auth_session = getattr(response, "session", None)
        
        if user and auth_session:
            # We don't have the profile here easily, but we can keep existing profile keys
            # Or just update the auth-specific keys
            now = int(time.time())
            expires_in = getattr(auth_session, "expires_in", 3600)
            
            session[K_ACCESS_TOKEN] = getattr(auth_session, "access_token", None)
            session[K_REFRESH_TOKEN] = getattr(auth_session, "refresh_token", None)
            session[K_EXPIRES_AT] = now + expires_in
            return True
        else:
            clear_auth_session()
            return False
    except Exception:
        clear_auth_session()
        return False

def clear_auth_session():
    """
    Clear all auth-related keys from the session.
    """
    keys_to_clear = [
        K_USER_ID, K_EMAIL, K_PROVIDER, K_ACCESS_TOKEN, K_REFRESH_TOKEN,
        K_EXPIRES_AT, K_PROFILE_ID, K_USERNAME, K_FULL_NAME, K_LOGIN_AT,
        K_REMEMBER, K_PROFILE_WARNING, K_AGE_CHECK_REQUIRED, K_PENDING_DATE_OF_BIRTH,
        "date_of_birth", "age_verified",
    ]
    for key in keys_to_clear:
        session.pop(key, None)
    session.permanent = False

def is_logged_in():
    """
    Lightweight check if user is logged in.
    """
    return bool(session.get(K_USER_ID) and (session.get(K_ACCESS_TOKEN) or session.get(K_PROFILE_ID)))

def get_current_profile_id():
    return session.get(K_PROFILE_ID)

def get_current_username():
    return session.get(K_USERNAME)
