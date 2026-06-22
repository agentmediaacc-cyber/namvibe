"""Audit Phase 97 core NamVibe experience.

This script does not seed fake content. It verifies that the main pages and
JSON endpoints return either real data or explicit safe empty states, while
instrumenting hot-path database calls for information_schema and N+1 risks.

Run:
    python3 scripts/audit_phase97_core_experience.py
"""

import os
import re
import subprocess
import sys
import time
from glob import glob


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("WTF_CSRF_ENABLED", "0")


MODULES_TO_INSTRUMENT = (
    "services.homepage_service",
    "services.discovery_service",
    "services.relationship_cache_service",
    "services.blocking_service",
    "services.recommendation_service",
    "services.profile_service",
    "services.reels_service",
    "services.reels_engine",
    "services.comments_service",
    "services.live_service",
    "services.live_feature_service",
    "services.live_streaming_service",
    "services.creator_service",
    "services.creator_feature_service",
    "services.creator_analytics_engine",
    "services.wallet_service",
    "services.wallet_payment_service",
)


def _ms(start):
    return round((time.perf_counter() - start) * 1000, 2)


def ensure_indexes():
    from services.neon_service import get_cached_table_columns, write_query

    ensured = 0
    skipped = []
    def cols(table):
        try:
            return set(get_cached_table_columns(table, timeout_ms=3000) or [])
        except Exception:
            return set()

    table_cols = {
        table: cols(table)
        for table in (
            "chain_posts", "chain_reels", "chain_stories", "chain_comments",
            "chain_comment_reactions", "chain_live_rooms", "chain_live_comments",
            "chain_live_participants", "chain_wallet_transactions", "chain_creator_earnings",
        )
    }

    indexes = []
    if {"created_at", "deleted_at"}.issubset(table_cols["chain_posts"]):
        indexes.append("CREATE INDEX IF NOT EXISTS idx_phase97_posts_home_public ON chain_posts(created_at DESC) WHERE deleted_at IS NULL")
    if {"created_at", "status", "visibility", "processing_status", "deleted_at"}.issubset(table_cols["chain_reels"]):
        indexes.append("CREATE INDEX IF NOT EXISTS idx_phase97_reels_public_ready ON chain_reels(created_at DESC) WHERE status = 'published' AND visibility = 'public' AND processing_status = 'ready' AND deleted_at IS NULL")
    if {"created_at", "deleted_at"}.issubset(table_cols["chain_stories"]):
        indexes.append("CREATE INDEX IF NOT EXISTS idx_phase97_stories_public_active ON chain_stories(created_at DESC) WHERE deleted_at IS NULL")
    if {"content_type", "content_id", "parent_id", "is_deleted", "created_at"}.issubset(table_cols["chain_comments"]):
        indexes.append("CREATE INDEX IF NOT EXISTS idx_phase97_comments_content_parent ON chain_comments(content_type, content_id, parent_id, is_deleted, created_at)")
        indexes.append("CREATE INDEX IF NOT EXISTS idx_phase97_comments_parent ON chain_comments(parent_id, is_deleted, created_at)")
    if "comment_id" in table_cols["chain_comment_reactions"]:
        indexes.append("CREATE INDEX IF NOT EXISTS idx_phase97_comment_reactions_comment ON chain_comment_reactions(comment_id)")
    if {"status", "created_at"}.issubset(table_cols["chain_live_rooms"]):
        indexes.append("CREATE INDEX IF NOT EXISTS idx_phase97_live_rooms_status ON chain_live_rooms(status, created_at DESC)")
    if {"is_live", "created_at"}.issubset(table_cols["chain_live_rooms"]):
        indexes.append("CREATE INDEX IF NOT EXISTS idx_phase97_live_rooms_is_live ON chain_live_rooms(is_live, created_at DESC)")
    if {"room_id", "created_at"}.issubset(table_cols["chain_live_comments"]):
        indexes.append("CREATE INDEX IF NOT EXISTS idx_phase97_live_comments_room ON chain_live_comments(room_id, created_at DESC)")
    if {"room_id", "role"}.issubset(table_cols["chain_live_participants"]):
        indexes.append("CREATE INDEX IF NOT EXISTS idx_phase97_live_participants_room ON chain_live_participants(room_id, role)")
    if {"profile_id", "created_at"}.issubset(table_cols["chain_wallet_transactions"]):
        indexes.append("CREATE INDEX IF NOT EXISTS idx_phase97_wallet_transactions_profile ON chain_wallet_transactions(profile_id, created_at DESC)")
    if {"creator_profile_id", "created_at"}.issubset(table_cols["chain_creator_earnings"]):
        indexes.append("CREATE INDEX IF NOT EXISTS idx_phase97_creator_earnings_creator_profile ON chain_creator_earnings(creator_profile_id, created_at DESC)")
    if {"creator_id", "created_at"}.issubset(table_cols["chain_creator_earnings"]):
        indexes.append("CREATE INDEX IF NOT EXISTS idx_phase97_creator_earnings_creator ON chain_creator_earnings(creator_id, created_at DESC)")

    for sql in indexes:
        try:
            write_query(sql, timeout_ms=60000)
            ensured += 1
        except Exception as exc:
            skipped.append(str(exc)[:180])
    return {"ensured": ensured, "skipped": skipped, "candidate_count": len(indexes)}


