#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("FLASK_ENV", "development")

import services.message_feature_service as mfs
import services.payout_service as payout_service

SENDER_ID = "11111111-1111-4111-8111-111111111111"
RECEIVER_ID = "22222222-2222-4222-8222-222222222222"
THIRD_ID = "33333333-3333-4333-8333-333333333333"


def main():
    failures = []

    balances = {SENDER_ID: 1000, RECEIVER_ID: 100}
    seen = {}

    def fake_transfer(sender, receiver, amount, description="", idempotency_key=None):
        key = idempotency_key or f"{sender}:{receiver}:{amount}"
        if key in seen:
            return {"ok": True, "transaction_id": seen[key], "idempotent": True}
        if balances[sender] < amount:
            return {"ok": False, "error": "insufficient_balance"}
        balances[sender] -= amount
        balances[receiver] += amount
        txid = f"tx-{len(seen)+1}"
        seen[key] = txid
        return {"ok": True, "transaction_id": txid, "idempotent": False}

    with patch.object(mfs, "_thread_member_ids", return_value=[SENDER_ID, RECEIVER_ID]), \
         patch("services.wallet_ledger_service.transfer", side_effect=fake_transfer), \
         patch.object(mfs, "emit_to_thread", lambda *args, **kwargs: None), \
         patch.object(mfs, "emit_to_profile", lambda *args, **kwargs: None):
        ok = mfs.wallet_send("11111111-1111-4111-8111-aaaaaaaaaaaa", SENDER_ID, RECEIVER_ID, 200, "test", idempotency_key="dup-1")
        if not ok.get("ok"):
            failures.append("valid transfer should succeed")
        dup = mfs.wallet_send("11111111-1111-4111-8111-aaaaaaaaaaaa", SENDER_ID, RECEIVER_ID, 200, "test", idempotency_key="dup-1")
        if not dup.get("ok") or not dup.get("idempotent"):
            failures.append("duplicate transfer should be idempotent")
        if balances[SENDER_ID] != 800 or balances[RECEIVER_ID] != 300:
            failures.append("duplicate transfer should not double-debit or double-credit")
        fail = mfs.wallet_send("11111111-1111-4111-8111-aaaaaaaaaaaa", SENDER_ID, RECEIVER_ID, 5000, "too-much", idempotency_key="dup-2")
        if fail.get("ok") or fail.get("error") != "insufficient_balance":
            failures.append("insufficient balance should fail")

    split_calls = []
    reversals = []

    def fake_wallet_send(thread_id, sender_profile_id, recipient_profile_id, amount, note="", idempotency_key=None):
        split_calls.append((recipient_profile_id, amount, idempotency_key))
        if recipient_profile_id == THIRD_ID:
            return {"ok": False, "error": "insufficient_balance"}
        return {"ok": True, "transaction_id": f"split-{len(split_calls)}", "idempotent": False}

    def fake_reverse(profile_id, amount_cents, **kwargs):
        reversals.append((profile_id, amount_cents))
        return {"ok": True}

    with patch.object(mfs, "_thread_member_ids", return_value=[SENDER_ID, RECEIVER_ID, THIRD_ID]), \
         patch.object(mfs, "_db_available", return_value=False), \
         patch.object(mfs, "wallet_send", side_effect=fake_wallet_send), \
         patch("services.wallet_ledger_service.reverse", side_effect=fake_reverse), \
         patch.object(mfs, "emit_to_thread", lambda *args, **kwargs: None), \
         patch.object(mfs, "emit_to_profile", lambda *args, **kwargs: None):
        split_fail = mfs.wallet_split("11111111-1111-4111-8111-bbbbbbbbbbbb", SENDER_ID, 300, [RECEIVER_ID, THIRD_ID], idempotency_key="split-1")
        if split_fail.get("ok") or split_fail.get("error") != "insufficient_balance":
            failures.append("split should fail atomically when one recipient transfer fails")
        if reversals != [(SENDER_ID, 150), (RECEIVER_ID, 150)]:
            failures.append("failed split should rollback the already applied leg once")
        duplicate = mfs.wallet_split("11111111-1111-4111-8111-bbbbbbbbbbbb", SENDER_ID, 300, [RECEIVER_ID, RECEIVER_ID], idempotency_key="split-dup")
        if duplicate.get("ok") or duplicate.get("error") != "duplicate_recipient":
            failures.append("split should reject duplicate recipients")

    success_calls = []

    def fake_wallet_send_success(thread_id, sender_profile_id, recipient_profile_id, amount, note="", idempotency_key=None):
        success_calls.append((recipient_profile_id, amount, idempotency_key))
        return {"ok": True, "transaction_id": f"ok-{len(success_calls)}", "idempotent": False}

    with patch.object(mfs, "_thread_member_ids", return_value=[SENDER_ID, RECEIVER_ID, THIRD_ID]), \
         patch.object(mfs, "_db_available", return_value=False), \
         patch.object(mfs, "wallet_send", side_effect=fake_wallet_send_success), \
         patch("services.wallet_ledger_service.reverse", side_effect=fake_reverse), \
         patch.object(mfs, "emit_to_thread", lambda *args, **kwargs: None), \
         patch.object(mfs, "emit_to_profile", lambda *args, **kwargs: None):
        first = mfs.wallet_split("11111111-1111-4111-8111-cccccccccccc", SENDER_ID, 300, [RECEIVER_ID, THIRD_ID], idempotency_key="split-2")
        second = mfs.wallet_split("11111111-1111-4111-8111-cccccccccccc", SENDER_ID, 300, [RECEIVER_ID, THIRD_ID], idempotency_key="split-2")
        if not first.get("ok") or not second.get("ok") or not second.get("idempotent"):
            failures.append("successful split should be idempotent on duplicate submission")
        if len(success_calls) != 2:
            failures.append("idempotent split should not replay transfer legs")

    payout_row = {"id": "p1", "profile_id": "creator-1", "amount_cents": 250, "status": "pending_review"}
    wallet = {"balance_cents": 750}
    refunded = []

    def fake_fast_query(sql, params, default=None):
        if "status IN ('pending', 'pending_review')" in sql:
            return [dict(payout_row)] if payout_row["status"] in {"pending", "pending_review"} and params[0] == "p1" else []
        if "status = 'approved'" in sql:
            return [dict(payout_row)] if payout_row["status"] == "approved" and params[0] == "p1" else []
        return default or []

    def fake_write_query(sql, params):
        if "SET status = 'rejected'" in sql and payout_row["status"] in {"pending", "pending_review"}:
            payout_row["status"] = "rejected"
        elif "SET status = 'approved'" in sql and payout_row["status"] in {"pending", "pending_review"}:
            payout_row["status"] = "approved"
        elif "SET status = 'paid'" in sql and payout_row["status"] == "approved":
            payout_row["status"] = "paid"
        return []

    def fake_credit(profile_id, amount_cents, **kwargs):
        refunded.append((profile_id, amount_cents))
        wallet["balance_cents"] += amount_cents
        return {"ok": True, "balance_cents": wallet["balance_cents"], "transaction_id": "refund-1"}

    def fake_debit(profile_id, amount_cents, **kwargs):
        wallet["balance_cents"] -= amount_cents
        return {"ok": True, "balance_cents": wallet["balance_cents"], "transaction_id": "debit-1"}

    with patch.object(payout_service, "_db_available", return_value=True), \
         patch.object(payout_service, "fast_query", side_effect=fake_fast_query), \
         patch.object(payout_service, "write_query", side_effect=fake_write_query), \
         patch.object(payout_service, "get_wallet", return_value=wallet), \
         patch("services.wallet_service.credit_wallet", side_effect=fake_credit), \
         patch.object(payout_service, "debit_wallet", side_effect=fake_debit), \
         patch.object(payout_service, "emit_to_profile", lambda *args, **kwargs: None), \
         patch.object(payout_service, "create_notification", lambda *args, **kwargs: None):
        rej1 = payout_service.reject_payout("p1", "nope")
        rej2 = payout_service.reject_payout("p1", "nope-again")
        if not rej1.get("ok"):
            failures.append("first reject should succeed")
        if rej2.get("ok"):
            failures.append("second reject should not succeed")
        if refunded != [("creator-1", 250)]:
            failures.append("rejected payout should refund exactly once")

        payout_row["status"] = "pending_review"
        wallet["balance_cents"] = 750
        refunded.clear()
        app = payout_service.approve_payout("p1")
        paid1 = payout_service.mark_payout_paid("p1")
        paid2 = payout_service.mark_payout_paid("p1")
        if not app.get("ok") or not paid1.get("ok"):
            failures.append("approved payout should be payable once")
        if paid2.get("ok"):
            failures.append("second paid action should not succeed")
        if wallet["balance_cents"] != 750:
            failures.append("modern paid payout should not double-debit balance")

    if failures:
        print("FAIL")
        for failure in failures:
            print(failure)
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
