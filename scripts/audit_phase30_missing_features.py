#!/usr/bin/env python3
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / "venv" / "bin" / "python3"
if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), *sys.argv])

sys.path.insert(0, str(ROOT))


SCAN_DIRS = ["api_routes", "services", "templates", "static/js", "static/css", "sql"]
SCAN_FILES = ["app.py"]

FEATURES = {
    "Messaging": {
        "forwarding": ["forward_messages", "chain_message_forwards", "message:forwarded"],
        "multi-select": ["multi_select_action", "multi-select"],
        "reply preview": ["parent_message_id", "reply"],
        "shared media": ["chain_message_shared_items", "shared"],
        "shared docs": ["document", "shared"],
        "shared links": ["item_type", "link"],
        "pinned messages": ["chain_message_pins", "pin_message"],
        "wallpaper": ["chain_message_wallpapers", "save_wallpaper"],
        "drafts": ["chain_message_drafts", "save_draft"],
        "online/offline": ["presence", "heartbeat", "set_online"],
        "last seen": ["last_seen", "presence"],
        "scheduled messages": ["chain_message_scheduled", "schedule_message"],
        "GIF picker": ["gif_url", "gif"],
        "sticker packs": ["get_stickers", "sticker"],
        "emoji picker": ["emoji", "reaction"],
        "encryption status": ["chain_message_encryption_status", "save_encryption_status"],
        "auto-download controls": ["chain_message_autodownload_settings", "autodownload"],
    },
    "Voice notes": {
        "hold to record": ["MediaRecorder", "voice"],
        "lock recording": ["lock", "voice"],
        "pause/resume": ["pause", "resume", "voice"],
        "waveform": ["waveform", "chain_message_voice_notes"],
        "playback speed": ["playback_speed", "voice"],
        "draft voice": ["chain_voice_note_drafts", "save_voice_note_draft"],
        "preview before send": ["preview", "voice"],
        "compression": ["MediaRecorder", "webm"],
    },
    "Calls": {
        "group calls": ["start_group_call", "is_group_call"],
        "conference calls": ["conference", "chain_call_sessions"],
        "add participant": ["add_participant"],
        "screen sharing": ["screen", "getDisplayMedia"],
        "bluetooth detection": ["setSinkId", "audio output"],
        "call waiting": ["chain_call_waiting_events", "record_call_waiting"],
        "network quality": ["chain_call_quality_events", "record_quality_event"],
        "HD/SD toggle": ["hd_enabled", "HD"],
        "camera switch": ["facingMode", "switch"],
        "background blur placeholder": ["background_blur"],
        "noise suppression": ["noise_suppression"],
        "call recording setting placeholder": ["chain_call_recording_settings", "allow_recording"],
        "ringback tones": ["ringback"],
        "ICE/STUN/TURN config check": ["iceServers", "STUN", "TURN"],
        "reconnect logic": ["call:reconnect", "reconnect"],
    },
    "Groups": {
        "moderators": ["moderator", "chain_group_roles"],
        "admins": ["admin", "chain_group_roles"],
        "co-hosts": ["co_host", "chain_group_roles"],
        "announcements": ["chain_group_announcements"],
        "paid access": ["paid_access", "join_fee"],
        "premium-only access": ["premium_only"],
        "group calls": ["allow_group_calls", "group_call"],
        "group live streams": ["chain_group_live_rooms"],
        "group reels": ["chain_group_reels"],
        "marketplace": ["chain_group_marketplace_items"],
        "adverts manager": ["chain_group_adverts"],
        "analytics": ["chain_group_analytics"],
        "verification": ["chain_group_verification"],
    },
    "Live": {
        "WebRTC broadcast hooks": ["webrtc_enabled", "RTCPeerConnection"],
        "RTMP ingest placeholder/settings": ["rtmp_stream_key", "rtmp_enabled"],
        "multi-host": ["guest_request", "cohost"],
        "guest requests": ["chain_live_guest_requests"],
        "polls": ["chain_live_polls"],
        "battles": ["chain_live_battles"],
        "subscriptions": ["chain_creator_subscriptions"],
        "moderation": ["chain_live_moderation_actions"],
        "replay": ["chain_live_replays"],
        "clips": ["chain_live_clips"],
        "shopping": ["chain_live_shopping_items"],
        "leaderboard": ["chain_live_leaderboard"],
    },
    "Creator economy": {
        "subscriptions": ["create_subscription", "chain_creator_subscriptions"],
        "premium content locks": ["create_premium_content", "chain_creator_premium_content"],
        "paid posts": ["create_paid_post", "chain_creator_paid_posts"],
        "payouts": ["request_payout", "chain_creator_payouts"],
        "gift conversion": ["record_gift_conversion", "chain_creator_gift_conversions"],
        "revenue reports": ["create_revenue_report", "chain_creator_revenue_reports"],
        "sponsorships": ["create_sponsorship", "chain_creator_sponsorships"],
        "creator badges": ["award_creator_badge", "chain_creator_badges"],
        "supporter badges": ["award_supporter_badge", "chain_supporter_badges"],
        "top fans": ["upsert_top_fan", "chain_top_fans"],
        "creator ranking": ["upsert_creator_ranking", "chain_creator_rankings"],
    },
}