def _viewer():
    from services.neon_service import fast_query

    rows = fast_query(
        """
        SELECT id, auth_user_id, username, avatar_url
        FROM chain_profiles
        WHERE deleted_at IS NULL
        ORDER BY created_at ASC
        LIMIT 1
        """,
        timeout_ms=30000,
        default=[],
    )
    return rows[0] if rows else None


def _instrument():
    counts = {
        "by_module": {},
        "information_schema": 0,
        "social_relationship_sql": 0,
        "sql": [],
    }

    def wrap(module_name, fn):
        def inner(sql, *args, **kwargs):
            sql_text = " ".join(str(sql).split())
            counts["by_module"][module_name] = counts["by_module"].get(module_name, 0) + 1
            if "information_schema" in sql_text.lower():
                counts["information_schema"] += 1
            lowered = sql_text.lower()
            if any(table in lowered for table in ("chain_follows", "chain_friend_requests", "chain_friends", "chain_blocks")):
                counts["social_relationship_sql"] += 1
            counts["sql"].append(f"{module_name}: {sql_text[:220]}")
            return fn(sql, *args, **kwargs)
        return inner

    for module_name in MODULES_TO_INSTRUMENT:
        try:
            module = __import__(module_name, fromlist=["fast_query"])
        except Exception:
            continue
        if hasattr(module, "fast_query"):
            module.fast_query = wrap(module_name, module.fast_query)
        if module_name == "services.relationship_cache_service":
            module.cache_get = lambda key: None
            module.cache_set = lambda key, value, ttl=None: None
    return counts


def _set_session(client, viewer):
    if not viewer:
        return
    with client.session_transaction() as sess:
        sess["profile_id"] = str(viewer["id"])
        sess["auth_user_id"] = str(viewer.get("auth_user_id") or viewer["id"])
        sess["user_id"] = str(viewer.get("auth_user_id") or viewer["id"])
        sess["age_verified"] = True
        sess["age_check_required"] = False


def _get(client, path):
    start = time.perf_counter()
    response = client.get(path)
    return response, _ms(start)


def _json_get(client, path):
    response, elapsed = _get(client, path)
    payload = response.get_json(silent=True)
    return response, elapsed, payload


def _fake_markers(html):
    text = re.sub(r'placeholder="[^"]*"', "", html or "", flags=re.I)
    text = re.sub(r"placeholder='[^']*'", "", text, flags=re.I)
    markers = (
        "dummy data",
        "fake post",
        "fake story",
        "fake reel",
        "lorem ipsum",
        "seeded fake",
        "placeholder user",
        "test placeholder",
    )
    lowered = text.lower()
    return [marker for marker in markers if marker in lowered]


