#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import services.interest_engine as interest_engine


def main() -> int:
    captured = []

    def capture(sql, params=None, timeout_ms=None, default=None):
        captured.append(str(sql))
        return []

    original = interest_engine.fast_query
    interest_engine.fast_query = capture
    try:
        valid = "11111111-1111-1111-1111-111111111111"
        vectors = {}
        interest_engine._collect_liked_posts(vectors, valid)
        interest_engine._collect_liked_reels(vectors, valid)
        interest_engine._collect_saved_posts(vectors, valid)
        interest_engine._collect_saved_reels(vectors, valid)
        interest_engine._collect_shared_posts(vectors, valid)
        interest_engine._collect_watched_reels(vectors, valid)
        interest_engine._collect_commented_posts(vectors, valid)
    finally:
        interest_engine.fast_query = original

    joined = "\n".join(captured).lower()
    assert "chain_shares" not in joined, joined
    assert "r.content" not in joined, joined
    assert "c.content" not in joined, joined
    assert "chain_reels" in joined, joined
    print("TEST_OK feed ai schema contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
