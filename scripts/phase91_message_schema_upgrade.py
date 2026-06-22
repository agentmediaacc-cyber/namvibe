#!/usr/bin/env python3
"""Phase 91 messaging schema hardening.

Idempotent, data-safe migration for receipt lifecycle, idempotent sends,
reply/forward links, and delete-for-everyone support.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.neon_service import get_connection, release_connection


MESSAGE_COLUMNS = [
    ("message_type", "TEXT DEFAULT 'text'"),
    ("media_url", "TEXT NULL"),
    ("media_type", "TEXT NULL"),
    ("storage_bucket", "TEXT NULL"),
    ("storage_path", "TEXT NULL"),
    ("media_bucket", "TEXT NULL"),
    ("media_path", "TEXT NULL"),
    ("mime_type", "TEXT NULL"),
    ("size_bytes", "BIGINT NULL"),
    ("client_event_id", "TEXT NULL"),
    ("parent_message_id", "UUID NULL"),
    ("is_forwarded", "BOOLEAN DEFAULT FALSE"),
    ("status_id", "TEXT NULL"),
    ("sticker_id", "TEXT NULL"),
    ("gif_url", "TEXT NULL"),
    ("location_lat", "DOUBLE PRECISION NULL"),
    ("location_lng", "DOUBLE PRECISION NULL"),
    ("contact_data", "JSONB NULL"),
    ("delivery_status", "TEXT DEFAULT 'sent'"),
    ("is_seen", "BOOLEAN DEFAULT FALSE"),
    ("read_at", "TIMESTAMPTZ NULL"),
    ("deleted_at", "TIMESTAMPTZ NULL"),
    ("status", "TEXT DEFAULT 'sent'"),
    ("delivered_at", "TIMESTAMPTZ NULL"),
    ("seen_at", "TIMESTAMPTZ NULL"),
    ("client_temp_id", "TEXT NULL"),
    ("deleted_for_everyone_at", "TIMESTAMPTZ NULL"),
    ("deleted_for_sender", "BOOLEAN DEFAULT FALSE"),
    ("reply_to_message_id", "UUID NULL"),
    ("forwarded_from_message_id", "UUID NULL"),
    ("edited_at", "TIMESTAMPTZ NULL"),
    ("duration_seconds", "INTEGER NULL"),
    ("file_size", "BIGINT NULL"),
]

RECEIPT_COLUMNS = [
    ("id", "UUID DEFAULT gen_random_uuid()"),
    ("message_id", "UUID NULL"),
    ("user_id", "UUID NULL"),
    ("status", "TEXT NOT NULL DEFAULT 'sent'"),
    ("delivered_at", "TIMESTAMPTZ NULL"),
    ("seen_at", "TIMESTAMPTZ NULL"),
    ("created_at", "TIMESTAMPTZ DEFAULT now()"),
    ("updated_at", "TIMESTAMPTZ DEFAULT now()"),
]


INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_p91_messages_thread_created_id ON chain_messages(thread_id, created_at ASC, id ASC)",
    "CREATE INDEX IF NOT EXISTS idx_p91_messages_sender_created ON chain_messages(sender_profile_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_p91_messages_client_temp_id ON chain_messages(client_temp_id)",
    "CREATE INDEX IF NOT EXISTS idx_p91_messages_reply_to ON chain_messages(reply_to_message_id)",
    "CREATE INDEX IF NOT EXISTS idx_p91_messages_forwarded_from ON chain_messages(forwarded_from_message_id)",
    "CREATE INDEX IF NOT EXISTS idx_p91_thread_members_profile_thread ON chain_thread_members(profile_id, thread_id)",
    "CREATE INDEX IF NOT EXISTS idx_p91_receipts_message_user ON chain_message_receipts(message_id, user_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_p91_receipts_message_user ON chain_message_receipts(message_id, user_id) WHERE user_id IS NOT NULL",
]


def _column_exists(cur, table, column):
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (table, column),
    )
    return bool(cur.fetchone())


def run():
    conn = None
    applied = []
    try:
        conn = get_connection(timeout_ms=30000)
        # get_connection() sets statement_timeout, which opens a transaction in psycopg2.
        # Clear that setup transaction before starting migration DDL.
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chain_message_receipts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    message_id UUID NOT NULL,
                    user_id UUID NOT NULL,
                    status TEXT NOT NULL DEFAULT 'sent',
                    delivered_at TIMESTAMPTZ NULL,
                    seen_at TIMESTAMPTZ NULL,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now(),
                    UNIQUE(message_id, user_id)
                )
                """
            )
            applied.append("chain_message_receipts")

            for column, ddl in RECEIPT_COLUMNS:
                if not _column_exists(cur, "chain_message_receipts", column):
                    cur.execute(f"ALTER TABLE chain_message_receipts ADD COLUMN {column} {ddl}")
                    applied.append(f"chain_message_receipts.{column}")
            if _column_exists(cur, "chain_message_receipts", "profile_id"):
                cur.execute(
                    """
                    UPDATE chain_message_receipts
                    SET user_id = COALESCE(user_id, profile_id)
                    WHERE user_id IS NULL
                    """
                )

            for column, ddl in MESSAGE_COLUMNS:
                if not _column_exists(cur, "chain_messages", column):
                    cur.execute(f"ALTER TABLE chain_messages ADD COLUMN {column} {ddl}")
                    applied.append(f"chain_messages.{column}")

            # Keep the new status/client_temp_id aliases populated for older rows.
            if _column_exists(cur, "chain_messages", "delivery_status"):
                cur.execute(
                    """
                    UPDATE chain_messages
                    SET status = COALESCE(status, delivery_status, 'sent')
                    WHERE status IS NULL
                    """
                )
            if _column_exists(cur, "chain_messages", "client_event_id"):
                cur.execute(
                    """
                    UPDATE chain_messages
                    SET client_temp_id = COALESCE(client_temp_id, client_event_id)
                    WHERE client_temp_id IS NULL AND client_event_id IS NOT NULL
                    """
                )

            for index_sql in INDEXES:
                cur.execute(index_sql)
            applied.append("indexes")

        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            release_connection(conn)

    print("phase91_message_schema_upgrade_ok")
    print("applied=" + ",".join(applied))


if __name__ == "__main__":
    run()