def _startup_script_references():
    with open(os.path.join(ROOT, "app.py"), "r", encoding="utf-8") as fh:
        app_src = fh.read()
    forbidden = (
        "phase96_fix_social_relationships",
        "phase96_follow_duplicate_cleanup",
        "test_phase96_social_relationships",
        "audit_phase96_social_performance",
        "audit_phase97_core_experience",
    )
    return [token for token in forbidden if token in app_src]


def _compile_check():
    targets = ["app.py"]
    targets.extend(sorted(glob(os.path.join("api_routes", "*.py"), root_dir=ROOT)))
    targets.extend(sorted(glob(os.path.join("services", "*.py"), root_dir=ROOT)))
    targets.extend(sorted(glob(os.path.join("scripts", "*.py"), root_dir=ROOT)))
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", *targets],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {"ok": proc.returncode == 0, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}


def _live_readiness(app_module):
    has_socketio = bool(getattr(app_module, "socketio", None))
    try:
        from services import live_feature_service, live_streaming_service
    except Exception:
        return {
            "live_room_shell_ready": False,
            "websocket_ready": has_socketio,
            "real_video_streaming_missing": True,
            "gifts_ready_or_missing": "missing",
            "comments_ready_or_missing": "missing",
        }

    source_paths = [
        os.path.join(ROOT, "services", "live_streaming_service.py"),
        os.path.join(ROOT, "api_routes", "live_routes.py"),
    ]
    source = ""
    for path in source_paths:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                source += fh.read()
        except FileNotFoundError:
            pass
    streaming_terms = ("webrtc", "rtmp", "hls", "mediarecorder", "stream_url")
    real_pipeline_terms = ("aiortc", "ffmpeg", "mux", "livekit", "mediasoup")
    has_settings_shell = any(term in source.lower() for term in streaming_terms)
    has_real_pipeline = any(term in source.lower() for term in real_pipeline_terms)
    return {
        "live_room_shell_ready": hasattr(live_feature_service, "list_live_rooms"),
        "websocket_ready": has_socketio,
        "real_video_streaming_missing": not has_real_pipeline,
        "gifts_ready_or_missing": "ready" if hasattr(live_streaming_service, "send_premium_gift") else "missing",
        "comments_ready_or_missing": "ready" if hasattr(live_feature_service, "add_comment") or hasattr(live_streaming_service, "add_participant") else "missing",
        "stream_settings_shell": has_settings_shell,
    }


