#!/usr/bin/env python3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel_path):
    return (ROOT / rel_path).read_text(encoding="utf-8")


def check(name, ok, detail, failures):
    line = f"{'PASS' if ok else 'FAIL'} [{name}] {detail}"
    print(line)
    if not ok:
        failures.append(f"{name}: {detail}")


def main():
    failures = []

    message_routes = read("api_routes/message_routes.py")
    feature_service = read("services/message_feature_service.py")
    gate_service = read("services/relationship_gate_service.py")
    thread_template = read("templates/messages/thread.html")
    inbox_template = read("templates/messages/index.html")
    pro_js = read("static/js/namvibe_messages_pro.js")

    check(
        "send_route_real_path",
        'fetch("/messages/api/messages/send"' in pro_js and '_uploadXHR.open("POST", "/messages/api/messages/send")' in pro_js,
        "premium JS posts to real message send routes",
        failures,
    )
    check(
        "thread_legacy_submit",
        'data-nv-pro-submit="legacy"' in thread_template,
        "thread template keeps inline send flow authoritative",
        failures,
    )
    check(
        "reply_alias_supported",
        "reply_to_message_id" in message_routes and "parent_message_id" in message_routes,
        "message send route accepts reply aliases",
        failures,
    )
    check(
        "friend_gate_preserved",
        "require_friendship_or_403(profile_id, other_id, \"message\")" in message_routes,
        "message send route still enforces friendship gate",
        failures,
    )
    check(
        "reaction_toggle_endpoint",
        "action == \"toggle\"" in message_routes and "phase29_messages.get_reactions(message_id)" in message_routes,
        "reaction endpoint toggles and returns DB-backed reactions",
        failures,
    )
    check(
        "edit_ownership_check",
        "sender_profile_id = %s" in feature_service and "return {\"ok\": False, \"error\": \"forbidden\"}" in feature_service,
        "edit/delete service rejects non-owner writes",
        failures,
    )
    check(
        "delete_for_everyone_owner_only",
        "deleted_for_everyone = TRUE" in feature_service and "SELECT id FROM chain_messages WHERE id = %s AND sender_profile_id = %s" in feature_service,
        "delete for everyone requires sender ownership",
        failures,
    )
    check(
        "reaction_ui_quick_bar",
        "['❤️','😂','😮','😢','🙏','🔥']" in thread_template,
        "thread UI exposes quick reaction bar",
        failures,
    )
    check(
        "reply_ui_present",
        "reply-preview" in thread_template and "parent_message_id" in thread_template,
        "thread UI renders reply preview state",
        failures,
    )
    check(
        "search_ui_present",
        "thread-search-input" in thread_template and "Search chats" in inbox_template,
        "inbox/thread search surfaces exist",
        failures,
    )
    check(
        "voice_upload_controls",
        "vp-progress" in thread_template and "recording-waveform" in thread_template,
        "voice preview exposes upload progress and waveform targets",
        failures,
    )
    check(
        "mobile_handlers_present",
        "touchstart" in thread_template and "handleSwipe" in thread_template and "visualViewport" in pro_js,
        "mobile swipe and keyboard-safe composer handlers exist",
        failures,
    )
    check(
        "no_fake_messages",
        "INSERT INTO chain_messages" in feature_service and "demo message" not in (message_routes + thread_template + pro_js).lower(),
        "messaging changes use real message tables and no fake message copy",
        failures,
    )
    check(
        "relationship_gate_service_unchanged",
        "def can_message" in gate_service and "def can_call" in gate_service,
        "relationship gate service remains present for privacy checks",
        failures,
    )

    if failures:
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
