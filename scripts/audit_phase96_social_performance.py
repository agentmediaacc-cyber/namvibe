"""Audit Phase 96 social relationship performance.

Checks Discovery loading with query instrumentation and ensures social indexes
needed by the batched relationship path exist.

Run:
    python3 scripts/audit_phase96_social_performance.py
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("WTF_CSRF_ENABLED", "0")


INDEXES = [
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_chain_follows_active
    ON chain_follows(follower_profile_id, following_profile_id)
    WHERE deleted_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phase96_perf_follows_following_active
    ON chain_follows(following_profile_id, follower_profile_id)
    WHERE deleted_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phase96_perf_friend_requests_sender_recipient_status
    ON chain_friend_requests(sender_profile_id, recipient_profile_id, status)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phase96_perf_friend_requests_recipient_sender_status
    ON chain_friend_requests(recipient_profile_id, sender_profile_id, status)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phase96_perf_follow_requests_requester_target_status
    ON chain_follow_requests(requester_profile_id, target_profile_id, status)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phase96_perf_follow_requests_target_requester_status
    ON chain_follow_requests(target_profile_id, requester_profile_id, status)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phase96_perf_friends_p1_p2_active
    ON chain_friends(profile_id_1, profile_id_2, status)
    WHERE deleted_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phase96_perf_friends_p2_p1_active
    ON chain_friends(profile_id_2, profile_id_1, status)
    WHERE deleted_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phase96_perf_blocks_blocker_blocked_active
    ON chain_blocks(blocker_profile_id, blocked_profile_id)
    WHERE deleted_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phase96_perf_blocks_blocked_blocker_active
    ON chain_blocks(blocked_profile_id, blocker_profile_id)
    WHERE deleted_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_phase96_perf_profiles_discovery
    ON chain_profiles(is_public, is_premium DESC, created_at DESC)
    WHERE deleted_at IS NULL
    """,
]


def ensure_indexes():
    from services.neon_service import write_query

    print("[phase96-perf] ensuring indexes")
    for sql in INDEXES:
        write_query(sql, timeout_ms=60000)
    print(f"[phase96-perf] indexes ensured: {len(INDEXES)}")


def _viewer():
    from services.neon_service import fast_query

    rows = fast_query(
        "SELECT id, auth_user_id FROM chain_profiles WHERE deleted_at IS NULL ORDER BY created_at ASC LIMIT 1",
        timeout_ms=30000,
        default=[],
    )
    return rows[0] if rows else None


def _instrument():
    import services.discovery_service as ds
    import services.relationship_cache_service as rcs
    import services.blocking_service as bs
    import services.recommendation_service as rec

    counts = {
        "discovery_fast_query": 0,
        "relationship_cache_fast_query": 0,
        "blocking_fast_query": 0,
        "recommendation_fast_query": 0,
        "information_schema": 0,
        "sql": [],
    }

    def wrap(name, fn):
        def inner(sql, *args, **kwargs):
            sql_text = str(sql)
            counts[name] += 1
            if "information_schema" in sql_text.lower():
                counts["information_schema"] += 1
            counts["sql"].append(" ".join(sql_text.split())[:180])
            return fn(sql, *args, **kwargs)
        return inner

    ds.fast_query = wrap("discovery_fast_query", ds.fast_query)
    rcs.fast_query = wrap("relationship_cache_fast_query", rcs.fast_query)
    rcs.cache_get = lambda key: None
    rcs.cache_set = lambda key, value, ttl=None: None
    bs.fast_query = wrap("blocking_fast_query", bs.fast_query)
    rec.fast_query = wrap("recommendation_fast_query", rec.fast_query)
    return counts


def _assert_no_startup_phase96_scripts():
    with open(os.path.join(ROOT, "app.py"), "r", encoding="utf-8") as fh:
        app_src = fh.read()
    forbidden = (
        "phase96_fix_social_relationships",
        "phase96_follow_duplicate_cleanup",
        "test_phase96_social_relationships",
        "audit_phase96_social_performance",
    )
    hits = [token for token in forbidden if token in app_src]
    print(f"[phase96-perf] startup phase96 script references in app.py: {hits}")
    return not hits


def load_discover(app_module):
    counts = _instrument()
    viewer = _viewer()
    app = app_module.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    client = app.test_client()

    if viewer:
        with client.session_transaction() as sess:
            sess["profile_id"] = str(viewer["id"])
            sess["auth_user_id"] = str(viewer.get("auth_user_id") or viewer["id"])
            sess["user_id"] = str(viewer.get("auth_user_id") or viewer["id"])

    start = time.perf_counter()
    response = client.get("/discover/?limit=20")
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    return response, elapsed_ms, counts, viewer


def run():
    import app as app_module  # Import first; app.py applies gevent monkey-patching at module top.

    ensure_indexes()
    startup_ok = _assert_no_startup_phase96_scripts()
    response, elapsed_ms, counts, viewer = load_discover(app_module)

    repeated_social_queries = counts["blocking_fast_query"] > 0 or counts["relationship_cache_fast_query"] > 5
    info_schema_ok = counts["information_schema"] == 0
    status_ok = response.status_code == 200

    print(f"[phase96-perf] viewer_id: {viewer.get('id') if viewer else None}")
    print(f"[phase96-perf] /discover status: {response.status_code}")
    print(f"[phase96-perf] /discover total_load_ms: {elapsed_ms}")
    print(f"[phase96-perf] discovery_fast_query: {counts['discovery_fast_query']}")
    print(f"[phase96-perf] recommendation_fast_query: {counts['recommendation_fast_query']}")
    print(f"[phase96-perf] relationship_cache_fast_query: {counts['relationship_cache_fast_query']}")
    print(f"[phase96-perf] blocking_fast_query: {counts['blocking_fast_query']}")
    print(f"[phase96-perf] information_schema_queries: {counts['information_schema']}")
    print(f"[phase96-perf] repeated_per_user_social_queries: {repeated_social_queries}")
    print("[phase96-perf] captured_sql:")
    for sql in counts["sql"]:
        print(f"  - {sql}")

    ok = status_ok and startup_ok and info_schema_ok and not repeated_social_queries
    print(f"[phase96-perf] result: {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
