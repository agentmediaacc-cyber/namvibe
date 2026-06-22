#!/usr/bin/env python3
"""
Phase 127 — Verify all 15 homepage/reels indexes exist in the database.
Checks pg_indexes for each expected index name.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0; FAIL = 0; WARN = 0

EXPECTED_TABLES = [
    "chain_posts",
    "chain_reels",
    "chain_stories",
    "chain_status_posts",
    "chain_live_rooms",
    "chain_profiles",
    "chain_reel_events",
]

EXPECTED_INDEXES = [
    "idx_posts_created_active",
    "idx_posts_profile_created_active",
    "idx_reels_created_active",
    "idx_reels_profile_created_active",
    "idx_stories_created_active",
    "idx_stories_profile_created_active",
    "idx_status_posts_created_active",
    "idx_status_posts_profile_created_active",
    "idx_live_rooms_created_active",
    "idx_live_rooms_is_live_created_active",
    "idx_profiles_created_active",
    "idx_profiles_followers_active",
    "idx_profiles_creator_followers_active",
    "idx_reel_events_reel_created",
    "idx_reel_events_user_created",
]


def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")


print("=" * 60)
print("PHASE 127 — INDEX VERIFICATION")
print("=" * 60)

try:
    from services.neon_service import fast_query, get_pool_status
    from services.logging_service import log_info
except ImportError as e:
    print(f"  [ERROR] Cannot import: {e}")
    sys.exit(1)

pool_status = get_pool_status()
if not pool_status.get("recent_success") and not pool_status.get("pool_ready"):
    warn("Neon pool not ready — results may be incomplete")
    # Try anyway
print("\n--- Pool Status ---")
print(f"  pool_ready: {pool_status.get('pool_ready')}")
print(f"  recent_success: {pool_status.get('recent_success')}")
print(f"  circuit_open: {pool_status.get('circuit_open')}")

# ── 1. Verify tables exist ──
print("\n--- Tables ---")
missing_tables = []
for tbl in EXPECTED_TABLES:
    rows = fast_query(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s",
        (tbl,),
        timeout_ms=2000,
        default=[],
    )
    if rows:
        ok(f"Table `{tbl}` exists")
    else:
        fail(f"Table `{tbl}` missing")
        missing_tables.append(tbl)

# ── 2. Verify indexes exist ──
print("\n--- Indexes ---")
missing_indexes = []
for idx in EXPECTED_INDEXES:
    rows = fast_query(
        "SELECT 1 FROM pg_indexes WHERE indexname = %s",
        (idx,),
        timeout_ms=2000,
        default=[],
    )
    if rows:
        ok(f"Index `{idx}` exists")
    else:
        fail(f"Index `{idx}` missing")
        missing_indexes.append(idx)

# ── 3. Table-level index count ──
print("\n--- Per-Table Index Count ---")
for tbl in EXPECTED_TABLES:
    rows = fast_query(
        "SELECT indexname FROM pg_indexes WHERE tablename = %s AND indexname NOT LIKE '%_pkey'",
        (tbl,),
        timeout_ms=2000,
        default=[],
    )
    names = [r["indexname"] for r in rows]
    expected_count = sum(1 for i in EXPECTED_INDEXES if i.startswith(f"idx_{tbl.split('_', 1)[-1]}") or i.startswith(f"idx_{tbl}"))
    if len(names) >= expected_count:
        ok(f"{tbl}: {len(names)} indexes ({', '.join(names)})")
    else:
        warn(f"{tbl}: expected >= {expected_count}, found {len(names)} — {', '.join(names)}")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 127 — INDEX VERIFICATION SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
if FAIL == 0:
    print("  [PASS] All indexes verified")
else:
    print(f"  [FAIL] {len(missing_indexes)} indexes missing, {len(missing_tables)} tables missing")
print(f"\n  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
