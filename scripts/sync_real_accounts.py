#!/usr/bin/env python3
"""
Phase 167 — Real DB Account Sync

Sync or create real DB/Supabase-backed test users:
  alpha@namvibe.com  (username: alpha_user)
  beta@namvibe.com   (username: beta_user)

Uses Supabase Admin API (service_role) + Neon direct writes.
Does NOT commit credentials — only code/test fixes.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Import app first, BEFORE any services that need request context
# to avoid import lock issues with gevent/Flask
from app import create_app as _create_app

from utils.supabase_client import get_supabase, get_supabase_admin
from gotrue.types import AdminUserAttributes
from services.neon_service import write_query, fast_query
from werkzeug.security import generate_password_hash
from services.auth_service import _remember_dev_registration_credential

PASSWORD = "TestPassword123!"
ALPHA_EMAIL = "alpha@namvibe.com"
BETA_EMAIL = "beta@namvibe.com"
ALPHA_USERNAME = "alpha_user"
BETA_USERNAME = "beta_user"
SECRETS_DIR = ROOT / "secrets"
CREDENTIALS_FILE = SECRETS_DIR / "test_credentials.json"

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  [{name}] {detail}")
    else:
        FAIL += 1
        print(f"  FAIL  [{name}] {detail}")


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def find_supabase_user(email):
    admin = get_supabase_admin()
    try:
        users = admin.auth.admin.list_users()
        for u in users:
            if getattr(u, "email", None) == email:
                return u
    except Exception as e:
        print(f"  Error listing Supabase users: {e}")
    return None


def create_or_update_supabase_user(email, username, full_name):
    existing = find_supabase_user(email)
    if existing:
        uid = getattr(existing, "id", None)
        print(f"  Supabase Auth user exists: {email} (id={uid})")
        try:
            result = get_supabase_admin().auth.admin.update_user_by_id(
                uid,
                AdminUserAttributes(
                    email_confirm=True,
                    password=PASSWORD,
                    user_metadata={
                        "full_name": full_name,
                        "username": username,
                        "email_verified": True,
                    },
                ),
            )
            user = getattr(result, "user", None) or result
            check(f"supabase_update_{email}", bool(getattr(user, "id", None)), str(getattr(user, "id", None)))
            confirmed = getattr(user, "email_confirmed_at", None) or getattr(user, "confirmed_at", None)
            check(f"supabase_confirmed_{email}", bool(confirmed), str(confirmed))
            return getattr(user, "id", None), False
        except Exception as e:
            check(f"supabase_update_{email}", False, str(e))
            return uid, False
    else:
        print(f"  Creating Supabase Auth user: {email}")
        try:
            result = get_supabase_admin().auth.admin.create_user(
                AdminUserAttributes(
                    email=email,
                    password=PASSWORD,
                    email_confirm=True,
                    user_metadata={
                        "full_name": full_name,
                        "username": username,
                        "email_verified": True,
                    },
                    app_metadata={"provider": "email", "providers": ["email"]},
                )
            )
            user = getattr(result, "user", None) or result
            uid = getattr(user, "id", None)
            check(f"supabase_create_{email}", bool(uid), str(uid))
            return uid, True
        except Exception as e:
            check(f"supabase_create_{email}", False, str(e))
            return None, True


def ensure_profile_in_db(email, username, full_name, auth_user_id, is_alpha):
    existing = fast_query(
        "SELECT id, auth_user_id FROM chain_profiles WHERE email = %s LIMIT 1",
        (email,), default=[],
    )
    if existing:
        profile_id = existing[0]["id"]
        current_auth_uid = existing[0]["auth_user_id"]
        print(f"  DB profile exists: {username} (id={profile_id})")
        needs_update = current_auth_uid != auth_user_id
        if needs_update:
            write_query(
                "UPDATE chain_profiles SET auth_user_id = %s, updated_at = %s WHERE id = %s",
                (auth_user_id, _utcnow_iso(), profile_id),
            )
            check(f"db_auth_userid_update_{username}", True, f"updated to {auth_user_id}")
        else:
            check(f"db_auth_userid_{username}", True, "already correct")

        profile_columns = fast_query(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'chain_profiles'",
            default=[],
        )
        cols = {r["column_name"] for r in profile_columns}
        updates = {}
        if "email_verified" in cols:
            updates["email_verified"] = True
        if "profile_completed" in cols:
            updates["profile_completed"] = True
        if "updated_at" in cols:
            updates["updated_at"] = _utcnow_iso()
        if "auth_provider" in cols:
            updates["auth_provider"] = "email"
        if updates:
            assignments = ", ".join(f"{c} = %s" for c in updates)
            write_query(
                f"UPDATE chain_profiles SET {assignments} WHERE id = %s",
                tuple(updates.values()) + (profile_id,),
            )
            check(f"db_profile_updates_{username}", True, f"set {list(updates.keys())}")

        return profile_id, False
    else:
        profile_id = str(uuid.uuid4())
        print(f"  Creating DB profile: {username}")
        try:
            write_query(
                """
                INSERT INTO chain_profiles (
                    id, auth_user_id, username, email, full_name, display_name,
                    auth_provider, email_verified, profile_completed, is_verified,
                    created_at, updated_at, is_public
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE SET
                    email = EXCLUDED.email,
                    auth_user_id = EXCLUDED.auth_user_id,
                    auth_provider = EXCLUDED.auth_provider,
                    updated_at = NOW()
                RETURNING id
                """,
                (
                    profile_id, auth_user_id, username, email, full_name, full_name,
                    "email", True, True, True,
                    _utcnow_iso(), _utcnow_iso(), True,
                ),
            )
            check(f"db_create_{username}", True, profile_id)
            return profile_id, True
        except Exception as e:
            check(f"db_create_{username}", False, str(e))
            existing2 = fast_query(
                "SELECT id FROM chain_profiles WHERE email = %s LIMIT 1",
                (email,), default=[],
            )
            if existing2:
                return existing2[0]["id"], False
            return None, True


def ensure_local_auth_credential(profile_id, username, email):
    try:
        write_query(
            """
            INSERT INTO chain_local_auth_credentials (
                id, profile_id, username, email, password_hash, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (profile_id) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                updated_at = NOW()
            """,
            (
                str(uuid.uuid4()), profile_id, username, email,
                generate_password_hash(PASSWORD),
                _utcnow_iso(), _utcnow_iso(),
            ),
        )
        check(f"local_auth_credential_{username}", True, "password_hash stored")
    except Exception as e:
        check(f"local_auth_credential_{username}", False, str(e))


def save_credentials(email, username, auth_user_id, profile_id, full_name):
    os.makedirs(SECRETS_DIR, exist_ok=True)
    password_hash = generate_password_hash(PASSWORD)
    credentials = {}
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE) as f:
                credentials = json.load(f)
            print(f"  Loaded {len(credentials)} existing credential entries")
        except (json.JSONDecodeError, IOError):
            pass

    profile_dict = {
        "id": str(profile_id),
        "auth_user_id": str(auth_user_id),
        "email": email,
        "username": username,
        "full_name": full_name,
        "display_name": full_name,
    }
    credential = {
        "email": email,
        "username": username,
        "password_hash": password_hash,
        "auth_user_id": str(auth_user_id),
        "profile_id": str(profile_id),
        "full_name": full_name,
        "profile": profile_dict,
    }
    credentials[username] = credential
    credentials[email] = credential

    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(credentials, f, indent=2)
    check(f"save_credentials_{username}", True, f"saved to {CREDENTIALS_FILE}")

    _remember_dev_registration_credential(
        email, username, PASSWORD,
        auth_user_id=str(auth_user_id),
        profile_id=str(profile_id),
        profile=profile_dict,
    )


def verify_login(email):
    app = _create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"

    with app.test_request_context():
        with app.test_client() as _client:
            with _client.session_transaction() as _sess:
                from services.auth_service import login_chain_user
                ok, result = login_chain_user(email, PASSWORD)
                check(f"login_{email}", ok, str(result))
                if ok:
                    _sess.update({
                        "logged_in": True,
                        "auth_user_id": result.get("auth_user_id") if isinstance(result, dict) else None,
                        "auth_email": email,
                        "email": email,
                        "profile_completed": True,
                    })
                return ok


def main():
    global PASS, FAIL
    print("=" * 72)
    print("PHASE 167 — REAL DB ACCOUNT SYNC")
    print("=" * 72)

    print("\n--- Supabase Auth Users ---")
    alpha_uid, alpha_created = create_or_update_supabase_user(
        ALPHA_EMAIL, ALPHA_USERNAME, "Alpha User",
    )
    beta_uid, beta_created = create_or_update_supabase_user(
        BETA_EMAIL, BETA_USERNAME, "Beta User",
    )

    if not alpha_uid or not beta_uid:
        print("\nERROR: Could not create/find Supabase Auth users")
        sys.exit(1)

    print("\n--- Database Profiles ---")
    alpha_pid, _ = ensure_profile_in_db(ALPHA_EMAIL, ALPHA_USERNAME, "Alpha User", alpha_uid, True)
    beta_pid, _ = ensure_profile_in_db(BETA_EMAIL, BETA_USERNAME, "Beta User", beta_uid, False)

    if not alpha_pid or not beta_pid:
        print("\nERROR: Could not ensure DB profiles")
        sys.exit(1)

    print("\n--- Local Auth Credentials ---")
    ensure_local_auth_credential(alpha_pid, ALPHA_USERNAME, ALPHA_EMAIL)
    ensure_local_auth_credential(beta_pid, BETA_USERNAME, BETA_EMAIL)

    print("\n--- Credentials ---")
    save_credentials(ALPHA_EMAIL, ALPHA_USERNAME, alpha_uid, alpha_pid, "Alpha User")
    save_credentials(BETA_EMAIL, BETA_USERNAME, beta_uid, beta_pid, "Beta User")

    print("\n--- Verify Login ---")
    alpha_ok = verify_login(ALPHA_EMAIL)
    beta_ok = verify_login(BETA_EMAIL)

    print(f"\n{'=' * 72}")
    print(f"RESULTS: {PASS} passed, {FAIL} failed")
    if not alpha_ok or not beta_ok:
        print("WARNING: Login verification failed. Tests may use fallback auth.")
    print(f"{'=' * 72}")
    print(f"Accounts synced:")
    print(f"  {ALPHA_EMAIL} / {PASSWORD}")
    print(f"  {BETA_EMAIL} / {PASSWORD}")

    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
