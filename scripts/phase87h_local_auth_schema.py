#!/usr/bin/env python3
"""Phase 87H: create local/dev auth credential fallback table."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_service import write_query


STATEMENTS = [
    """
    CREATE EXTENSION IF NOT EXISTS pgcrypto
    """,
    """
    CREATE TABLE IF NOT EXISTS chain_local_auth_credentials (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id UUID NOT NULL,
        username TEXT NULL,
        email TEXT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now(),
        last_used_at TIMESTAMPTZ NULL,
        CONSTRAINT chain_local_auth_credentials_profile_unique UNIQUE (profile_id)
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_chain_local_auth_credentials_profile_id
        ON chain_local_auth_credentials (profile_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_chain_local_auth_credentials_username_lower
        ON chain_local_auth_credentials (LOWER(username))
        WHERE username IS NOT NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_chain_local_auth_credentials_email_lower
        ON chain_local_auth_credentials (LOWER(email))
        WHERE email IS NOT NULL
    """,
]


def main():
    for statement in STATEMENTS:
        write_query(statement, timeout_ms=15000)
    print("phase87h_local_auth_schema_ok")


if __name__ == "__main__":
    main()
