"""Phase 82: add homepage performance indexes safely."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_service import write_query


INDEXES = [
    """
    CREATE INDEX IF NOT EXISTS idx_phase82_chain_stories_active_created
    ON chain_stories (created_at DESC)
    WHERE deleted_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phase82_chain_reels_active_created
    ON chain_reels (created_at DESC)
    WHERE deleted_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phase82_chain_posts_active_created
    ON chain_posts (created_at DESC)
    WHERE deleted_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phase82_chain_profiles_active_created
    ON chain_profiles (created_at DESC)
    WHERE deleted_at IS NULL
    """,
]


def run():
    failures = []
    for sql in INDEXES:
        name = sql.split("IF NOT EXISTS", 1)[1].split()[0]
        try:
            write_query(sql)
            print(f"  OK  {name}")
        except Exception as error:
            print(f"  FAIL {name}: {error}")
            failures.append(name)
    print(f"\nPhase 82 homepage indexes: {len(INDEXES) - len(failures)} applied/verified, {len(failures)} failed")
    return not failures


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
