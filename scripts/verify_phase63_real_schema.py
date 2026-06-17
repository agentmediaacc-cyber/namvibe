#!/usr/bin/env python3
"""Phase 63 — Real Database Schema Verification.

Connects via services/neon_service.py and checks:
  - chain_profiles columns
  - Indexes
Alters table / creates indexes if missing.
"""

import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

REQUIRED_COLUMNS = [
    "cover_path", "cover_url", "banner_path", "banner_url",
    "avatar_storage_path", "avatar_storage_bucket",
    "country", "current_country", "visibility", "profile_type",
    "reels_count", "saved_count", "tagged_count",
    "followers_count", "following_count", "posts_count",
    "is_creator", "is_verified", "verified",
    "profile_completed", "terms_accepted_at", "privacy_version",
]

REQUIRED_INDEXES = [
    "idx_phase62_chain_posts_created_at",
    "idx_phase62_chain_reels_created_at",
    "idx_phase62_chain_profiles_created_at",
    "idx_phase62_chain_stories_created_at",
    "idx_phase62_chain_live_rooms_created_at",
]

INDEX_DEFS = {
    "idx_phase62_chain_posts_created_at": "CREATE INDEX IF NOT EXISTS idx_phase62_chain_posts_created_at ON chain_posts(created_at DESC NULLS LAST)",
    "idx_phase62_chain_reels_created_at": "CREATE INDEX IF NOT EXISTS idx_phase62_chain_reels_created_at ON chain_reels(created_at DESC NULLS LAST)",
    "idx_phase62_chain_profiles_created_at": "CREATE INDEX IF NOT EXISTS idx_phase62_chain_profiles_created_at ON chain_profiles(created_at DESC NULLS LAST)",
    "idx_phase62_chain_stories_created_at": "CREATE INDEX IF NOT EXISTS idx_phase62_chain_stories_created_at ON chain_stories(created_at DESC NULLS LAST)",
    "idx_phase62_chain_live_rooms_created_at": "CREATE INDEX IF NOT EXISTS idx_phase62_chain_live_rooms_created_at ON chain_live_rooms(created_at DESC NULLS LAST)",
}


def main():
    print("=" * 60)
    print("Phase 63 — Real Database Schema Verification")
    print("=" * 60)

    try:
        from services.neon_service import get_connection, release_connection
    except ImportError as e:
        print(f"FAIL: Could not import neon_service: {e}")
        return 1

    conn = None
    try:
        conn = get_connection(timeout_ms=15000)
        print("\n--- Database connection OK ---\n")

        cursor = conn.cursor()

        # 1. Check chain_profiles columns
        print("Checking chain_profiles columns...")
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'chain_profiles'
              AND table_schema = 'public'
        """)
        existing_columns = {row["column_name"] for row in cursor.fetchall()}

        missing_cols = []
        for col in REQUIRED_COLUMNS:
            if col in existing_columns:
                print(f"  PASS: {col}")
            else:
                print(f"  FAIL: {col} — MISSING")
                missing_cols.append(col)

        # Fix missing columns
        if missing_cols:
            print(f"\n--- Adding {len(missing_cols)} missing columns ---")
            for col in missing_cols:
                col_type = "TEXT"
                if col in ("reels_count", "saved_count", "tagged_count",
                           "followers_count", "following_count", "posts_count"):
                    col_type = "INTEGER DEFAULT 0"
                elif col in ("is_creator", "is_verified", "verified", "profile_completed"):
                    col_type = "BOOLEAN DEFAULT FALSE"
                elif col in ("terms_accepted_at", "privacy_version"):
                    col_type = "TIMESTAMPTZ"
                sql = f"ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS {col} {col_type}"
                try:
                    cursor.execute(sql)
                    conn.commit()
                    print(f"  ADDED: {col} ({col_type})")
                except Exception as e:
                    conn.rollback()
                    print(f"  FAIL: Could not add {col}: {e}")

        # 2. Check indexes
        print("\nChecking indexes...")
        cursor.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename IN ('chain_posts', 'chain_reels', 'chain_profiles', 'chain_stories', 'chain_live_rooms')
              AND indexname LIKE 'idx_phase62_%'
        """)
        existing_indexes = {row["indexname"] for row in cursor.fetchall()}

        for idx in REQUIRED_INDEXES:
            if idx in existing_indexes:
                print(f"  PASS: {idx}")
            else:
                print(f"  FAIL: {idx} — MISSING")
                sql = INDEX_DEFS.get(idx)
                if sql:
                    try:
                        cursor.execute(sql)
                        conn.commit()
                        print(f"  CREATED: {idx}")
                    except Exception as e:
                        conn.rollback()
                        print(f"  FAIL: Could not create {idx}: {e}")

        # 3. Verify by re-reading
        print("\n--- Re-verifying after fixes ---")
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'chain_profiles' AND table_schema = 'public'
        """)
        final_cols = {row["column_name"] for row in cursor.fetchall()}
        still_missing = [c for c in REQUIRED_COLUMNS if c not in final_cols]

        cursor.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename IN ('chain_posts', 'chain_reels', 'chain_profiles', 'chain_stories', 'chain_live_rooms')
              AND indexname LIKE 'idx_phase62_%'
        """)
        final_idx = {row["indexname"] for row in cursor.fetchall()}
        still_missing_idx = [i for i in REQUIRED_INDEXES if i not in final_idx]

        print()
        if still_missing:
            print(f"RESULT: {len(still_missing)} columns still missing: {', '.join(still_missing)}")
        else:
            print("RESULT: ALL 22 COLUMNS PRESENT")

        if still_missing_idx:
            print(f"RESULT: {len(still_missing_idx)} indexes still missing: {', '.join(still_missing_idx)}")
        else:
            print("RESULT: ALL 5 INDEXES PRESENT")

        overall = len(still_missing) == 0 and len(still_missing_idx) == 0
        print(f"\nOVERALL: {'PASS' if overall else 'FAIL'}")
        return 0 if overall else 1

    except Exception as e:
        print(f"\nFAIL: Schema check error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if conn:
            try:
                release_connection(conn)
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
