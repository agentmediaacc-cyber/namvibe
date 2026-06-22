"""Phase 96 - repair NamVibe social relationship schema.

Run:
    python3 scripts/phase96_fix_social_relationships.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services.neon_service import fast_query, write_query


def log(message):
    print(f"[phase96] {message}")


def run_sql(label, sql, params=None, required=True):
    try:
        write_query(sql, params)
        log(f"OK {label}")
        return True
    except Exception as exc:
        level = "FAIL" if required else "WARN"
        log(f"{level} {label}: {exc}")
        if required:
            raise
        return False


def real_columns(table):
    rows = fast_query(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,), timeout_ms=15000, default=[]
    )
    return {row["column_name"] for row in rows if row.get("column_name")}


def ensure_column(table, column, ddl):
    cols = real_columns(table)
    if column in cols:
        log(f"OK column exists: {table}.{column}")
        return
    run_sql(f"column {table}.{column}", f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}")


def ensure_tables():
    run_sql("extension pgcrypto", "CREATE EXTENSION IF NOT EXISTS pgcrypto")
    run_sql(
        "table chain_follows",
        """
        CREATE TABLE IF NOT EXISTS chain_follows (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            follower_profile_id UUID NOT NULL,
            following_profile_id UUID NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ
        )
        """,
    )
    run_sql(
        "table chain_follow_requests",
        """
        CREATE TABLE IF NOT EXISTS chain_follow_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            requester_profile_id UUID NOT NULL,
            target_profile_id UUID NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            responded_at TIMESTAMPTZ
        )
        """,
    )
    run_sql(
        "table chain_friend_requests",
        """
        CREATE TABLE IF NOT EXISTS chain_friend_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sender_profile_id UUID NOT NULL,
            recipient_profile_id UUID NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            responded_at TIMESTAMPTZ
        )
        """,
    )
    run_sql(
        "table chain_friends",
        """
        CREATE TABLE IF NOT EXISTS chain_friends (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            profile_id_1 UUID NOT NULL,
            profile_id_2 UUID NOT NULL,
            status TEXT NOT NULL DEFAULT 'friend',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ
        )
        """,
    )
    run_sql(
        "table chain_blocks",
        """
        CREATE TABLE IF NOT EXISTS chain_blocks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            blocker_profile_id UUID NOT NULL,
            blocked_profile_id UUID NOT NULL,
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ
        )
        """,
    )


def ensure_columns():
    for table in ("chain_follows", "chain_follow_requests", "chain_friend_requests", "chain_friends", "chain_blocks"):
        ensure_column(table, "created_at", "TIMESTAMPTZ NOT NULL DEFAULT now()")
        ensure_column(table, "updated_at", "TIMESTAMPTZ NOT NULL DEFAULT now()")

    ensure_column("chain_follows", "follower_profile_id", "UUID")
    ensure_column("chain_follows", "following_profile_id", "UUID")
    ensure_column("chain_follows", "deleted_at", "TIMESTAMPTZ")

    ensure_column("chain_follow_requests", "requester_profile_id", "UUID")
    ensure_column("chain_follow_requests", "target_profile_id", "UUID")
    ensure_column("chain_follow_requests", "status", "TEXT NOT NULL DEFAULT 'pending'")
    ensure_column("chain_follow_requests", "message", "TEXT")
    ensure_column("chain_follow_requests", "responded_at", "TIMESTAMPTZ")

    ensure_column("chain_friend_requests", "sender_profile_id", "UUID")
    ensure_column("chain_friend_requests", "recipient_profile_id", "UUID")
    ensure_column("chain_friend_requests", "status", "TEXT NOT NULL DEFAULT 'pending'")
    ensure_column("chain_friend_requests", "message", "TEXT")
    ensure_column("chain_friend_requests", "responded_at", "TIMESTAMPTZ")

    ensure_column("chain_friends", "profile_id_1", "UUID")
    ensure_column("chain_friends", "profile_id_2", "UUID")
    ensure_column("chain_friends", "status", "TEXT NOT NULL DEFAULT 'friend'")
    ensure_column("chain_friends", "deleted_at", "TIMESTAMPTZ")

    ensure_column("chain_blocks", "blocker_profile_id", "UUID")
    ensure_column("chain_blocks", "blocked_profile_id", "UUID")
    ensure_column("chain_blocks", "deleted_at", "TIMESTAMPTZ")


def backfill_legacy_columns():
    friend_request_cols = real_columns("chain_friend_requests")
    if "receiver_profile_id" in friend_request_cols and "recipient_profile_id" in friend_request_cols:
        run_sql(
            "backfill recipient_profile_id from receiver_profile_id",
            """
            UPDATE chain_friend_requests
            SET recipient_profile_id = receiver_profile_id
            WHERE recipient_profile_id IS NULL AND receiver_profile_id IS NOT NULL
            """,
            required=False,
        )

    friend_cols = real_columns("chain_friends")
    if {"profile_id", "friend_profile_id", "profile_id_1", "profile_id_2"}.issubset(friend_cols):
        run_sql(
            "backfill ordered chain_friends pair",
            """
            UPDATE chain_friends
            SET profile_id_1 = LEAST(profile_id, friend_profile_id),
                profile_id_2 = GREATEST(profile_id, friend_profile_id),
                status = COALESCE(status, 'friend')
            WHERE (profile_id_1 IS NULL OR profile_id_2 IS NULL)
              AND profile_id IS NOT NULL
              AND friend_profile_id IS NOT NULL
            """,
            required=False,
        )


def ensure_indexes():
    indexes = [
        (
            "unique active follows",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_phase96_chain_follows_active_pair ON chain_follows(follower_profile_id, following_profile_id) WHERE deleted_at IS NULL",
            "CREATE INDEX IF NOT EXISTS idx_phase96_chain_follows_active_pair ON chain_follows(follower_profile_id, following_profile_id) WHERE deleted_at IS NULL",
        ),
        (
            "unique pending follow requests",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_phase96_chain_follow_requests_pending_pair ON chain_follow_requests(requester_profile_id, target_profile_id) WHERE status = 'pending'",
            "CREATE INDEX IF NOT EXISTS idx_phase96_chain_follow_requests_pair ON chain_follow_requests(requester_profile_id, target_profile_id)",
        ),
        (
            "unique pending friend requests",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_phase96_chain_friend_requests_pending_pair ON chain_friend_requests(sender_profile_id, recipient_profile_id) WHERE status = 'pending'",
            "CREATE INDEX IF NOT EXISTS idx_phase96_chain_friend_requests_pair ON chain_friend_requests(sender_profile_id, recipient_profile_id)",
        ),
        (
            "unique active friends",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_phase96_chain_friends_active_pair ON chain_friends(profile_id_1, profile_id_2) WHERE deleted_at IS NULL",
            "CREATE INDEX IF NOT EXISTS idx_phase96_chain_friends_pair ON chain_friends(profile_id_1, profile_id_2)",
        ),
        (
            "unique active blocks",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_phase96_chain_blocks_active_pair ON chain_blocks(blocker_profile_id, blocked_profile_id) WHERE deleted_at IS NULL",
            "CREATE INDEX IF NOT EXISTS idx_phase96_chain_blocks_pair ON chain_blocks(blocker_profile_id, blocked_profile_id)",
        ),
    ]
    for label, unique_sql, fallback_sql in indexes:
        if not run_sql(label, unique_sql, required=False):
            run_sql(f"{label} fallback", fallback_sql, required=False)

    performance_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_phase96_chain_friend_requests_recipient_status ON chain_friend_requests(recipient_profile_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_phase96_chain_friend_requests_sender_status ON chain_friend_requests(sender_profile_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_phase96_chain_follow_requests_target_status ON chain_follow_requests(target_profile_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_phase96_chain_follow_requests_requester_status ON chain_follow_requests(requester_profile_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_phase96_chain_friends_profile_1 ON chain_friends(profile_id_1, profile_id_2)",
        "CREATE INDEX IF NOT EXISTS idx_phase96_chain_friends_profile_2 ON chain_friends(profile_id_2, profile_id_1)",
        "CREATE INDEX IF NOT EXISTS idx_phase96_chain_blocks_blocker_blocked ON chain_blocks(blocker_profile_id, blocked_profile_id)",
    ]
    for sql in performance_indexes:
        run_sql(sql.split(" ON ", 1)[0].replace("CREATE INDEX IF NOT EXISTS ", "index "), sql, required=False)


def run():
    log("starting")
    ensure_tables()
    ensure_columns()
    backfill_legacy_columns()
    ensure_indexes()
    log("complete")
    return True


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
