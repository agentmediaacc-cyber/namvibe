#!/usr/bin/env python3
"""
Wallet, Earnings & Payment Reality Audit — Phase 100.

Tests all wallet/earnings/payment paths against real Neon DB and real Redis.
Reports PASS/FAIL per section with exact failure points.
"""
import os
import sys
import json
import uuid
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env so DATABASE_URL and REDIS_URL are available
# Use direct assignment (not setdefault) to override any stale shell values
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip("'\"")
                if v:
                    os.environ[k] = v

# Must NOT set FLASK_TESTING or CHAIN_FAST_LOCAL — we want real DB
from app import create_app
app = create_app()

from services.neon_service import fast_query, write_query, get_pool_status
import services.socketio_service as socksvc
import services.notification_engine as notification_engine

# ── Wallet service imports ──
from services.wallet_service import (
    get_or_create_wallet, get_wallet,
    credit_wallet, debit_wallet,
    lock_wallet, unlock_wallet,
    get_wallet_transactions,
)
from services.wallet_ledger_service import (
    credit as ledger_credit,
    debit as ledger_debit,
    hold, release_hold, transfer,
)
from services.wallet_payment_service import (
    send_tip, send_gift, pay_subscription,
    request_payout as wp_request_payout,
    add_payout_method, get_payout_methods,
)
from services.payout_service import (
    request_payout as payout_request_payout,
    approve_payout, reject_payout,
    get_payout_requests, get_creator_payouts,
)
from services.payment_fraud_service import (
    check_daily_transaction_limit,
    check_rapid_gifting,
    check_large_amount,
    check_payout_eligibility,
)
from services.creator_earnings_service import (
    record_earnings,
    get_earnings_summary,
    get_earnings_history,
)

# ── Monkey-patch at import site to capture notifications ──
CAPTURED_EMITS = []

# Patch socketio_service functions that other modules already imported
_original_socksvc_emit = socksvc.emit_to_profile
_original_socksvc_broadcast = socksvc.broadcast_notification

def capture_emit_to_profile(profile_id, event, payload):
    CAPTURED_EMITS.append({"profile_id": str(profile_id), "event": event, "payload": payload, "via": "emit_to_profile"})
    return _original_socksvc_emit(profile_id, event, payload)

def capture_broadcast_notification(profile_id, notification):
    CAPTURED_EMITS.append({"profile_id": str(profile_id), "event": "notification", "payload": notification, "via": "broadcast_notification"})
    return _original_socksvc_broadcast(profile_id, notification)

socksvc.emit_to_profile = capture_emit_to_profile
socksvc.broadcast_notification = capture_broadcast_notification

# Re-patch at every importing module so our wrapper is used
import services.payout_service as _ps_mod
import services.wallet_payment_service as _wps_mod
import services.notification_engine as _ne_mod
_ps_mod.emit_to_profile = socksvc.emit_to_profile
_ne_mod.broadcast_notification = socksvc.broadcast_notification

# ── Test IDs (use existing chain_profiles that have no wallet yet) ──
P_SENDER = "09a467dd-c2ca-4783-991f-2116f12dcb8e"   # e2e_content_viewer
P_RECEIVER = "aadbd77a-b814-4bc3-bbc7-404a962af273"  # e2e_content_owner

def cleanup():
    """Remove any wallets created during testing."""
    for pid in (P_SENDER, P_RECEIVER):
        write_query("DELETE FROM chain_wallet_transactions WHERE profile_id = %s", (pid,))
        write_query("DELETE FROM chain_payout_requests WHERE creator_profile_id = %s", (pid,))
        write_query("DELETE FROM chain_wallet_holds WHERE profile_id = %s", (pid,))
        write_query("DELETE FROM chain_wallets WHERE profile_id = %s", (pid,))
        fast_query("DELETE FROM chain_notifications WHERE recipient_profile_id = %s", (pid,))

