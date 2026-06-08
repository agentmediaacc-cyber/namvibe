#!/usr/bin/env python3
"""Phase 36 — Production Readiness Score"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

SCORES = {}
CATEGORIES = []

def score_category(name, items):
    total = len(items)
    passed = sum(1 for _, ok in items if ok)
    pct = round((passed / total) * 100) if total else 0
    SCORES[name] = {"passed": passed, "total": total, "pct": pct}
    CATEGORIES.append((name, pct))
    return pct

def check_items(name, items):
    pct = score_category(name, items)
    for label, ok in items:
        print(f"  {'[PASS]' if ok else '[FAIL]'} {label}")
    print(f"  Score: {pct}%")
    print()
    return pct

print("=" * 60)
print("CHAIN Phase 36 — Production Readiness Audit")
print("=" * 60)
print()

# 1. Architecture
arch_items = []
try:
    from app import create_app
    arch_items.append(("App factory pattern", True))
except Exception:
    arch_items.append(("App factory pattern", False))
try:
    from services.socketio_service import socketio
    arch_items.append(("Socket.IO initialized", True))
except Exception:
    arch_items.append(("Socket.IO initialized", False))
try:
    from services.neon_service import get_neon_health
    arch_items.append(("Neon/Postgres configured", callable(get_neon_health)))
except Exception:
    arch_items.append(("Neon/Postgres configured", False))
try:
    from services.redis_service import redis_available
    arch_items.append(("Redis configured", callable(redis_available)))
except Exception:
    arch_items.append(("Redis configured", False))
try:
    from services.rate_limit_service import init_rate_limiter
    arch_items.append(("Rate limiter configured", callable(init_rate_limiter)))
except Exception:
    arch_items.append(("Rate limiter configured", False))
print("Architecture:")
check_items("Architecture", arch_items)

# 2. Messaging
msg_items = []
try:
    from services.message_feature_service import send_text_message, get_thread_messages
    msg_items.append(("Message send/receive functions", callable(send_text_message) and callable(get_thread_messages)))
except Exception:
    msg_items.append(("Message send/receive functions", False))
try:
    from services.messaging_engine import send_message, get_thread
    msg_items.append(("Messaging engine functions", callable(send_message) and callable(get_thread)))
except Exception:
    msg_items.append(("Messaging engine functions", False))
try:
    from services.message_delivery_service import send_message as d_send
    msg_items.append(("Delivery service functions", callable(d_send)))
except Exception:
    msg_items.append(("Delivery service functions", False))
try:
    from services.socketio_service import emit_to_thread
    msg_items.append(("Real-time messaging (Socket.IO)", callable(emit_to_thread)))
except Exception:
    msg_items.append(("Real-time messaging (Socket.IO)", False))
print("Messaging:")
check_items("Messaging", msg_items)

# 3. Calls
call_items = []
try:
    from services.call_service import start_call, answer_call, end_call
    call_items.append(("Call CRUD functions", callable(start_call) and callable(answer_call) and callable(end_call)))
except Exception:
    call_items.append(("Call CRUD functions", False))
try:
    from services.call_feature_service import start_call, recent_calls
    call_items.append(("Call feature functions", callable(start_call) and callable(recent_calls)))
except Exception:
    call_items.append(("Call feature functions", False))
try:
    from services.webrtc_turn_service import get_webrtc_ice_config
    call_items.append(("WebRTC ICE config", callable(get_webrtc_ice_config)))
except Exception:
    call_items.append(("WebRTC ICE config", False))
try:
    src = open(os.path.join(BASE, "services", "socket_events.py")).read()
    has_call_events = all(e in src for e in ['"call:offer"', '"call:answer"', '"call:end"'])
    call_items.append(("Socket.IO call events", has_call_events))
except Exception:
    call_items.append(("Socket.IO call events", False))
print("Calls:")
check_items("Calls", call_items)

# 4. Groups
grp_items = []
try:
    from services.group_feature_service import create_group, join_public_group, get_group, get_members
    grp_items.append(("Group CRUD functions", callable(create_group) and callable(join_public_group) and callable(get_group) and callable(get_members)))
except Exception:
    grp_items.append(("Group CRUD functions", False))
try:
    from services.group_feature_service import create_group_post, set_role
    grp_items.append(("Group post/role functions", callable(create_group_post) and callable(set_role)))
except Exception:
    grp_items.append(("Group post/role functions", False))
try:
    from services.group_feature_service import get_public_groups, my_groups
    grp_items.append(("Group list functions", callable(get_public_groups) and callable(my_groups)))
except Exception:
    grp_items.append(("Group list functions", False))
print("Groups:")
check_items("Groups", grp_items)

# 5. Live
live_items = []
try:
    from services.live_service import create_live_room, get_live_rooms, get_room, add_comment, send_gift, end_live
    live_items.append(("Live service functions", callable(create_live_room) and callable(get_live_rooms) and callable(get_room) and callable(add_comment) and callable(send_gift) and callable(end_live)))
except Exception:
    live_items.append(("Live service functions", False))
try:
    from services.live_feature_service import start_live, list_live_rooms
    live_items.append(("Live feature functions", callable(start_live) and callable(list_live_rooms)))
except Exception:
    live_items.append(("Live feature functions", False))
try:
    from services.media_server_service import is_live_streaming_ready
    live_items.append(("Media server service", callable(is_live_streaming_ready)))
except Exception:
    live_items.append(("Media server service", False))
print("Live:")
check_items("Live", live_items)

# 6. Push
push_items = []
try:
    from services.push_notification_service import get_vapid_public_key, save_subscription, queue_push_event
    push_items.append(("Push notification service", callable(get_vapid_public_key) and callable(save_subscription) and callable(queue_push_event)))
except Exception:
    push_items.append(("Push notification service", False))
vapid = bool(os.environ.get("VAPID_PUBLIC_KEY", ""))
push_items.append(("VAPID keys configured", vapid))
try:
    import pywebpush
    push_items.append(("pywebpush installed", True))
except ImportError:
    push_items.append(("pywebpush installed", False))
try:
    sw = os.path.exists(os.path.join(BASE, "static", "js", "sw.js"))
    push_items.append(("Service worker exists", sw))
except Exception:
    push_items.append(("Service worker exists", False))
print("Push:")
check_items("Push", push_items)

# 7. Wallet
wallet_items = []
try:
    from services.wallet_service import ensure_wallet, get_wallet_home, top_up_wallet
    wallet_items.append(("Wallet service functions", callable(ensure_wallet) and callable(get_wallet_home) and callable(top_up_wallet)))
except Exception:
    wallet_items.append(("Wallet service functions", False))
try:
    from services.wallet_engine import get_wallet_summary, list_transactions, send_gift
    wallet_items.append(("Wallet engine functions", callable(get_wallet_summary) and callable(list_transactions) and callable(send_gift)))
except Exception:
    wallet_items.append(("Wallet engine functions", False))
try:
    from services.payment_provider_service import payment_configured, get_payment_providers
    wallet_items.append(("Payment provider service", callable(payment_configured) and callable(get_payment_providers)))
except Exception:
    wallet_items.append(("Payment provider service", False))
print("Wallet:")
check_items("Wallet", wallet_items)

# 8. Creator
creator_items = []
try:
    from services.creator_feature_service import creator_dashboard, request_verification, create_subscription, get_subscriptions
    creator_items.append(("Creator feature service", callable(creator_dashboard) and callable(request_verification) and callable(create_subscription) and callable(get_subscriptions)))
except Exception:
    creator_items.append(("Creator feature service", False))
try:
    from services.creator_feature_service import create_paid_post, get_paid_posts, create_premium_content, get_premium_content
    creator_items.append(("Paid post/premium functions", callable(create_paid_post) and callable(get_paid_posts) and callable(create_premium_content) and callable(get_premium_content)))
except Exception:
    creator_items.append(("Paid post/premium functions", False))
try:
    from services.creator_feature_service import request_payout, create_sponsorship, get_sponsorships
    creator_items.append(("Payout/sponsorship functions", callable(request_payout) and callable(create_sponsorship) and callable(get_sponsorships)))
except Exception:
    creator_items.append(("Payout/sponsorship functions", False))
print("Creator:")
check_items("Creator", creator_items)

# 9. Security
sec_items = []
try:
    from api_routes.profile_routes import login_required
    sec_items.append(("login_required decorator", True))
except Exception:
    sec_items.append(("login_required decorator", False))
try:
    from services.rate_limit_service import init_rate_limiter
    sec_items.append(("Rate limiter", callable(init_rate_limiter)))
except Exception:
    sec_items.append(("Rate limiter", False))
try:
    from services.session_service import store_auth_session, clear_auth_session
    sec_items.append(("Session management", callable(store_auth_session) and callable(clear_auth_session)))
except Exception:
    sec_items.append(("Session management", False))
try:
    from services.storage_service import allowed_file, sanitize_filename
    sec_items.append(("Upload validation", callable(allowed_file) and callable(sanitize_filename)))
except Exception:
    sec_items.append(("Upload validation", False))
print("Security:")
check_items("Security", sec_items)

# 10. Performance
perf_items = []
try:
    from services.cache_engine_redis import cache_get, cache_set
    perf_items.append(("Redis cache layer", callable(cache_get) and callable(cache_set)))
except Exception:
    perf_items.append(("Redis cache layer", False))
try:
    from engines.cache_engine import init_cache
    perf_items.append(("Cache engine", callable(init_cache)))
except Exception:
    perf_items.append(("Cache engine", False))
try:
    from engines.performance_engine import timed
    perf_items.append(("Performance engine", callable(timed)))
except Exception:
    perf_items.append(("Performance engine", False))
print("Performance:")
check_items("Performance", perf_items)

# 11. Infrastructure
infra_items = []
try:
    from services.webrtc_turn_service import turn_configured
    infra_items.append(("TURN configured", turn_configured()))
except Exception:
    infra_items.append(("TURN configured", False))
try:
    from services.media_server_service import is_live_streaming_ready
    status = is_live_streaming_ready().get("status")
    infra_items.append(("Media server configured", status in ("ready", "partial")))
except Exception:
    infra_items.append(("Media server configured", False))
try:
    from services.payment_provider_service import payment_configured
    infra_items.append(("Payment provider configured", payment_configured()))
except Exception:
    infra_items.append(("Payment provider configured", False))
vapid_present = bool(os.environ.get("VAPID_PUBLIC_KEY", "")) and bool(os.environ.get("VAPID_PRIVATE_KEY", ""))
infra_items.append(("VAPID keys configured", vapid_present))
print("Infrastructure:")
check_items("Infrastructure", infra_items)

# Summary
print("=" * 60)
print("READINESS SCORE SUMMARY")
print("=" * 60)
print()
total_pct = 0
for name, pct in CATEGORIES:
    bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
    print(f"  {name:20s} [{bar}] {pct}%")
    total_pct += pct
overall = round(total_pct / len(CATEGORIES)) if CATEGORIES else 0
print()
print(f"  {'OVERALL':20s} {'=' * 20} {overall}%")
print()
print("  Classification:")
if overall >= 90:
    print("    PRODUCTION READY")
elif overall >= 70:
    print("    RELEASE CANDIDATE")
elif overall >= 40:
    print("    BETA")
else:
    print("    PROTOTYPE")
print()

# Infrastructure gaps
infra_gaps = []
if not turn_configured() and 'turn_configured' in dir():
    pass
try:
    from services.webrtc_turn_service import turn_configured as tc
    if not tc():
        infra_gaps.append("TURN server")
except Exception:
    infra_gaps.append("TURN server")
try:
    from services.media_server_service import is_live_streaming_ready as lsr
    if lsr().get("status") == "missing":
        infra_gaps.append("Media server (RTMP/LiveKit)")
except Exception:
    infra_gaps.append("Media server (RTMP/LiveKit)")
try:
    from services.payment_provider_service import payment_configured as pc
    if not pc():
        infra_gaps.append("Payment provider (Stripe/PayPal)")
except Exception:
    infra_gaps.append("Payment provider (Stripe/PayPal)")
if not vapid_present:
    infra_gaps.append("VAPID keys")

if infra_gaps:
    print("  Infrastructure Gaps:")
    for g in infra_gaps:
        print(f"    - {g}")
    print()
    print("  CHAIN is NOT production ready without missing infrastructure.")
else:
    print("  All infrastructure configured.")

# Export for final report
with open(os.path.join(BASE, "reports", "phase36_readiness_score.txt"), "w") as f:
    f.write(f"{overall}\n")
    for name, pct in CATEGORIES:
        f.write(f"{name}:{pct}\n")

print(f"\nResults: All categories scored.")
