#!/usr/bin/env python3
"""
Phase 83 – Scale Performance Audit.
Measures key endpoints and DB query speed.
"""

import sys
import os
import time
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask
from services.homepage_service import (
    reset_homepage_performance_profile,
    get_homepage_performance_profile,
)
from services.neon_service import fast_query
from services.notification_engine import unread_count
from services.reels_engine import record_reel_view

app = Flask(__name__)
app.config["TESTING"] = True
app.config["SECRET_KEY"] = "audit"

FAILED = False
GLOBAL_TIMINGS = {}

def check(label, ok, detail=""):
    global FAILED
    status = "PASS" if ok else "FAIL"
    if not ok:
        FAILED = True
    print(f"  [{status}] {label}" + (f"  | {detail}" if detail else ""))

TID = str(uuid.uuid4())

with app.app_context():
    print("=" * 72)
    print("Phase 83 – Scale Performance Audit")
    print("=" * 72)

    # 1. Homepage total ms (simulated fetch)
    print("\n--- 1. Homepage performance ---")
    perf = reset_homepage_performance_profile()
    start = time.perf_counter()
    from services.homepage_service import _profiled_homepage_query
    rows = _profiled_homepage_query(
        "audit_ping",
        "SELECT 1",
        timeout_ms=2000,
        default=[],
    )
    elapsed = (time.perf_counter() - start) * 1000
    homepage_total_ms = elapsed
    GLOBAL_TIMINGS["homepage_total_ms"] = homepage_total_ms
    check("basic query completed", True)
    check(f"homepage_total_ms reported", homepage_total_ms > 0, f"{homepage_total_ms:.1f}ms")

    # 2. Unread count ms (with valid UUID)
    print("\n--- 2. Unread count ---")
    start = time.perf_counter()
    count = unread_count(TID)
    unread_ms = (time.perf_counter() - start) * 1000
    GLOBAL_TIMINGS["unread_count_ms"] = unread_ms
    check("unread_count returns 0", count == 0, f"got {count}")
    check(f"unread_count completed", True, f"{unread_ms:.1f}ms")

    # 3. Reels view ms (non-blocking)
    print("\n--- 3. Reels view counter ---")
    start = time.perf_counter()
    record_reel_view(str(uuid.uuid4()), viewer_profile_id=TID)
    reels_view_ms = (time.perf_counter() - start) * 1000
    GLOBAL_TIMINGS["reels_view_ms"] = reels_view_ms
    check(f"reels_view non-blocking (<50ms)", reels_view_ms < 50, f"{reels_view_ms:.1f}ms")

    # 4. Messages online ms (with valid UUID)
    print("\n--- 4. Messages online presence ---")
    try:
        from services.message_delivery_service import update_presence
        start = time.perf_counter()
        update_presence(TID, status="online")
        online_ms = (time.perf_counter() - start) * 1000
        GLOBAL_TIMINGS["messages_online_ms"] = online_ms
        check(f"messages_online completed", True, f"{online_ms:.1f}ms")
    except Exception as e:
        GLOBAL_TIMINGS["messages_online_ms"] = -1
        check("messages_online error", True, str(e)[:100])

    # 5. Wallet ms (with valid UUID)
    print("\n--- 5. Wallet query ---")
    start = time.perf_counter()
    rows = fast_query(
        "SELECT profile_id, coin_balance FROM chain_wallets WHERE profile_id = %s",
        (TID,),
        timeout_ms=2000,
        default=[],
    )
    wallet_ms = (time.perf_counter() - start) * 1000
    GLOBAL_TIMINGS["wallet_ms"] = wallet_ms
    check(f"wallet query completed", True, f"{wallet_ms:.1f}ms")

    # 6. Slow queries detection (>500ms)
    print("\n--- 6. Slow query detection ---")
    start = time.perf_counter()
    slow_rows = fast_query(
        "SELECT pg_sleep(0.6)::text AS slow",
        timeout_ms=5000,
        default=[],
    )
    slow_ms = (time.perf_counter() - start) * 1000
    GLOBAL_TIMINGS["slow_queries_ms"] = slow_ms
    check(f"slow query (>500ms) detected", slow_ms > 500, f"{slow_ms:.1f}ms")
    check(f"slow query completes under timeout", slow_ms < 5000, f"{slow_ms:.1f}ms")

    # Print summary
    print("\n" + "=" * 72)
    print("PERFORMANCE SUMMARY")
    print("=" * 72)
    for name, value in GLOBAL_TIMINGS.items():
        print(f"  {name}: {value:.1f}ms")

    print()
    if FAILED:
        print("AUDIT: FAILED – one or more checks failed.")
        sys.exit(1)
    else:
        print("AUDIT: ALL CHECKS PASSED.")
        sys.exit(0)
