import json
import os
import sys
import uuid
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_service import write_query, fast_query


TEST_USERS = [
    {
        "username": "chain_star",
        "email": "chain_star@chain.local",
        "full_name": "Chain Star",
        "bio": "The star of Chain — premium socialite.",
        "is_verified": True,
        "premium_tier": "premium",
    },
    {
        "username": "chain_moon",
        "email": "chain_moon@chain.local",
        "full_name": "Chain Moon",
        "bio": "Moonlight dreamer on Chain.",
        "is_verified": True,
        "premium_tier": None,
    },
    {
        "username": "chain_gold",
        "email": "chain_gold@chain.local",
        "full_name": "Chain Gold",
        "bio": "Golden member of Chain community.",
        "is_verified": True,
        "premium_tier": "gold",
    },
    {
        "username": "chain_million",
        "email": "chain_million@chain.local",
        "full_name": "Chain Million",
        "bio": "Living the million-coin lifestyle.",
        "is_verified": True,
        "premium_tier": "premium",
    },
    {
        "username": "chain_premium",
        "email": "chain_premium@chain.local",
        "full_name": "Chain Premium",
        "bio": "Premium power user on Chain.",
        "is_verified": True,
        "premium_tier": "premium",
    },
]

PASSWORD = "Adimintest"
SECRETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "secrets")
CREDENTIALS_FILE = os.path.join(SECRETS_DIR, "test_credentials.json")


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def upsert_test_user(user_info):
    username = user_info["username"]
    email = user_info["email"]

    existing = fast_query(
        "SELECT id, auth_user_id FROM chain_profiles WHERE username = %s OR email = %s LIMIT 1",
        (username, email), default=[]
    )

    if existing:
        profile_id = existing[0]["id"]
        auth_user_id = existing[0]["auth_user_id"]
        print(f"  Profile already exists: {username} (id={profile_id})")
        return profile_id, auth_user_id, False

    auth_user_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())

    profile_columns = [
        "id", "auth_user_id", "username", "email", "normalized_email",
        "full_name", "display_name", "bio",
        "is_verified", "is_online", "profile_completed",
        "created_at", "updated_at", "is_creator",
    ]
    profile_values = [
        profile_id, auth_user_id, username, email, email.lower().strip(),
        user_info["full_name"], user_info["full_name"],
        user_info["bio"], user_info["is_verified"], False, True,
        _utcnow_iso(), _utcnow_iso(), False,
    ]
    cols_str = ", ".join(profile_columns)
    placeholders = ", ".join("%s" for _ in profile_columns)
    try:
        write_query(
            f"INSERT INTO chain_profiles ({cols_str}) VALUES ({placeholders})",
            tuple(profile_values)
        )
    except Exception as exc:
        # Idempotent: if duplicate key (fast_query timed out), re-fetch
        recheck = fast_query(
            "SELECT id, auth_user_id FROM chain_profiles WHERE username = %s OR email = %s LIMIT 1",
            (username, email), default=[]
        )
        if recheck:
            profile_id = recheck[0]["id"]
            auth_user_id = recheck[0]["auth_user_id"]
            print(f"  Profile already exists (retry): {username} (id={profile_id})")
            return profile_id, auth_user_id, False
        print(f"  ERROR creating {username}: {exc}")
        raise

    if user_info.get("premium_tier"):
        try:
            write_query(
                "UPDATE chain_profiles SET is_premium = TRUE WHERE id = %s",
                (profile_id,)
            )
        except Exception:
            pass

    print(f"  Created profile: {username} (id={profile_id}, auth={auth_user_id})")
    return profile_id, auth_user_id, True


def seed_mutual_follows(profiles):
    usernames = list(profiles.keys())
    star_id = profiles["chain_star"]

    for username, pid in profiles.items():
        if username == "chain_star":
            continue
        existing = fast_query(
            "SELECT id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s LIMIT 1",
            (star_id, pid), default=[]
        )
        if not existing:
            try:
                write_query(
                    "INSERT INTO chain_follows (id, follower_profile_id, following_profile_id, created_at) VALUES (%s, %s, %s, %s)",
                    (str(uuid.uuid4()), star_id, pid, _utcnow_iso())
                )
            except Exception:
                pass
        existing = fast_query(
            "SELECT id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s LIMIT 1",
            (pid, star_id), default=[]
        )
        if not existing:
            try:
                write_query(
                    "INSERT INTO chain_follows (id, follower_profile_id, following_profile_id, created_at) VALUES (%s, %s, %s, %s)",
                    (str(uuid.uuid4()), pid, star_id, _utcnow_iso())
                )
            except Exception:
                pass

    for i, (u1, pid1) in enumerate(profiles.items()):
        for j, (u2, pid2) in enumerate(profiles.items()):
            if i >= j or u1 == "chain_star" or u2 == "chain_star":
                continue
            existing = fast_query(
                "SELECT id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s LIMIT 1",
                (pid1, pid2), default=[]
            )
            if not existing:
                try:
                    write_query(
                        "INSERT INTO chain_follows (id, follower_profile_id, following_profile_id, created_at) VALUES (%s, %s, %s, %s)",
                        (str(uuid.uuid4()), pid1, pid2, _utcnow_iso())
                    )
                except Exception:
                    pass
            existing = fast_query(
                "SELECT id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s LIMIT 1",
                (pid2, pid1), default=[]
            )
            if not existing:
                try:
                    write_query(
                        "INSERT INTO chain_follows (id, follower_profile_id, following_profile_id, created_at) VALUES (%s, %s, %s, %s)",
                        (str(uuid.uuid4()), pid2, pid1, _utcnow_iso())
                    )
                except Exception:
                    pass

    print(f"  Seeded mutual follows for {len(profiles)} users (star follows all, all follow back)")


