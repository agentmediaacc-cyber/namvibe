import importlib
import inspect
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_project_python():
    try:
        import flask  # noqa: F401
    except ModuleNotFoundError:
        venv_python = ROOT / "venv" / "bin" / "python3"
        if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
            os.execv(str(venv_python), [str(venv_python), *sys.argv])
        raise


_ensure_project_python()

os.environ.setdefault("CHAIN_TRUST_PROFILE_SCHEMA", "1")

from app import app
from services.neon_service import table_exists


TABLE_GROUPS = {
    "message": [
        "chain_message_threads", "chain_thread_members", "chain_messages",
        "chain_message_reactions", "chain_message_stars", "chain_message_edits",
        "chain_message_deletions", "chain_message_forwards", "chain_message_attachments",
        "chain_message_voice_notes", "chain_message_reads",
    ],
    "call": ["chain_call_sessions", "chain_call_participants", "chain_call_events"],
    "group": ["chain_groups", "chain_group_members", "chain_group_join_requests", "chain_group_invites", "chain_group_posts"],
    "live": ["chain_live_rooms", "chain_live_viewers", "chain_live_comments", "chain_live_gifts"],
    "creator_wallet_gift": [
        "chain_wallets", "chain_wallet_transactions", "chain_gift_catalog",
        "chain_creator_earnings", "chain_creator_subscriptions",
        "chain_creator_supporters", "chain_verification_requests",
    ],
}

ROUTES = [
    "/messages/", "/messages/api/messages/send", "/messages/api/messages/<message_id>/reaction",
    "/messages/api/messages/<message_id>/delete", "/messages/api/messages/<thread_id>/seen",
    "/calls/recent", "/calls/start", "/live/", "/live/studio",
    "/creator/dashboard", "/wallet/",
]

TEMPLATES = [
    "messages/index.html", "messages/thread.html", "calls/recent.html",
    "calls/video.html", "live/channels.html", "live/watch.html",
    "creator/dashboard.html", "wallet/index.html",
]

SOCKET_EVENTS = [
    "message:send", "message:delivered", "message:seen", "typing:start",
    "typing:stop", "message:reaction:add", "message:delete",
    "call:offer", "call:answer", "call:end", "call:status",
    "join_live_room", "live_chat_message", "live_gift",
]


def route_rules():
    return {rule.rule for rule in app.url_map.iter_rules()}


def socket_source():
    import services.socket_events as socket_events

    return inspect.getsource(socket_events)


def feature_status():
    statuses = {}
    source_paths = [ROOT / "api_routes" / "message_upgrade_routes.py", ROOT / "api_routes" / "message_routes.py"]
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in source_paths if path.exists())
    statuses["session_only_demo_routes_registered"] = "message_upgrade" in app.blueprints
    statuses["session_only_demo_code_present"] = "session.setdefault" in text
    statuses["phase29_services_present"] = all((ROOT / "services" / name).exists() for name in [
        "message_feature_service.py", "group_feature_service.py", "call_feature_service.py",
        "live_feature_service.py", "creator_feature_service.py",
    ])
    statuses["real_socket_handlers_present"] = all(event in socket_source() for event in ["message:send", "call:answer", "join_live_room"])
    return statuses


def print_group(title, rows):
    print(f"\n{title}")
    print("-" * 72)
    for name, status in rows:
        print(f"{name}: {status}")


def main():
    rules = route_rules()
    print("PHASE 29 feature connection audit")
    print("=" * 72)

    for group, tables in TABLE_GROUPS.items():
        rows = []
        for table in tables:
            try:
                exists = table_exists(table, timeout_ms=500)
            except Exception:
                exists = False
            rows.append((table, "present" if exists else "missing"))
        print_group(f"{group} tables", rows)

    print_group("routes", [(route, "present" if route in rules else "missing") for route in ROUTES])
    print_group("templates", [(template, "present" if (ROOT / "templates" / template).exists() else "missing") for template in TEMPLATES])

    source = socket_source()
    print_group("Socket.IO events", [(event, "present" if re.search(rf'["\']{re.escape(event)}["\']', source) else "missing") for event in SOCKET_EVENTS])

    statuses = feature_status()
    print_group("real/partial/fake status", [(key, value) for key, value in statuses.items()])

    real_score = sum(1 for value in statuses.values() if value is True)
    fake = statuses.get("session_only_demo_routes_registered")
    print("\nSummary")
    print("-" * 72)
    print(f"features_real_or_wired: {real_score}/{len(statuses)}")
    print(f"session_only_routes_live: {bool(fake)}")
    return 1 if fake else 0


if __name__ == "__main__":
    raise SystemExit(main())
