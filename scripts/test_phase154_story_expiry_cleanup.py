#!/usr/bin/env python3
"""Phase 154: Story expiry cleanup — finds expired status/story rows, deletes
files from Supabase storage, then marks as deleted in Neon."""

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

from services.neon_service import fast_query, write_query, get_pool_status
from services.supabase_storage_service import BUCKET_MAPPING, SUPABASE_MEDIA_BUCKET
from utils.supabase_client import get_supabase_admin
import time

for _ in range(30):
    s = get_pool_status()
    if s.get("pool_ready") or s.get("recent_success"):
        break
    time.sleep(1)

rows = fast_query(
    "SELECT id, storage_bucket, storage_path FROM chain_status_posts WHERE expires_at < now() AND deleted_at IS NULL",
    timeout_ms=10000,
)

if not rows:
    print("No expired stories to clean up.")
    sys.exit(0)

print(f"Found {len(rows)} expired story rows to clean up.")

supabase = get_supabase_admin()
cleaned = 0
failed = 0

for row in rows:
    path = row.get("storage_path")
    rid = row.get("id", "?")
    if not path:
        print(f"  SKIP {rid}: no storage_path")
        cleaned += 1
        continue
    folder = path.split("/", 1)[0] if "/" in path else None
    bucket = BUCKET_MAPPING.get(folder, SUPABASE_MEDIA_BUCKET) if folder else SUPABASE_MEDIA_BUCKET
    try:
        supabase.storage.from_(bucket).remove([path])
        print(f"  DEL {rid}: {bucket}/{path}")
    except Exception as e:
        print(f"  WARN {rid}: failed to delete {bucket}/{path}: {e}")
    cleaned += 1

write_query(
    "UPDATE chain_status_posts SET deleted_at = now() WHERE expires_at < now() AND deleted_at IS NULL"
)

print(f"\nDone: {cleaned} processed, {failed} hard errors")
sys.exit(0 if failed == 0 else 1)
