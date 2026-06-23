#!/usr/bin/env python3
"""Phase 154: Create chain_media_albums table (idempotent, Neon DB only)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip("'\"")
                if v:
                    os.environ[k] = v

from services.neon_service import write_query, get_pool_status
import time

for _ in range(30):
    s = get_pool_status()
    if s.get("pool_ready") or s.get("recent_success"):
        break
    time.sleep(1)

statements = []

statements.append("""
CREATE TABLE IF NOT EXISTS chain_media_albums (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    cover_url TEXT DEFAULT '',
    visibility TEXT DEFAULT 'public' CHECK (visibility IN ('public', 'followers', 'private')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
)
""")

statements.append("CREATE INDEX IF NOT EXISTS idx_chain_media_albums_profile ON chain_media_albums(profile_id)")
statements.append("CREATE INDEX IF NOT EXISTS idx_chain_media_albums_visibility ON chain_media_albums(visibility)")
statements.append("CREATE INDEX IF NOT EXISTS idx_chain_media_albums_created ON chain_media_albums(created_at DESC)")

ok = 0
fail = 0
for sql in statements:
    sql = sql.strip()
    if not sql:
        continue
    try:
        write_query(sql)
        print(f"  OK  {sql[:70]}...")
        ok += 1
    except Exception as e:
        print(f"  ERR {sql[:70]}... -> {e}")
        fail += 1

print(f"\nDone: {ok} ok, {fail} fail")
sys.exit(0 if fail == 0 else 1)
