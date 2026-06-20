#!/usr/bin/env python3
"""Development-only password reset helper for local accounts.

Usage:
    python3 scripts/dev_reset_user_password.py --username moon --password "newpass123"

Rules:
    - Only runs if FLASK_ENV=development or CHAIN_ALLOW_DEV_PASSWORD_RESET=1
    - Updates local password hash safely
    - Does not print password
    - Does not touch external auth provider password
"""

import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ALLOW_ENV = os.environ.get("FLASK_ENV") == "development"
ALLOW_FLAG = os.environ.get("CHAIN_ALLOW_DEV_PASSWORD_RESET") == "1"

if not ALLOW_ENV and not ALLOW_FLAG:
    print("password_reset_blocked")
    print("Set FLASK_ENV=development or CHAIN_ALLOW_DEV_PASSWORD_RESET=1")
    sys.exit(1)

parser = argparse.ArgumentParser(description="Dev password reset")
parser.add_argument("--username", required=True)
parser.add_argument("--password", required=True)
args = parser.parse_args()

from werkzeug.security import generate_password_hash
from services.neon_service import fast_query, write_query

hashed = generate_password_hash(args.password)
username = args.username.strip().lower()

# Find profile
profiles = fast_query(
    "SELECT id, email, username FROM chain_profiles WHERE LOWER(username) = %s AND deleted_at IS NULL LIMIT 1",
    [username],
    timeout_ms=30000,
)
if not profiles:
    profiles = fast_query(
        "SELECT id, email, username FROM chain_profiles WHERE LOWER(email) = %s AND deleted_at IS NULL LIMIT 1",
        [username],
        timeout_ms=30000,
    )

if not profiles:
    print("profile_not_found")
    sys.exit(1)

profile = profiles[0]
profile_id = profile["id"]

# Update password_hash (preferred column) when the profile table supports it.
cols = fast_query(
    "SELECT column_name FROM information_schema.columns WHERE table_name = 'chain_profiles' AND column_name IN ('password_hash', 'hashed_password', 'password', 'password_digest', 'legacy_password_hash')",
    timeout_ms=3000
)
col_names = [r["column_name"] for r in cols]

if "password_hash" in col_names:
    write_query("UPDATE chain_profiles SET password_hash = %s WHERE id = %s", [hashed, profile_id])
    method = "password_hash"
elif "hashed_password" in col_names:
    write_query("UPDATE chain_profiles SET hashed_password = %s WHERE id = %s", [hashed, profile_id])
    method = "hashed_password"
elif "password" in col_names:
    write_query("UPDATE chain_profiles SET password = %s WHERE id = %s", [hashed, profile_id])
    method = "password"
elif "password_digest" in col_names:
    write_query("UPDATE chain_profiles SET password_digest = %s WHERE id = %s", [hashed, profile_id])
    method = "password_digest"
elif "legacy_password_hash" in col_names:
    write_query("UPDATE chain_profiles SET legacy_password_hash = %s WHERE id = %s", [hashed, profile_id])
    method = "legacy_password_hash"
else:
    write_query(
        """
        INSERT INTO chain_local_auth_credentials (profile_id, username, email, password_hash, updated_at)
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (profile_id) DO UPDATE SET
            username = EXCLUDED.username,
            email = EXCLUDED.email,
            password_hash = EXCLUDED.password_hash,
            updated_at = now()
        """,
        [profile_id, profile.get("username"), profile.get("email"), hashed],
        timeout_ms=10000,
    )
    method = "chain_local_auth_credentials"

print(f"password_reset_local_ok username={args.username} method={method} id={profile_id}")