def save_credentials(profiles, auth_user_ids):
    os.makedirs(SECRETS_DIR, exist_ok=True)
    password_hash = generate_password_hash(PASSWORD)
    # Merge with existing credentials so users not found via DB keep their hashes
    credentials = {}
    if os.path.isfile(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE) as f:
                credentials = json.load(f)
        except (json.JSONDecodeError, IOError):
            credentials = {}
    for user_info in TEST_USERS:
        username = user_info["username"]
        pid = profiles.get(username)
        auth_uid = auth_user_ids.get(username)
        if pid and auth_uid:
            profile_dict = {
                "id": str(pid),
                "auth_user_id": str(auth_uid),
                "email": user_info["email"],
                "username": username,
                "full_name": user_info["full_name"],
                "display_name": user_info["full_name"],
            }
            credential = {
                "email": user_info["email"],
                "username": username,
                "password_hash": password_hash,
                "auth_user_id": str(auth_uid),
                "profile_id": str(pid),
                "full_name": user_info["full_name"],
                "profile": profile_dict,
            }
            credentials[username] = credential
            credentials[user_info["email"]] = credential

    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(credentials, f, indent=2)
    print(f"  Saved {len(credentials)} credential entries to {CREDENTIALS_FILE}")

    # Print diagnostic info (Task 6)
    print()
    print("=== Credential Diagnostics ===")
    print(f"  Auth source:         chain_profiles (Neon) + dev credential fallback (local)")
    print(f"  Supabase Auth:       NOT used — password verified via werkzeug hash on dev fallback")
    for user_info in TEST_USERS:
        username = user_info["username"]
        pid = profiles.get(username)
        auth_uid = auth_user_ids.get(username)
        status = "OK" if pid and auth_uid else "MISSING"
        print(f"  [{status}] {username:20s}  pid={str(pid)[:8]}...  auth={str(auth_uid)[:8]}...  email={user_info['email']}")


def verify_login():
    """--verify-login: test all passwords against stored hashes."""
    from werkzeug.security import check_password_hash
    if not os.path.isfile(CREDENTIALS_FILE):
        print("ERROR: credentials file not found. Run seeding first.")
        return False
    with open(CREDENTIALS_FILE) as f:
        creds = json.load(f)

    print("=== Password Verification ===")
    print(f"  Password checker:   werkzeug.security.check_password_hash")
    print(f"  Hash algorithm:     scrypt (generated by generate_password_hash)")
    print()

    all_ok = True
    for user_info in TEST_USERS:
        username = user_info["username"]
        email = user_info["email"]
        cred = creds.get(username)
        if not cred:
            print(f"  [FAIL] {username:20s}  NO CREDENTIAL — {email}")
            all_ok = False
            continue
        stored_hash = cred.get("password_hash", "")
        correct = check_password_hash(stored_hash, PASSWORD)
        wrong = check_password_hash(stored_hash, "wrong_password_123")
        if correct and not wrong:
            print(f"  [PASS] {username:20s}  hash_ok={correct}  wrong_rejected={not wrong}")
        else:
            print(f"  [FAIL] {username:20s}  hash_ok={correct}  wrong_rejected={not wrong}")
            all_ok = False

    print()
    if all_ok:
        print("  ALL PASS — password verification works for all test accounts")
    else:
        print("  SOME FAILED — run with --force-password to regenerate hashes")
    print()
    return all_ok


def force_password():
    """--force-password: re-read profiles from DB and re-save credentials."""
    print("=== Force Password Update ===")
    profiles = {}
    auth_user_ids = {}
    for user_info in TEST_USERS:
        username = user_info["username"]
        rows = fast_query(
            "SELECT id, auth_user_id FROM chain_profiles WHERE username = %s LIMIT 1",
            (username,), default=[]
        )
        if rows:
            profiles[username] = rows[0]["id"]
            auth_user_ids[username] = rows[0]["auth_user_id"]
            print(f"  Found profile: {username} (id={rows[0]['id'][:8]}...)")
        else:
            print(f"  SKIP (no profile): {username}")
    if profiles:
        save_credentials(profiles, auth_user_ids)
        print("Password hash regenerated and saved.")
    else:
        print("No profiles found. Run seeding first.")


def main():
    print("=== Seeding Chain Test Users ===")

    profiles = {}
    auth_user_ids = {}
    created_any = False
    for user_info in TEST_USERS:
        pid, auth_uid, is_new = upsert_test_user(user_info)
        profiles[user_info["username"]] = pid
        auth_user_ids[user_info["username"]] = auth_uid
        if is_new:
            created_any = True

    seed_mutual_follows(profiles)

    save_credentials(profiles, auth_user_ids)

    print(f"\nTest password for all users: {PASSWORD}")
    print("Users created/verified:")
    for u in TEST_USERS:
        print(f"  - {u['username']} ({u['email']})")
    print("=== Done ===")


if __name__ == "__main__":
    if "--verify-login" in sys.argv:
        ok = verify_login()
        sys.exit(0 if ok else 1)
    elif "--force-password" in sys.argv:
        force_password()
        sys.exit(0)
    else:
        main()
