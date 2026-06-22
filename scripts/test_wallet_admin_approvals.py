#!/usr/bin/env python3
"""Test admin payout approval flows."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

from services.payout_security_service import validate_payout_status_transition, log_admin_action

def check(label, cond):
    global failed
    status = "PASS" if cond else "FAIL"
    print(f"{status}: {label}")
    if not cond:
        failed = True

failed = False

# 1. Admin can approve pending
r = validate_payout_status_transition("pending", "approved")
check("Admin can approve pending", r.get("ok") == True)

# 2. Admin can reject pending
r = validate_payout_status_transition("pending", "rejected")
check("Admin can reject pending", r.get("ok") == True)

# 3. Admin can mark paid from approved
r = validate_payout_status_transition("approved", "paid")
check("Admin can mark paid from approved", r.get("ok") == True)

# 4. Admin can mark failed from approved
r = validate_payout_status_transition("approved", "failed")
check("Admin can mark failed from approved", r.get("ok") == True)

# 5. Invalid transition rejected
r = validate_payout_status_transition("pending", "paid")
check("Cannot skip approved step", r.get("ok") == False)

r = validate_payout_status_transition("rejected", "approved")
check("Rejected cannot be approved", r.get("ok") == False)

# 6. Admin audit log created (function exists)
check("log_admin_action function exists", "log_admin_action" in open(os.path.join(os.path.dirname(__file__), "..", "services/payout_security_service.py")).read())

# 7. Dashboard counts (function signature check)
from services.creator_earnings_service import get_earnings_summary
summary = get_earnings_summary("test-admin-earnings")
check("Earnings summary returns dict", isinstance(summary, dict))
check("Earnings summary has expected keys", "pending_cents" in summary and "available_cents" in summary)

if failed:
    sys.exit(1)
print("test_wallet_admin_approvals_ok")
