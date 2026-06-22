"""Phase 96 follow duplicate cleanup.

Audits active duplicate chain_follows relationships, keeps the oldest active
record per (follower_profile_id, following_profile_id), soft-deletes the rest,
and creates the unique active follow index.

Run:
    python3 scripts/phase96_follow_duplicate_cleanup.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services.neon_service import fast_query, write_query


DUPLICATE_QUERY = """
SELECT follower_profile_id,
       following_profile_id,
       COUNT(*) AS count
FROM chain_follows
WHERE deleted_at IS NULL
GROUP BY follower_profile_id, following_profile_id
HAVING COUNT(*) > 1
ORDER BY count DESC, follower_profile_id, following_profile_id
"""


def _count_active_duplicates():
    rows = fast_query(DUPLICATE_QUERY, timeout_ms=30000, default=[])
    duplicate_rows = sum(int(row.get("count") or 0) - 1 for row in rows)
    return rows, duplicate_rows


def _count_active_follows():
    rows = fast_query(
        "SELECT COUNT(*) AS count FROM chain_follows WHERE deleted_at IS NULL",
        timeout_ms=30000,
        default=[{"count": 0}],
    )
    return int(rows[0].get("count") or 0) if rows else 0


def _soft_delete_duplicates():
    result = write_query(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY follower_profile_id, following_profile_id
                       ORDER BY created_at ASC NULLS LAST, id ASC
                   ) AS rn
            FROM chain_follows
            WHERE deleted_at IS NULL
        ),
        updated AS (
            UPDATE chain_follows cf
            SET deleted_at = now()
            FROM ranked r
            WHERE cf.id = r.id
              AND r.rn > 1
            RETURNING cf.id
        )
        SELECT COUNT(*) AS soft_deleted FROM updated
        """,
        timeout_ms=60000,
    )
    if isinstance(result, list) and result:
        return int(result[0].get("soft_deleted") or 0)
    return 0


def _create_unique_index():
    write_query(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_chain_follows_active_pair
        ON chain_follows(follower_profile_id, following_profile_id)
        WHERE deleted_at IS NULL
        """,
        timeout_ms=60000,
    )


def run():
    print("[phase96-follow-cleanup] starting")
    active_before = _count_active_follows()
    duplicate_pairs_before, duplicate_rows_before = _count_active_duplicates()

    print(f"[phase96-follow-cleanup] active follows before: {active_before}")
    print(f"[phase96-follow-cleanup] duplicate active pairs before: {len(duplicate_pairs_before)}")
    print(f"[phase96-follow-cleanup] duplicate active rows to soft-delete: {duplicate_rows_before}")

    for row in duplicate_pairs_before[:50]:
        print(
            "[phase96-follow-cleanup] duplicate pair "
            f"follower={row.get('follower_profile_id')} "
            f"following={row.get('following_profile_id')} "
            f"count={row.get('count')}"
        )
    if len(duplicate_pairs_before) > 50:
        print(f"[phase96-follow-cleanup] ... {len(duplicate_pairs_before) - 50} more duplicate pairs not printed")

    soft_deleted = _soft_delete_duplicates()
    print(f"[phase96-follow-cleanup] soft-deleted duplicates: {soft_deleted}")

    _create_unique_index()
    print("[phase96-follow-cleanup] unique index ensured: uq_chain_follows_active_pair")

    active_after = _count_active_follows()
    duplicate_pairs_after, duplicate_rows_after = _count_active_duplicates()

    print(f"[phase96-follow-cleanup] active follows after: {active_after}")
    print(f"[phase96-follow-cleanup] duplicate active pairs after: {len(duplicate_pairs_after)}")
    print(f"[phase96-follow-cleanup] duplicate active rows after: {duplicate_rows_after}")

    if duplicate_pairs_after:
        print("[phase96-follow-cleanup] FAIL duplicates remain")
        return False

    print("[phase96-follow-cleanup] verification query returned 0 rows")
    print("[phase96-follow-cleanup] complete")
    return True


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
