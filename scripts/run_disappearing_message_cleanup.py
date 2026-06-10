#!/usr/bin/env python3
"""
Phase 54 disappearing-message cleanup.

Marks expired disappearing messages as deleted/expired. It intentionally
soft-deletes records and leaves permanent deletion to retention jobs.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.message_feature_service import run_disappearing_message_cleanup


def main():
    limit = int(os.environ.get("CHAIN_DISAPPEARING_CLEANUP_LIMIT", "500"))
    result = run_disappearing_message_cleanup(limit=limit)
    print(
        "[disappearing_cleanup] checked={checked} expired={expired} ok={ok}".format(
            checked=result.get("checked_count", 0),
            expired=result.get("expired_count", 0),
            ok=result.get("ok", False),
        )
    )
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
