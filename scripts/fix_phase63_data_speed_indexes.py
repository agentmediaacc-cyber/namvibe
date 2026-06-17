#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


INDEX_SPECS = [
    ("idx_p63_chain_profiles_id", "chain_profiles", ["id"], ""),
    ("idx_p63_chain_profiles_auth_user_id", "chain_profiles", ["auth_user_id"], ""),
    ("idx_p63_chain_profiles_username", "chain_profiles", ["username"], ""),
    ("idx_p63_chain_profiles_created_at_desc", "chain_profiles", ["created_at"], "DESC"),
    ("idx_p63_chain_profiles_town", "chain_profiles", ["town"], ""),
    ("idx_p63_chain_profiles_location", "chain_profiles", ["location"], ""),
    ("idx_p63_chain_profiles_is_online", "chain_profiles", ["is_online"], ""),
    ("idx_p63_chain_profiles_is_verified", "chain_profiles", ["is_verified"], ""),
    ("idx_p63_chain_profiles_deleted_at", "chain_profiles", ["deleted_at"], ""),
    ("idx_p63_chain_posts_id", "chain_posts", ["id"], ""),
    ("idx_p63_chain_posts_profile_id", "chain_posts", ["profile_id"], ""),
    ("idx_p63_chain_posts_created_at_desc", "chain_posts", ["created_at"], "DESC"),
    ("idx_p63_chain_posts_deleted_at", "chain_posts", ["deleted_at"], ""),
    ("idx_p63_chain_posts_visibility", "chain_posts", ["visibility"], ""),
    ("idx_p63_chain_posts_town_tag", "chain_posts", ["town_tag"], ""),
    ("idx_p63_chain_posts_post_type", "chain_posts", ["post_type"], ""),
    ("idx_p63_chain_posts_category", "chain_posts", ["category"], ""),
    ("idx_p63_chain_posts_deleted_created", "chain_posts", ["deleted_at", "created_at"], "created_at DESC"),
    ("idx_p63_chain_posts_profile_created", "chain_posts", ["profile_id", "created_at"], "created_at DESC"),
    ("idx_p63_chain_posts_visibility_deleted_created", "chain_posts", ["visibility", "deleted_at", "created_at"], "created_at DESC"),
    ("idx_p63_chain_reels_id", "chain_reels", ["id"], ""),
    ("idx_p63_chain_reels_profile_id", "chain_reels", ["profile_id"], ""),
    ("idx_p63_chain_reels_created_at_desc", "chain_reels", ["created_at"], "DESC"),
    ("idx_p63_chain_reels_deleted_at", "chain_reels", ["deleted_at"], ""),
    ("idx_p63_chain_reels_deleted_created", "chain_reels", ["deleted_at", "created_at"], "created_at DESC"),
    ("idx_p63_chain_reels_profile_created", "chain_reels", ["profile_id", "created_at"], "created_at DESC"),
    ("idx_p63_chain_stories_id", "chain_stories", ["id"], ""),
    ("idx_p63_chain_stories_profile_id", "chain_stories", ["profile_id"], ""),
    ("idx_p63_chain_stories_created_at_desc", "chain_stories", ["created_at"], "DESC"),
    ("idx_p63_chain_stories_deleted_at", "chain_stories", ["deleted_at"], ""),
    ("idx_p63_chain_stories_deleted_created", "chain_stories", ["deleted_at", "created_at"], "created_at DESC"),
    ("idx_p63_chain_stories_profile_created", "chain_stories", ["profile_id", "created_at"], "created_at DESC"),
    ("idx_p63_chain_live_rooms_id", "chain_live_rooms", ["id"], ""),
    ("idx_p63_chain_live_rooms_profile_id", "chain_live_rooms", ["profile_id"], ""),
    ("idx_p63_chain_live_rooms_status", "chain_live_rooms", ["status"], ""),
    ("idx_p63_chain_live_rooms_is_live", "chain_live_rooms", ["is_live"], ""),
    ("idx_p63_chain_live_rooms_created_at_desc", "chain_live_rooms", ["created_at"], "DESC"),
    ("idx_p63_chain_live_rooms_deleted_at", "chain_live_rooms", ["deleted_at"], ""),
    ("idx_p63_chain_live_rooms_is_live_deleted_created", "chain_live_rooms", ["is_live", "deleted_at", "created_at"], "created_at DESC"),
    ("idx_p63_chain_live_rooms_status_deleted_created", "chain_live_rooms", ["status", "deleted_at", "created_at"], "created_at DESC"),
    ("idx_p63_chain_messages_id", "chain_messages", ["id"], ""),
    ("idx_p63_chain_messages_thread_id", "chain_messages", ["thread_id"], ""),
    ("idx_p63_chain_messages_sender_id", "chain_messages", ["sender_id"], ""),
    ("idx_p63_chain_messages_recipient_id", "chain_messages", ["recipient_id"], ""),
    ("idx_p63_chain_messages_sender_profile_id", "chain_messages", ["sender_profile_id"], ""),
    ("idx_p63_chain_messages_recipient_profile_id", "chain_messages", ["recipient_profile_id"], ""),
    ("idx_p63_chain_messages_created_at_desc", "chain_messages", ["created_at"], "DESC"),
    ("idx_p63_chain_messages_deleted_at", "chain_messages", ["deleted_at"], ""),
    ("idx_p63_chain_messages_thread_created", "chain_messages", ["thread_id", "created_at"], "created_at DESC"),
    ("idx_p63_chain_messages_recipient_created", "chain_messages", ["recipient_id", "created_at"], "created_at DESC"),
    ("idx_p63_chain_messages_sender_created", "chain_messages", ["sender_id", "created_at"], "created_at DESC"),
    ("idx_p63_chain_messages_sender_profile_created", "chain_messages", ["sender_profile_id", "created_at"], "created_at DESC"),
    ("idx_p63_chain_notifications_id", "chain_notifications", ["id"], ""),
    ("idx_p63_chain_notifications_recipient_profile_id", "chain_notifications", ["recipient_profile_id"], ""),
    ("idx_p63_chain_notifications_is_read", "chain_notifications", ["is_read"], ""),
    ("idx_p63_chain_notifications_created_at_desc", "chain_notifications", ["created_at"], "DESC"),
    ("idx_p63_chain_notifications_deleted_at", "chain_notifications", ["deleted_at"], ""),
    ("idx_p63_chain_notifications_recipient_read_deleted", "chain_notifications", ["recipient_profile_id", "is_read", "deleted_at"], ""),
    ("idx_p63_chain_wallets_profile_id", "chain_wallets", ["profile_id"], ""),
    ("idx_p63_chain_wallet_transactions_profile_created", "chain_wallet_transactions", ["profile_id", "created_at"], "created_at DESC"),
    ("idx_p63_chain_wallet_transactions_wallet_created", "chain_wallet_transactions", ["wallet_id", "created_at"], "created_at DESC"),
]