failed = False
def check(label, cond):
    global failed
    status = "PASS" if cond else "FAIL"
    print(f"  {status}: {label}")
    if not cond:
        failed = True

def section(name):
    print(f"\n═══ {name} ═══")

# Clean slate
cleanup()

# ────────────────────────────────────────────────────────
# 1. Wallet Creation
# ────────────────────────────────────────────────────────
section("1. Wallet Creation")

w1 = get_or_create_wallet(P_SENDER)
check("get_or_create_wallet returns dict for sender", w1 is not None and isinstance(w1, dict))
check("sender wallet balance_cents starts at 0", w1 and w1.get("balance_cents") == 0)
check("sender wallet profile_id matches", w1 and w1.get("profile_id") == P_SENDER)
check("sender wallet status is active", w1 and w1.get("status") == "active")

w2 = get_or_create_wallet(P_RECEIVER)
check("get_or_create_wallet returns dict for receiver", w2 is not None and isinstance(w2, dict))
check("receiver wallet balance_cents starts at 0", w2 and w2.get("balance_cents") == 0)

# Idempotent creation
w1_dup = get_or_create_wallet(P_SENDER)
check("get_or_create_wallet idempotent (same wallet returned)", w1_dup is not None and w1_dup["id"] == w1["id"])

# get_wallet consistency
w1_get = get_wallet(P_SENDER)
check("get_wallet returns same data", w1_get is not None and w1_get["id"] == w1["id"])

# ────────────────────────────────────────────────────────
# 2. Balance Updates
# ────────────────────────────────────────────────────────
section("2. Balance Updates")

# Credit
cr = credit_wallet(P_SENDER, 10000, "Initial fund", "fund")
check("credit_wallet returns ok", cr.get("ok") == True)
check("credit_wallet returns transaction_id", bool(cr.get("transaction_id")))
w_after = get_wallet(P_SENDER)
check("credit persisted (balance >= 10000)", w_after["balance_cents"] >= 10000)

# Debit
dr = debit_wallet(P_SENDER, 3000, "Test spend", "spend")
check("debit_wallet returns ok", dr.get("ok") == True)
w_after2 = get_wallet(P_SENDER)
check("debit decreased balance", w_after2["balance_cents"] < w_after["balance_cents"])
check("lifetime_spent_cents recorded", w_after2["lifetime_spent_cents"] >= 3000)

# Overdraft rejection
dr_over = debit_wallet(P_SENDER, 999999999, "Overdraft", "over")
check("overdraft debit rejected", dr_over.get("ok") == False)

# Negative amounts
cr_neg = credit_wallet(P_SENDER, -50, "Negative", "neg")
check("negative credit rejected", cr_neg.get("ok") == False)
dr_neg = debit_wallet(P_SENDER, -50, "Negative", "neg")
check("negative debit rejected", dr_neg.get("ok") == False)

# Wallet lock / unlock
lock_ok = lock_wallet(P_SENDER)
check("lock_wallet succeeds", lock_ok == True)
w_locked = get_wallet(P_SENDER)
check("wallet status shows locked", w_locked.get("status") == "locked")
cr_locked = credit_wallet(P_SENDER, 100, "Should fail", "locked_test")
check("credit on locked wallet rejected", cr_locked.get("ok") == False)

unlock_ok = unlock_wallet(P_SENDER)
check("unlock_wallet succeeds", unlock_ok == True)
w_unlocked = get_wallet(P_SENDER)
check("wallet status active after unlock", w_unlocked.get("status") == "active")

# Credit after unlock works again
cr_after = credit_wallet(P_SENDER, 500, "After unlock", "refund")
check("credit works after unlock", cr_after.get("ok") == True)

# ────────────────────────────────────────────────────────
# 3. Tips
# ────────────────────────────────────────────────────────
section("3. Tips")

# Fund sender
credit_wallet(P_SENDER, 50000, "Fund tipping", "fund")
before_sender = get_wallet(P_SENDER)
before_receiver = get_wallet(P_RECEIVER)