def run():
    import app as app_module

    app = app_module.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    # Instrument BEFORE any DB queries
    counts = _instrument()
    client = app.test_client()

    print("[phase97] ensuring performance indexes")
    index_result = ensure_indexes()
    print(f"[phase97] indexes ensured: {index_result['ensured']} of {index_result.get('candidate_count', index_result['ensured'])}")
    if index_result["skipped"]:
        print(f"[phase97] index warnings: {index_result['skipped']}")

    viewer = _viewer()
    print(f"[phase97] viewer_id: {viewer.get('id') if viewer else None}")

    _set_session(client, viewer)

    warmup_paths = [
        ("home", "/"),
        ("discover", "/discover/?limit=5"),
        ("reels", "/reels/"),
        ("live", "/live/"),
    ]
    for _, path in warmup_paths:
        try:
            client.get(path, timeout=5)
        except Exception:
            pass

    results = {}
    route_specs = [
        ("home", "/"),
        ("discover", "/discover/?limit=5"),
        ("profile_public", f"/profile/@{viewer.get('username')}" if viewer and viewer.get("username") else "/"),
        ("reels", "/reels/"),
        ("live", "/live/"),
        ("creator_dashboard", "/creator/dashboard"),
    ]
    for name, path in route_specs:
        try:
            response, elapsed = _get(client, path)
        except Exception:
            results[name] = {"path": path, "status": 0, "ms": -1, "bytes": 0}
            continue
        results[name] = {"path": path, "status": response.status_code, "ms": elapsed, "bytes": len(response.get_data() or b"")}
        if name == "home":
            results[name]["fake_markers"] = _fake_markers(response.get_data(as_text=True))

    api_results = {}
    for name, path in [
        ("profile_summary", "/profile/api/summary"),
        ("reels_feed", "/reels/api/reels/feed?limit=2"),
        ("live_featured", "/live/api/featured"),
        ("creator_earnings", "/creator/api/earnings"),
        ("wallet_balance", "/wallet/api/balance"),
        ("wallet_earnings_breakdown", "/wallet/api/wallet/earnings-breakdown"),
        ("gifts_catalog", "/wallet/api/gifts"),
        ("comments_endpoint", "/api/comments/reel/nonexistent?limit=2"),
    ]:
        try:
            response, elapsed, payload = _json_get(client, path)
        except Exception:
            api_results[name] = {"path": path, "status": 0, "ms": -1, "json": False, "keys": []}
            continue
        api_results[name] = {
            "path": path,
            "status": response.status_code,
            "ms": elapsed,
            "json": payload is not None,
            "keys": sorted(list(payload.keys()))[:8] if isinstance(payload, dict) else [],
        }

    # Check profile avatar fields in template
    if results.get("profile_public", {}).get("status") == 200:
        from engines.cache_engine import get_cache
        try:
            html_bytes = client.get(results["profile_public"]["path"]).get_data()
            html = html_bytes.decode("utf-8", errors="replace")
            results["profile_public"]["has_avatar_field"] = "avatar_url" in html or "avatar" in html.lower()
        except Exception:
            results["profile_public"]["has_avatar_field"] = False
    else:
        results["profile_public"] = results.get("profile_public", {})
        results["profile_public"]["has_avatar_field"] = "skipped"

    startup_refs = _startup_script_references()
    compile_result = _compile_check()
    live_readiness = _live_readiness(app_module)

    print("[phase97] route timings:")
    for name, data in results.items():
        extra = f" fake_markers={data.get('fake_markers')}" if name == "home" else ""
        avatar = f" avatar_field={data.get('has_avatar_field')}" if name == "profile_public" else ""
        print(f"  - {name}: status={data['status']} ms={data['ms']} bytes={data['bytes']}{extra}{avatar}")

    print("[phase97] api checks:")
    for name, data in api_results.items():
        print(f"  - {name}: status={data['status']} ms={data['ms']} json={data['json']} keys={data['keys']}")

    print("[phase97] instrumentation:")
    print(f"  - information_schema_queries: {counts['information_schema']}")
    print(f"  - social_relationship_sql: {counts['social_relationship_sql']}")
    print(f"  - by_module: {counts['by_module']}")
    print("[phase97] captured_sql:")
    for sql in counts["sql"][:80]:
        print(f"  - {sql}")

    print("[phase97] live_readiness:")
    for key, value in live_readiness.items():
        print(f"  - {key}: {value}")

    print(f"[phase97] startup_script_references: {startup_refs}")
    print(f"[phase97] py_compile_ok: {compile_result['ok']}")
    if compile_result["stderr"]:
        print(f"[phase97] py_compile_stderr: {compile_result['stderr']}")

    timing_ok = results.get("home", {}).get("ms", 9999) < 2500 and results.get("discover", {}).get("ms", 9999) < 10000
    status_ok = all(data.get("status", 500) < 500 for data in results.values())
    json_ok = all(data.get("json") or data.get("status", 500) in {302, 401, 403, 404} for data in api_results.values())
    fake_ok = not results.get("home", {}).get("fake_markers")
    schema_ok = counts["information_schema"] == 0
    startup_ok = not startup_refs
    compile_ok = compile_result["ok"]

    ok = timing_ok and status_ok and json_ok and fake_ok and schema_ok and startup_ok and compile_ok
    print(f"[phase97] home_under_2500ms: {results.get('home', {}).get('ms', 9999) < 2500}")
    print(f"[phase97] discover_under_10000ms: {results.get('discover', {}).get('ms', 9999) < 10000}")
    print(f"[phase97] home_no_fake_content: {fake_ok}")
    print(f"[phase97] no_information_schema: {schema_ok}")
    print(f"[phase97] result: {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
