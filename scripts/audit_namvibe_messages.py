#!/usr/bin/env python3
from pathlib import Path
import importlib
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {label}" + (f" - {detail}" if detail and not condition else ""))
    return bool(condition)


def main():
    results = []
    app_mod = importlib.import_module("app")
    routes = {rule.rule: sorted(rule.methods) for rule in app_mod.app.url_map.iter_rules()}
    route_src = read("api_routes/messaging_routes.py")
    js = read("static/js/namvibe_messages_pro.js")
    css = read("static/css/namvibe_messages_pro.css")
    thread_html = read("templates/messages/thread.html")
    index_html = read("templates/messages/index.html")
    thread_service = read("services/message_thread_service.py")
    receipt_service = read("services/message_receipt_service.py")
    media_service = read("services/message_media_service.py")
    socket_src = read("services/socket_events.py")
    migration = read("scripts/phase91_message_schema_upgrade.py")

    required_routes = [
        "/messages/",
        "/messages/thread/<thread_id>",
        "/api/messages/send",
        "/api/messages/<message_id>/seen",
        "/api/messages/<message_id>/delivered",
        "/api/messages/<message_id>/delete-for-me",
        "/api/messages/<message_id>/delete-for-everyone",
        "/api/messages/<message_id>/forward",
        "/api/messages/upload",
        "/api/messages/thread/<thread_id>/latest",
        "/api/messages/thread/<thread_id>/older",
        "/api/messages/unread-count",
        "/api/messages/group/create",
        "/api/messages/group/<thread_id>/members/add",
        "/api/messages/group/<thread_id>/members/remove",
        "/api/messages/group/<thread_id>/leave",
    ]
    results.extend(check(f"route exists {route}", route in routes) for route in required_routes)
    results.append(check("required JS file exists", (ROOT / "static/js/namvibe_messages_pro.js").exists()))
    results.append(check("required CSS file exists", (ROOT / "static/css/namvibe_messages_pro.css").exists()))
    lower_bundle = "\n".join([thread_html, index_html, js, route_src]).lower()
    results.append(check("no fake messages", "fake message" not in lower_bundle and "lorem ipsum" not in lower_bundle))
    results.append(check("no hardcoded demo users", "demo user" not in lower_bundle and "test user" not in lower_bundle))
    results.append(check("message body escaped", "textContent" in js and "escapeText" in js))
    results.append(check("CSRF present for POST", "X-CSRFToken" in js and "csrfHeaders" in js))
    results.append(check("mobile safe-area support", "env(safe-area-inset-bottom)" in css))
    results.append(check("textarea min font size 16px", "font-size: 16px" in css and "textarea" in css))
    for event in ["join:user", "join:thread", "leave:thread", "message:send", "message:ack", "message:delivered", "message:seen", "typing:start", "typing:stop"]:
        results.append(check(f"socket event {event}", event in socket_src or event in js))
    results.append(check("message ordering uses created_at ASC id ASC", "ORDER BY m.created_at ASC, m.id ASC" in thread_service))
    results.append(check("client_temp_id exists", "client_temp_id" in migration and "client_temp_id" in route_src))
    results.append(check("receipt fields exist", all(s in migration for s in ["delivered_at", "seen_at", "chain_message_receipts"])))
    results.append(check("delete-for-everyone logic exists", "deleted_for_everyone_at" in route_src and "This message was deleted" in route_src))
    results.append(check("voice note UI exists", "voice-note-preview" in thread_html and "data-voice-record-button" in thread_html and "MediaRecorder" in js))
    results.append(check("attachment validation exists", "validate_message_attachment" in media_service and "invalid_mime_type" in media_service))
    results.append(check("offline queue exists", "localStorage" in js and "offline_queue" in js))
    results.append(check("group chat routes exist", all(route in routes for route in required_routes[-4:])))
    results.append(check("shop/demo placeholders absent", "hardcoded" not in lower_bundle))
    results.append(check("message body hidden after delete", "CASE WHEN m.deleted_for_everyone_at IS NOT NULL" in thread_service))
    results.append(check("receipt idempotency uses ON CONFLICT", "ON CONFLICT (message_id, user_id)" in receipt_service))
    results.append(check("templates include pro CSS/JS", "namvibe_messages_pro.css" in thread_html + index_html and "namvibe_messages_pro.js" in thread_html + index_html))

    if not all(results):
        raise SystemExit(1)
    print("audit_namvibe_messages_ok")


if __name__ == "__main__":
    main()