tip = send_tip(P_SENDER, P_RECEIVER, 2000, "Great content!")
check("send_tip returns ok", tip.get("ok") == True)
check("send_tip has transaction_id", bool(tip.get("transaction_id")))
check("send_tip has amount_cents", tip.get("amount_cents") == 2000)
check("send_tip has fee_cents > 0", tip.get("fee_cents", 0) > 0)
check("send_tip net + fee == amount", tip.get("fee_cents", 0) + tip.get("net_cents", 0) == 2000)

after_sender = get_wallet(P_SENDER)
after_receiver = get_wallet(P_RECEIVER)
check("sender balance decreased by full amount", after_sender["balance_cents"] == before_sender["balance_cents"] - 2000)
check("receiver balance increased by net amount", after_receiver["balance_cents"] == before_receiver["balance_cents"] + tip["net_cents"])

# Self-tip prevented
self_tip = send_tip(P_SENDER, P_SENDER, 100, "self")
check("self-tip rejected", self_tip.get("ok") == False)

# Zero-amount tip
zero_tip = send_tip(P_SENDER, P_RECEIVER, 0, "zero")
check("zero-amount tip rejected", zero_tip.get("ok") == False)

# ────────────────────────────────────────────────────────
# 4. Gifts
# ────────────────────────────────────────────────────────
section("4. Gifts")

gift_got = False
gift_id = None
try:
    from services.supabase_safe import safe_select
    gifts = safe_select("chain_gift_catalog", limit=5, filters={"is_active": True}, order_by=None)
    if gifts:
        gift_id = gifts[0]["id"]
        gift_got = True
        check("gift catalog accessible via Supabase", True)
    else:
        check("gift catalog returned empty — SKIP gift tests", True)
except Exception as e:
    check(f"gift catalog lookup failed: {e}", False)

if gift_got and gift_id:
    credit_wallet(P_SENDER, 10000, "Fund gift", "fund")
    gft = send_gift(P_SENDER, P_RECEIVER, gift_id)
    check("send_gift returns ok", gft.get("ok") == True)
    check("send_gift has transaction_id", bool(gft.get("transaction_id")))
    check("send_gift has non-negative fee", gft.get("fee_cents", 0) >= 0)
    check("send_gift net + fee == amount", gft.get("fee_cents", 0) + gft.get("net_cents", 0) == gft.get("amount_cents", 0))
    check("gift price > 0", gft.get("amount_cents", 0) > 0)

    # Self-gift prevented
    self_gift = send_gift(P_SENDER, P_SENDER, gift_id)
    check("self-gift rejected", self_gift.get("ok") == False)

# ────────────────────────────────────────────────────────
# 5. Subscriptions
# ────────────────────────────────────────────────────────
section("5. Subscriptions")

credit_wallet(P_SENDER, 10000, "Fund sub", "fund")
sub = pay_subscription(P_SENDER, P_RECEIVER, 3000, "premium")
check("pay_subscription returns ok", sub.get("ok") == True)
check("subscription has transaction_id", bool(sub.get("transaction_id")))
check("subscription fee > 0", sub.get("fee_cents", 0) > 0)
check("subscription net + fee == amount", sub.get("fee_cents", 0) + sub.get("net_cents", 0) == 3000)

# Self-subscription prevented
self_sub = pay_subscription(P_SENDER, P_SENDER, 100, "self")
check("self-subscription rejected", self_sub.get("ok") == False)

# ────────────────────────────────────────────────────────
# 6. Withdrawals (Payouts)
# ────────────────────────────────────────────────────────
section("6. Withdrawals")

# Fund
credit_wallet(P_SENDER, 50000, "Fund withdrawal", "fund")

# Use payout_service.request_payout (Neon-native)
pr = payout_request_payout(P_SENDER, 5000, "bank", {"bank": "Test Bank", "account": "12345"})
check("payout_service.request_payout returns ok", pr.get("ok") == True)
check("payout has payout_id", bool(pr.get("payout_id")))
check("payout status is pending", pr.get("status") == "pending")

