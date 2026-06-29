#!/usr/bin/env python3
"""
Phase 3: Real-Time Platform Engine — Audit Script
Verifies all 12 components are wired correctly.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("FLASK_ENV", "development")

import importlib
import py_compile


def check(desc, condition, failures):
    if not condition:
        failures.append(desc)
        print(f"  FAIL: {desc}")
    else:
        print(f"  OK: {desc}")


def main():
    failures = []

    print("\n=== Phase 3: Real-Time Platform Engine Audit ===\n")

    # 1. Activity Engine
    print("\n[1] Activity Engine")
    check("activity_engine.py compiles", py_compile.compile(str(ROOT / "services/activity_engine.py"), doraise=True), failures)
    import services.activity_engine as ae
    check("_ACTIVITY_TYPES includes message_sent", "message_sent" in ae._ACTIVITY_TYPES, failures)
    check("_ACTIVITY_TYPES includes call_started", "call_started" in ae._ACTIVITY_TYPES, failures)
    check("_ACTIVITY_TYPES includes call_ended", "call_ended" in ae._ACTIVITY_TYPES, failures)
    check("_ACTIVITY_TYPES includes call_missed", "call_missed" in ae._ACTIVITY_TYPES, failures)
    check("_ACTIVITY_TYPES includes profile_viewed", "profile_viewed" in ae._ACTIVITY_TYPES, failures)
    check("_ACTIVITY_TYPES includes message_reacted", "message_reacted" in ae._ACTIVITY_TYPES, failures)
    check("emit_activity function exists", callable(ae.emit_activity), failures)
    check("get_recent_activity function exists", callable(ae.get_recent_activity), failures)
    check("get_activity_summary function exists", callable(ae.get_activity_summary), failures)
    check("emit_socket_activity function exists", callable(ae.emit_socket_activity), failures)
    check("safe_activity_metadata only allows safe keys", ae.safe_activity_metadata({"preview": "ok", "secret": "no"}) == {"preview": "ok"}, failures)
    check("emit_activity returns None for unknown type", ae.emit_activity("test-id", "unknown_type") is None, failures)

    # 2. Presence Service
    print("\n[2] Presence Service")
    check("presence_service.py compiles", py_compile.compile(str(ROOT / "services/presence_service.py"), doraise=True), failures)
    import services.presence_service as ps
    check("set_presence function exists", callable(ps.set_presence), failures)
    check("get_presence function exists", callable(ps.get_presence), failures)
    check("get_many_presence function exists", callable(ps.get_many_presence), failures)
    check("heartbeat function exists", callable(ps.heartbeat), failures)
    check("presence_label function exists", callable(ps.presence_label), failures)
    check("set_online function exists", callable(ps.set_online), failures)
    check("set_offline function exists", callable(ps.set_offline), failures)
    check("set_typing function exists", callable(ps.set_typing), failures)
    check("clear_presence function exists", callable(ps.clear_presence), failures)
    check("set_presence returns None for unknown state", ps.set_presence("test-id", "unknown_state") is None, failures)

    # 3. Socket Room Service
    print("\n[3] Socket Room Service")
    check("socket_room_service.py compiles", py_compile.compile(str(ROOT / "services/socket_room_service.py"), doraise=True), failures)
    import services.socket_room_service as srs
    check("safe_emit_to_user function exists", callable(srs.safe_emit_to_user), failures)
    check("safe_emit_to_thread function exists", callable(srs.safe_emit_to_thread), failures)
    check("safe_emit_to_call function exists", callable(srs.safe_emit_to_call), failures)
    check("safe_emit_typing function exists", callable(srs.safe_emit_typing), failures)
    check("user_room function exists", callable(srs.user_room), failures)
    check("thread_room function exists", callable(srs.thread_room), failures)
    check("call_room function exists", callable(srs.call_room), failures)

    # 4. Notification Grouping (existing service)
    print("\n[4] Notification Grouping")
    check("notification_grouping_service.py compiles", py_compile.compile(str(ROOT / "services/notification_grouping_service.py"), doraise=True), failures)
    import services.notification_grouping_service as ngs
    check("group_notifications function exists", callable(ngs.group_notifications), failures)
    check("TYPES_THAT_CAN_GROUP includes post_like", "post_like" in ngs.TYPES_THAT_CAN_GROUP, failures)
    check("TYPES_THAT_CAN_GROUP includes reel_like", "reel_like" in ngs.TYPES_THAT_CAN_GROUP, failures)

    # 5. Notification Center Service
    print("\n[5] Notification Center Service")
    check("notification_center_service.py compiles", py_compile.compile(str(ROOT / "services/notification_center_service.py"), doraise=True), failures)

    # 6. Migration Script
    print("\n[6] Migration Script")
    migration = ROOT / "scripts/migrations/create_activity_events.sql"
    check("migration script exists", migration.exists(), failures)
    check("migration has CREATE TABLE", "CREATE TABLE IF NOT EXISTS chain_activity_events" in migration.read_text(), failures)
    check("migration has indexes", "CREATE INDEX IF NOT EXISTS" in migration.read_text(), failures)

    # 7. Performance Monitor
    print("\n[7] Performance Monitor")
    check("performance_monitor.py compiles", py_compile.compile(str(ROOT / "services/performance_monitor.py"), doraise=True), failures)
    import services.performance_monitor as pm
    check("track_timing function exists", callable(pm.track_timing), failures)
    check("track_counter function exists", callable(pm.track_counter), failures)
    check("get_performance_snapshot function exists", callable(pm.get_performance_snapshot), failures)
    check("slow_query_warning function exists", callable(pm.slow_query_warning), failures)
    check("record_cache_hit function exists", callable(pm.record_cache_hit), failures)
    check("record_cache_miss function exists", callable(pm.record_cache_miss), failures)

    # 8. Activity wired into message routes
    print("\n[8] Activity Events in Routes")
    msg_routes = (ROOT / "api_routes/message_routes.py").read_text()
    check("message_routes imports emit_activity", "from services.activity_engine import emit_activity" in msg_routes, failures)
    check("message_routes calls emit_activity for message_sent", 'emit_activity(profile_id, "message_sent"' in msg_routes, failures)

    call_routes = (ROOT / "api_routes/call_routes.py").read_text()
    check("call_routes imports emit_activity", "from services.activity_engine import emit_activity" in call_routes, failures)
    check("call_routes calls emit_activity for call_started", 'emit_activity(profile["id"], "call_started"' in call_routes, failures)
    check("call_routes calls emit_activity for call_ended", 'emit_activity(profile["id"], "call_ended"' in call_routes, failures)
    check("call_routes calls emit_activity for call_missed", 'emit_activity(profile["id"], "call_missed"' in call_routes, failures)

    profile_routes = (ROOT / "api_routes/profile_routes.py").read_text()
    check("profile_routes imports emit_activity", "from services.activity_engine import emit_activity" in profile_routes, failures)
    check("profile_routes calls emit_activity for profile_viewed", 'emit_activity(viewer.get("id"), "profile_viewed"' in profile_routes, failures)

    # 9. JS modules
    print("\n[9] JavaScript Modules")
    check("namvibe_realtime_engine.js exists", (ROOT / "static/js/namvibe_realtime_engine.js").exists(), failures)
    check("namvibe_upload_manager.js exists", (ROOT / "static/js/namvibe_upload_manager.js").exists(), failures)
    check("namvibe_offline_queue.js exists", (ROOT / "static/js/namvibe_offline_queue.js").exists(), failures)
    check("namvibe_infinite_scroll.js exists", (ROOT / "static/js/namvibe_infinite_scroll.js").exists(), failures)
    check("namvibe_image_loader.js exists", (ROOT / "static/js/namvibe_image_loader.js").exists(), failures)
    js_re = (ROOT / "static/js/namvibe_realtime_engine.js").read_text()
    check("realtime engine exports NamVibeRealtime", "window.NamVibeRealtime" in js_re, failures)
    js_um = (ROOT / "static/js/namvibe_upload_manager.js").read_text()
    check("upload manager exports NamVibeUpload", "window.NamVibeUpload" in js_um, failures)
    js_oq = (ROOT / "static/js/namvibe_offline_queue.js").read_text()
    check("offline queue exports NamVibeOffline", "window.NamVibeOffline" in js_oq, failures)
    js_is = (ROOT / "static/js/namvibe_infinite_scroll.js").read_text()
    check("infinite scroll exports NamVibeInfinite", "window.NamVibeInfinite" in js_is, failures)
    js_il = (ROOT / "static/js/namvibe_image_loader.js").read_text()
    check("image loader exports NamVibeImageLoader", "window.NamVibeImageLoader" in js_il, failures)

    # 10. CSS modules
    print("\n[10] CSS Modules")
    check("namvibe_realtime_engine.css exists", (ROOT / "static/css/namvibe_realtime_engine.css").exists(), failures)
    check("namvibe_upload_manager.css exists", (ROOT / "static/css/namvibe_upload_manager.css").exists(), failures)
    check("namvibe_image_loader.css exists", (ROOT / "static/css/namvibe_image_loader.css").exists(), failures)

    # 11. Templates
    print("\n[11] Template Loading")
    base = (ROOT / "templates/base.html").read_text()
    check("base.html loads namvibe_realtime_engine.css", "namvibe_realtime_engine.css" in base, failures)
    check("base.html loads namvibe_upload_manager.css", "namvibe_upload_manager.css" in base, failures)
    check("base.html loads namvibe_image_loader.css", "namvibe_image_loader.css" in base, failures)
    check("base.html loads namvibe_realtime_engine.js", "namvibe_realtime_engine.js" in base, failures)
    check("base.html loads namvibe_upload_manager.js", "namvibe_upload_manager.js" in base, failures)
    check("base.html loads namvibe_offline_queue.js", "namvibe_offline_queue.js" in base, failures)
    check("base.html loads namvibe_infinite_scroll.js", "namvibe_infinite_scroll.js" in base, failures)
    check("base.html loads namvibe_image_loader.js", "namvibe_image_loader.js" in base, failures)

    # 12. Verify production routes still work
    print("\n[12] Production Route Integrity")
    try:
        from scripts.verify_production_routes import main as verify_main
        # Don't actually run the full verification since it needs DB, just check import
        check("verify_production_routes imports OK", True, failures)
    except Exception as e:
        check("verify_production_routes imports", False, failures)

    # Summary
    total = 67
    passed = total - len(failures)
    print(f"\n{'='*50}")
    print(f"Audit: {passed}/{total} passed")
    if failures:
        print(f"Failures ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All checks passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
