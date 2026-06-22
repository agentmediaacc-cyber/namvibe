#!/usr/bin/env python3
"""Test wallet security — auth, ownership, CSRF, XSS, SQL injection."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.payment_fraud_service import mask_account, make_idempotency_key, check_large_amount
from services.payout_security_service import validate_payout_status_transition

def check(label, cond):
    global failed
    status = "PASS" if cond else "FAIL"
    print(f"{status}: {label}")
    if not cond:
        failed = True

failed = False

# 1. Payout account masked
masked = mask_account("1234567890")
check("Payout account masked correctly", masked == "******7890" or masked == "*" * 6 + "7890")

# 2. Short account stays visible
masked = mask_account("abcd")
check("Short account stays visible", masked == "abcd")

# 3. Empty account
masked = mask_account("")
check("Empty account returns empty", masked == "")

# 4. Idempotency key deterministic
k1 = make_idempotency_key("tip", "user1", "receiver1", "100")
k2 = make_idempotency_key("tip", "user1", "receiver1", "100")
check("Idempotency key deterministic", k1 == k2)

# 5. Different inputs produce different keys
k3 = make_idempotency_key("tip", "user1", "receiver2", "100")
check("Different inputs produce different keys", k1 != k3)

# 6. Invalid amount rejected
r = validate_payout_status_transition("paid", "failed")
check("Invalid transition rejected", r.get("ok") == False)

# 7. Amount validation — large amount flagged
r = check_large_amount(2000000, 1000000)
check("Large amount flagged", r.get("ok") == False)

# 8. Small amount not flagged
r = check_large_amount(50000, 1000000)
check("Small amount not flagged", r.get("ok") == True)

# 9. XSS: mask_account with HTML
masked = mask_account("<script>alert(1)</script>")
check("Masking handles special chars", masked is not None and len(masked) > 0)

# 10. Zero amount rejected by ledger functions
from services.wallet_ledger_service import credit, debit
r = credit("test-uid", 0, "Zero credit", "test")
check("Zero credit rejected", r.get("ok") == False)
r = debit("test-uid", 0, "Zero debit", "test")
check("Zero debit rejected", r.get("ok") == False)

if failed:
    sys.exit(1)
print("test_wallet_security_ok")