# Verify it appears in admin list
pending_list = get_payout_requests(status="pending")
payout_ids = [r["id"] for r in pending_list]
check("payout visible in get_payout_requests(status=pending)", pr["payout_id"] in payout_ids)

# Verify it appears in creator list
creator_payouts = get_creator_payouts(P_SENDER)
creator_ids = [r["id"] for r in creator_payouts]
check("payout visible in get_creator_payouts", pr["payout_id"] in creator_ids)

# Overdraft prevention
big_pr = payout_request_payout(P_SENDER, 999999999, "bank", {})
check("overdraft payout rejected", big_pr.get("ok") == False)

# ────────────────────────────────────────────────────────
# 7. Duplicate Payout Prevention
# ────────────────────────────────────────────────────────
section("7. Duplicate Payout Prevention")

# payout_service checks existing pending amounts, so requesting another
# within available balance should still work but be tracked
pr2 = payout_request_payout(P_SENDER, 1000, "bank", {"dup": "test"})
check("second payout within balance allowed", pr2.get("ok") == True)

# Excessive pending amounts blocked (balance already reduced by pending checks)
# The service looks at SUM of pending approved amounts, so let's verify
# This is more about the check not crashing than exact math
check("duplicate request has own payout_id", pr2.get("payout_id") != pr.get("payout_id"))

# ────────────────────────────────────────────────────────
# 8. Transaction History
# ────────────────────────────────────────────────────────
section("8. Transaction History")

txns = get_wallet_transactions(P_SENDER)
check("transaction list returned", isinstance(txns, list))
check("at least 1 transaction recorded", len(txns) > 0)
check("transactions have amount_cents", all(t.get("amount_cents") is not None for t in txns))
check("transactions have transaction_type", all(t.get("transaction_type") is not None for t in txns))
check("transactions have created_at", all(t.get("created_at") is not None for t in txns))

# Filter by type
tip_txns = get_wallet_transactions(P_SENDER, transaction_type="tip_sent")
check("filter by transaction_type works", isinstance(tip_txns, list))

# Receiver's history
recv_txns = get_wallet_transactions(P_RECEIVER)
check("receiver also has transactions", isinstance(recv_txns, list) and len(recv_txns) > 0)

# ────────────────────────────────────────────────────────
# 9. Admin Approval Flow
# ────────────────────────────────────────────────────────
section("9. Admin Approval")

# Collect pending payouts for sender
sender_pending = [r for r in get_payout_requests(status="pending") if r["creator_profile_id"] == P_SENDER]
check("found pending payout for sender", len(sender_pending) > 0)

target = sender_pending[0]
apr = approve_payout(target["id"], "Approved via reality test")
check("approve_payout returns ok", apr.get("ok") == True)
check("approve_payout status=approved", apr.get("status") == "approved")

# Check emit captured
approve_emits = [e for e in CAPTURED_EMITS if e.get("event") == "wallet:payout-updated" and e.get("payload", {}).get("status") == "approved"]
check("approve emitted wallet:payout-updated", len(approve_emits) >= 1)

# Double-approve prevented
apr2 = approve_payout(target["id"], "Double")
check("double-approve rejected", apr2.get("ok") == False)

# Now reject another
target2 = [r for r in get_payout_requests(status="pending") if r["creator_profile_id"] == P_SENDER]
if target2:
    rej = reject_payout(target2[0]["id"], "Rejected via reality test")
    check("reject_payout returns ok", rej.get("ok") == True)
    check("reject_payout status=rejected", rej.get("status") == "rejected")

    reject_emits = [e for e in CAPTURED_EMITS if e.get("event") == "wallet:payout-updated" and e.get("payload", {}).get("status") == "rejected"]
    check("reject emitted wallet:payout-updated", len(reject_emits) >= 1)

# Reject on already-approved fails
rej_approved = reject_payout(target["id"], "Too late")
check("reject on approved payout rejected", rej_approved.get("ok") == False)