def read_corpus():
    chunks = {}
    for directory in SCAN_DIRS:
        path = ROOT / directory
        if not path.exists():
            continue
        for file_path in path.rglob("*"):
            if file_path.suffix.lower() not in {".py", ".html", ".js", ".css"}:
                continue
            try:
                chunks[str(file_path.relative_to(ROOT))] = file_path.read_text(errors="ignore")
            except Exception:
                pass
    for file_name in SCAN_FILES:
        path = ROOT / file_name
        if path.exists():
            chunks[file_name] = path.read_text(errors="ignore")
    return chunks


def classify(feature, needles, corpus):
    backend_hits = []
    ui_hits = []
    for path, text in corpus.items():
        hit_count = sum(1 for needle in needles if needle.lower() in text.lower())
        if not hit_count:
            continue
        if path.startswith(("api_routes/", "services/", "app.py", "sql/")):
            backend_hits.append(path)
        elif path.startswith(("templates/", "static/")):
            ui_hits.append(path)
    if backend_hits and ui_hits:
        return "real", sorted(set(backend_hits + ui_hits))[:6]
    if backend_hits:
        return "partial", sorted(set(backend_hits))[:6]
    if ui_hits:
        return "ui_only", sorted(set(ui_hits))[:6]
    return "missing", []


def duplicate_routes():
    from app import app
    seen = {}
    duplicates = []
    for rule in app.url_map.iter_rules():
        methods = tuple(sorted(rule.methods - {"HEAD", "OPTIONS"}))
        key = (rule.rule, methods)
        if key in seen:
            duplicates.append((rule.rule, methods, seen[key], rule.endpoint))
        else:
            seen[key] = rule.endpoint
    return duplicates


def main():
    corpus = read_corpus()
    print("PHASE 30 missing feature audit")
    print("=" * 72)
    for group, features in FEATURES.items():
        print(f"\n{group}")
        print("-" * 72)
        for feature, needles in features.items():
            status, locations = classify(feature, needles, corpus)
            location_text = ", ".join(locations) if locations else "-"
            print(f"{feature}: {status} [{location_text}]")

    dups = duplicate_routes()
    print("\nduplicate routes")
    print("-" * 72)
    if not dups:
        print("none")
    else:
        for rule, methods, first, second in dups:
            print(f"{rule} {methods}: duplicate [{first}, {second}]")

    print("\nexternal infrastructure gates")
    print("-" * 72)
    print("RTMP: settings table/API only unless an RTMP server is configured")
    print("TURN: ICE/TURN can be configured by frontend/server env; dedicated TURN service still required for strict NATs")
    print("payments: creator payouts are request records; provider execution remains external")
    print("GIF/sticker provider: local/static metadata is supported; external provider still required for broad catalogs")
    print("push notifications: provider keys/service required for off-device push")


if __name__ == "__main__":
    main()