ANALYZE_TABLES = [
    "chain_profiles",
    "chain_posts",
    "chain_reels",
    "chain_stories",
    "chain_live_rooms",
    "chain_messages",
    "chain_notifications",
]


def _ident(value):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe identifier: {value}")
    return value


def _schema(fetch_all):
    rows = fetch_all(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        """,
        timeout_ms=15000,
    )
    schema = {}
    for row in rows or []:
        schema.setdefault(row.get("table_name"), set()).add(row.get("column_name"))
    return schema


def _column_expr(columns, desc_hint):
    desc_columns = set()
    if desc_hint == "DESC":
        desc_columns.add(columns[-1])
    elif desc_hint:
        for part in desc_hint.split(","):
            bits = part.strip().split()
            if len(bits) == 2 and bits[1].upper() == "DESC":
                desc_columns.add(bits[0])
    return ", ".join(f"{_ident(col)} DESC" if col in desc_columns else _ident(col) for col in columns)


def main():
    os.chdir(ROOT)
    from services.neon_service import fetch_all, write_query

    schema = _schema(fetch_all)
    if not schema:
        print("FAIL: database schema unavailable; no indexes were created")
        return 1
    created = 0
    skipped = []

    for index_name, table_name, columns, desc_hint in INDEX_SPECS:
        table_columns = schema.get(table_name)
        if not table_columns:
            skipped.append(f"{index_name}: missing table {table_name}")
            continue
        missing = [col for col in columns if col not in table_columns]
        if missing:
            skipped.append(f"{index_name}: missing columns {','.join(missing)}")
            continue
        sql = f"CREATE INDEX IF NOT EXISTS {_ident(index_name)} ON {_ident(table_name)}({_column_expr(columns, desc_hint)})"
        write_query(sql, timeout_ms=30000)
        created += 1

    analyzed = 0
    for table_name in ANALYZE_TABLES:
        if table_name in schema:
            write_query(f"ANALYZE {_ident(table_name)}", timeout_ms=30000)
            analyzed += 1

    print(f"PASS: phase63 indexes checked/created={created} analyzed={analyzed}")
    if skipped:
        print("INFO: skipped optional indexes:")
        for item in skipped:
            print(f" - {item}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