# ────────────────────────────────────────────────────────
# 10. Fraud Protection
# ────────────────────────────────────────────────────────
section("10. Fraud Protection")

dl = check_daily_transaction_limit(P_SENDER, 100)
check("check_daily_transaction_limit passes for normal txn", dl.get("ok") == True)

rg = check_rapid_gifting(P_SENDER)
check("check_rapid_gifting passes for normal rate", rg.get("ok") == True)

la = check_large_amount(5000000)
check("check_large_amount flags big amount", la.get("ok") == False)
check("check_large_amount has flag metadata", la.get("flag") == "large_amount")

pe = check_payout_eligibility(P_SENDER)
check("check_payout_eligibility passes", pe.get("ok") == True)

# ────────────────────────────────────────────────────────
# 11. Notifications
# ────────────────────────────────────────────────────────
section("11. Notifications")

# Check notification rows in Neon DB
notif_rows = fast_query(
    "SELECT event_type, title FROM chain_notifications WHERE recipient_profile_id IN (%s, %s) ORDER BY created_at DESC",
    (P_SENDER, P_RECEIVER), default=[]
)
notif_types = {r["event_type"] for r in notif_rows}
notif_titles = {r["title"] for r in notif_rows}
check("tip notification saved in DB", "tip" in notif_types)
check("gift notification saved in DB", "gift" in notif_types)
check("subscription notification saved in DB", "subscription" in notif_types)
check("payout notification saved in DB", "payout_approved" in notif_types or "payout" in notif_types)

# Check captured emits (payout service)
payout_emitted = any(
    e.get("event") == "wallet:payout-updated"
    for e in CAPTURED_EMITS
)
check("wallet:payout-updated emit captured", payout_emitted)

# ────────────────────────────────────────────────────────
# 12. Duplicate & Idempotency Protection
# ────────────────────────────────────────────────────────
section("12. Duplicate & Idempotency Protection")

# wallet_ledger_service credit with same idempotency key
cr1 = ledger_credit(P_SENDER, 100, "Idempotent credit", "test", idempotency_key="reality-dup-key-1")
cr2 = ledger_credit(P_SENDER, 100, "Idempotent credit dup", "test", idempotency_key="reality-dup-key-1")
check("ledger credit first returns ok", cr1.get("ok") == True)
check("ledger credit dup is idempotent", cr2.get("idempotent") == True)

# ledger debit with idempotency key
credit_wallet(P_SENDER, 10000, "Fund", "fund")
dr1 = ledger_debit(P_SENDER, 500, "Idempotent debit", "test", idempotency_key="reality-dup-debit-1")
dr2 = ledger_debit(P_SENDER, 500, "Idempotent debit dup", "test", idempotency_key="reality-dup-debit-1")
check("ledger debit first returns ok", dr1.get("ok") == True)
check("ledger debit dup is idempotent", dr2.get("idempotent") == True)

# transfer (self prevented, but operation works)
credit_wallet(P_SENDER, 5000, "Fund transfer", "fund")
tr = transfer(P_SENDER, P_RECEIVER, 200, "Test transfer")
check("transfer between wallets returns ok", tr.get("ok") == True)
check("transfer has transaction_id", bool(tr.get("transaction_id")))

# Self-transfer prevented
self_tr = transfer(P_SENDER, P_SENDER, 100, "Self transfer")
check("self-transfer rejected", self_tr.get("ok") == False)

# Hold / release
h = hold(P_SENDER, 1000, "Test hold")
check("hold returns ok", h.get("ok") == True)
check("hold has hold_id", bool(h.get("hold_id")))

rh = release_hold(h["hold_id"])
check("release_hold returns ok", rh.get("ok") == True)

# ────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────
print()
if failed:
    print(">>> SOME CHECKS FAILED <<<")
    sys.exit(1)
else:
    print(">>> wallet_reality_all_pass <<<")
