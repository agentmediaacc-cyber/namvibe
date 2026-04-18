import logging
import os
import sys
import uuid

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def supabase_profile_id_for_user(user):
    return uuid.uuid5(uuid.NAMESPACE_URL, f"namvibe:user:{user.pk}")


def _supabase_disabled_for_tests():
    if "test" in sys.argv and os.getenv("SUPABASE_SYNC_IN_TESTS", "").lower() not in {"1", "true", "yes"}:
        return True
    return False


def supabase_is_configured():
    if _supabase_disabled_for_tests():
        return False
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


def _headers(prefer_return=False):
    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer_return:
        headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    return headers


def _profiles_url():
    return f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/profiles"


def supabase_profile_payload(user):
    account_profile = getattr(user, "account_profile", None)
    social_profile = getattr(user, "profile", None)
    full_name = (
        getattr(account_profile, "full_name", "")
        or user.get_full_name()
        or getattr(social_profile, "display_name", "")
        or user.username
    )
    phone = getattr(account_profile, "cellphone_number", "") or None
    return {
        "id": str(supabase_profile_id_for_user(user)),
        "email": (getattr(account_profile, "email", "") or user.email or "").lower(),
        "username": (getattr(social_profile, "username", "") or user.username).lower(),
        "full_name": full_name,
        "phone": phone,
    }


def ensure_supabase_profile(user):
    if not supabase_is_configured():
        if not _supabase_disabled_for_tests():
            logger.warning("Supabase profile sync skipped: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing.")
        return None

    payload = supabase_profile_payload(user)
    if not all(payload.get(field) for field in ("id", "email", "username", "full_name", "phone")):
        logger.warning("Supabase profile sync skipped for user %s: required profile fields are incomplete.", user.pk)
        return None

    try:
        response = requests.post(
            _profiles_url(),
            headers=_headers(prefer_return=True),
            params={"on_conflict": "id"},
            json=payload,
            timeout=15,
        )
        if response.ok:
            rows = response.json()
            return rows[0] if rows else payload

        if response.status_code == 409:
            update_response = requests.patch(
                f"{_profiles_url()}?id=eq.{payload['id']}",
                headers=_headers(prefer_return=True),
                json={
                    "email": payload["email"],
                    "username": payload["username"],
                    "full_name": payload["full_name"],
                    "phone": payload["phone"],
                },
                timeout=15,
            )
            if update_response.ok:
                rows = update_response.json()
                return rows[0] if rows else payload
            logger.warning("Supabase profile update failed for user %s: %s %s", user.pk, update_response.status_code, update_response.text)
            return None

        logger.warning("Supabase profile sync failed for user %s: %s %s", user.pk, response.status_code, response.text)
    except requests.RequestException as exc:
        logger.warning("Supabase profile sync failed for user %s: %s", user.pk, exc)
    return None


def get_supabase_profile(user):
    if not supabase_is_configured():
        return None

    try:
        response = requests.get(
            _profiles_url(),
            headers=_headers(),
            params={
                "select": "*",
                "id": f"eq.{supabase_profile_id_for_user(user)}",
                "limit": "1",
            },
            timeout=15,
        )
        if response.ok:
            rows = response.json()
            return rows[0] if rows else None
        logger.warning("Supabase profile read failed for user %s: %s %s", user.pk, response.status_code, response.text)
    except requests.RequestException as exc:
        logger.warning("Supabase profile read failed for user %s: %s", user.pk, exc)
    return None


def find_supabase_profile(email=None, username=None, phone=None):
    if not supabase_is_configured():
        return None

    filters = []
    if email:
        filters.append(f"email.eq.{email.lower()}")
    if username:
        filters.append(f"username.eq.{username.lower()}")
    if phone:
        filters.append(f"phone.eq.{phone}")
    if not filters:
        return None

    try:
        response = requests.get(
            _profiles_url(),
            headers=_headers(),
            params={
                "select": "*",
                "or": f"({','.join(filters)})",
                "limit": "1",
            },
            timeout=15,
        )
        if response.ok:
            rows = response.json()
            return rows[0] if rows else None
        logger.warning("Supabase profile lookup failed: %s %s", response.status_code, response.text)
    except requests.RequestException as exc:
        logger.warning("Supabase profile lookup failed: %s", exc)
    return None


def sign_in_supabase_auth(email, password):
    if _supabase_disabled_for_tests():
        return None, "not_configured"
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        return None, "not_configured"

    try:
        response = requests.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token",
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Content-Type": "application/json",
            },
            params={"grant_type": "password"},
            json={"email": email, "password": password},
            timeout=15,
        )
        if response.ok:
            return response.json(), None
        return None, response.json().get("error_description") if response.headers.get("content-type", "").startswith("application/json") else response.text
    except requests.RequestException as exc:
        logger.warning("Supabase auth login failed for %s: %s", email, exc)
    return None, "request_failed"
