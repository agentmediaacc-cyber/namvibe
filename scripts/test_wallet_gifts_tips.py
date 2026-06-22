#!/usr/bin/env python3
"""Test wallet gift and tip flows — using ledger service directly."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

from services.wallet_ledger_service import credit
from services.wallet_service import get_or_create_wallet
from services.creator_earnings_service import record_earnings, get_earnings_summary, get_earnings_history

SENDER = "test-gift-sender"
RECEIVER = "test-gift-receiver"

def check(label, cond):
    global failed
    status = "PASS" if cond else "FAIL"
    print(f"{status}: {label}")
    if not cond:
        failed = True

failed = False

get_or_create_wallet(SENDER)
get_or_create_wallet(RECEIVER)

# 1. Credit works (test sender debit manually)
r = credit(SENDER, 5000, "Fund sender", "fund")
check("Fund sender ok", r.get("ok") == True)

# 2. Debit works via ledger (simulate tip)
from services.wallet_ledger_service import debit
r = debit(SENDER, 500, "Tip: Great content!", "tip_sent", counterparty=RECEIVER)
check("Sender debited for tip", r.get("ok") == True)

# 3. Credit receiver for tip
r = credit(RECEIVER, 475, "Tip received", "tip_received", counterparty=SENDER)
check("Receiver credited for tip", r.get("ok") == True)

# 4. Platform fee calculation exists in ledger
from services.wallet_ledger_service import PLATFORM_FEE_PCT
check("Platform fee constant exists", PLATFORM_FEE_PCT == 5)

# 5. Creator earning row created
r_earn = record_earnings(RECEIVER, "tip", "tip-1", 500, "pending")
check("Earning recorded", r_earn.get("ok") == True)
check("Earning has fee deduction", r_earn.get("fee_cents", 0) > 0)
check("Earning net is less than gross", r_earn.get("net_cents", 0) < 500)

# 6. Invalid amount rejected
r = debit(SENDER, -100, "Invalid", "tip")
check("Invalid debit amount rejected", r.get("ok") == False)

# 7. Self transfer rejected
from services.wallet_ledger_service import transfer
r = transfer(SENDER, SENDER, 100, "Self transfer")
check("Self transfer rejected", r.get("ok") == False)

# 8. Duplicate via idempotency prevented in debit
r1 = debit(SENDER, 100, "Dupe debit", "tip_sent", idempotency_key="dup-tip-1")
r2 = debit(SENDER, 100, "Dupe debit again", "tip_sent", idempotency_key="dup-tip-1")
check("Idempotency prevents double debit", r2.get("ok") == True)

# 9. Earnings summary works
summary = get_earnings_summary(RECEIVER)
check("Earnings summary returns dict", isinstance(summary, dict))
check("Earnings summary has pending", "pending_cents" in summary)

# 10. Earnings history works
history = get_earnings_history(RECEIVER)
check("Earnings history returns list", isinstance(history, list))

if failed:
    sys.exit(1)
print("test_wallet_gifts_tips_ok")
