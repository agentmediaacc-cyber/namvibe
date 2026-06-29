#!/usr/bin/env python3
"""
Phase 3: Real-Time Platform Engine — Test Script
Verifies all 12 components compile and import correctly.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("FLASK_ENV", "development")

import py_compile


def check(desc, condition, failures):
    if not condition:
        failures.append(desc)
        print(f"  FAIL: {desc}")
    else:
        print(f"  OK: {desc}")


def main():
    failures = []

    print("\n=== Phase 3: Real-Time Platform Engine — Compile & Import Tests ===\n")

    # Python files
    python_files = [
        "services/activity_engine.py",
        "services/presence_service.py",
        "services/socket_room_service.py",
        "services/performance_monitor.py",
        "services/notification_grouping_service.py",
    ]
    print("[Python Compilation]")
    for pf in python_files:
        path = ROOT / pf
        check(f"{pf} compiles", py_compile.compile(str(path), doraise=True), failures)

    # Import tests
    print("\n[Python Imports]")
    modules_to_import = [
        ("services.activity_engine", ["emit_activity", "get_recent_activity", "get_activity_summary", "emit_socket_activity"]),
        ("services.presence_service", ["set_presence", "get_presence", "get_many_presence", "heartbeat", "set_online", "set_offline", "set_typing", "clear_presence", "presence_label"]),
        ("services.socket_room_service", ["safe_emit_to_user", "safe_emit_to_thread", "safe_emit_to_call", "safe_emit_typing", "user_room", "thread_room", "call_room"]),
        ("services.performance_monitor", ["track_timing", "track_counter", "get_performance_snapshot", "slow_query_warning", "record_cache_hit", "record_cache_miss"]),
        ("services.notification_grouping_service", ["group_notifications", "get_group_key"]),
    ]
    for mod_name, funcs in modules_to_import:
        try:
            mod = __import__(mod_name, fromlist=funcs)
            check(f"{mod_name} imports OK", True, failures)
            for fn in funcs:
                check(f"  {mod_name}.{fn} exists", hasattr(mod, fn), failures)
        except Exception as e:
            check(f"{mod_name} imports", False, failures)
            check(f"  error: {e}", False, failures)

    # JS files exist and have expected exports
    print("\n[JavaScript Files]")
    js_files = [
        ("static/js/namvibe_realtime_engine.js", "window.NamVibeRealtime"),
        ("static/js/namvibe_upload_manager.js", "window.NamVibeUpload"),
        ("static/js/namvibe_offline_queue.js", "window.NamVibeOffline"),
        ("static/js/namvibe_infinite_scroll.js", "window.NamVibeInfinite"),
        ("static/js/namvibe_image_loader.js", "window.NamVibeImageLoader"),
    ]
    for jspath, expected_export in js_files:
        full = ROOT / jspath
        check(f"{jspath} exists", full.exists(), failures)
        if full.exists():
            content = full.read_text()
            check(f"{jspath} exports {expected_export.split('.')[-1]}", expected_export in content, failures)

    # CSS files exist
    print("\n[CSS Files]")
    css_files = [
        "static/css/namvibe_realtime_engine.css",
        "static/css/namvibe_upload_manager.css",
        "static/css/namvibe_image_loader.css",
    ]
    for c in css_files:
        check(f"{c} exists", (ROOT / c).exists(), failures)

    # Migration script exists
    print("\n[Migration Script]")
    migration = ROOT / "scripts/migrations/create_activity_events.sql"
    check("migration script exists", migration.exists(), failures)
    if migration.exists():
        content = migration.read_text()
        check("contains CREATE TABLE", "CREATE TABLE IF NOT EXISTS chain_activity_events" in content, failures)
        check("contains indexes", "CREATE INDEX IF NOT EXISTS" in content, failures)

    # Template loading
    print("\n[Template Includes]")
    base = (ROOT / "templates/base.html").read_text()
    css_includes = [
        "namvibe_realtime_engine.css",
        "namvibe_upload_manager.css",
        "namvibe_image_loader.css",
    ]
    js_includes = [
        "namvibe_realtime_engine.js",
        "namvibe_upload_manager.js",
        "namvibe_offline_queue.js",
        "namvibe_infinite_scroll.js",
        "namvibe_image_loader.js",
    ]
    for css in css_includes:
        check(f"base.html includes {css}", css in base, failures)
    for js in js_includes:
        check(f"base.html includes {js}", js in base, failures)

    # Route wiring checks
    print("\n[Route Wiring]")
    msg = (ROOT / "api_routes/message_routes.py").read_text()
    check("message_routes has emit_activity import", "from services.activity_engine import emit_activity" in msg, failures)
    cr = (ROOT / "api_routes/call_routes.py").read_text()
    check("call_routes has emit_activity import", "from services.activity_engine import emit_activity" in cr, failures)
    pr = (ROOT / "api_routes/profile_routes.py").read_text()
    check("profile_routes has emit_activity import", "from services.activity_engine import emit_activity" in pr, failures)

    total = len(python_files) + sum(1 + len(f) for _, f in modules_to_import) + len(js_files) * 2 + len(css_files) + 3 + len(css_includes) + len(js_includes) + 3
    passed = total - len(failures)
    print(f"\n{'='*50}")
    print(f"Tests: {passed}/{total} passed")
    if failures:
        print(f"Failures ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
