#!/usr/bin/env python3
"""Create Phase 84 video interest event table and indexes."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DDL = [
    """
    CREATE TABLE IF NOT EXISTS chain_video_events (
        id UUID PRIMARY KEY,
        viewer_profile_id UUID NOT NULL,
        video_type TEXT NOT NULL CHECK (video_type IN ('reel','post','story')),
        video_id UUID NOT NULL,
        creator_profile_id UUID,
        event_type TEXT NOT NULL CHECK (event_type IN (
            'impression','view','watch_3s','watch_10s','complete',
            'like','comment','share','save','skip','follow_creator'
        )),
        watch_ms INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_chain_video_events_viewer_created ON chain_video_events(viewer_profile_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_chain_video_events_video_event_created ON chain_video_events(video_id, event_type, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_chain_video_events_creator_created ON chain_video_events(creator_profile_id, created_at DESC)",
]


def main():
    try:
        from services.neon_service import write_query
    except Exception as error:
        print(f"SKIP database unavailable: {error}")
        return 0

    ok = 0
    for statement in DDL:
        try:
            write_query(statement, timeout_ms=15000)
            ok += 1
            print("OK", statement.strip().splitlines()[0][:80])
        except Exception as error:
            print(f"WARN schema statement failed: {error}")
    print(f"phase84_video_events_schema: {ok}/{len(DDL)} statements applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
