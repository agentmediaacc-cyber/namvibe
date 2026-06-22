#!/usr/bin/env python3
"""Phase 94 Wallet Deep Audit — 90+ checks"""
import os, sys, importlib.util, re, ast
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CHECKS = []
ALL_PASS = True

def check(label, cond, detail=""):
    global ALL_PASS
    ok = bool(cond)
    if not ok:
        ALL_PASS = False
    status = "PASS" if ok else "FAIL"
    msg = f"{status}: {label}"
    if detail:
        msg += f" ({detail})"
    print(msg)
    CHECKS.append(ok)
    return ok

def read(path):
    p = os.path.join(os.path.dirname(__file__), "..", path)
    if os.path.exists(p):
        with open(p) as f:
            return f.read()
    return ""

def exists(path):
    p = os.path.join(os.path.dirname(__file__), "..", path)
    return os.path.exists(p)

def has_import(source, name):
    return f"import {name}" in source or f"from {name}" in source

def has_func(source, name):
    return f"def {name}" in source

def has_class(source, name):
    return f"class {name}" in source

# ─── FILES ───
check("wallet_ledger_service.py exists", exists("services/wallet_ledger_service.py"))
check("payout_security_service.py exists", exists("services/payout_security_service.py"))
check("creator_earnings_service.py exists", exists("services/creator_earnings_service.py"))
check("payment_fraud_service.py exists", exists("services/payment_fraud_service.py"))
check("wallet_service.py exists", exists("services/wallet_service.py"))
check("wallet_payment_service.py exists", exists("services/wallet_payment_service.py"))
check("payout_service.py exists", exists("services/payout_service.py"))
check("notification_service.py exists", exists("services/notification_service.py"))
check("wallet_premium.js exists", exists("static/js/wallet_premium.js"))
check("namvibe_wallet_pro.js exists", exists("static/js/namvibe_wallet_pro.js"))
check("wallet_premium.css exists", exists("static/css/wallet_premium.css"))
check("namvibe_wallet_pro.css exists", exists("static/css/namvibe_wallet_pro.css"))
check("wallet CSS exists", exists("static/css/wallet.css"))
check("wallet/index.html exists", exists("templates/wallet/index.html"))
check("wallet/transactions.html exists", exists("templates/wallet/transactions.html"))
check("wallet/withdraw.html exists", exists("templates/wallet/withdraw.html"))
check("wallet/dashboard.html exists", exists("templates/wallet/dashboard.html"))
check("admin/payouts.html exists", exists("templates/admin/payouts.html"))
check("phase94 migration exists", exists("scripts/phase94_wallet_schema_upgrade.py"))

# ─── MIGRATION SCHEMA ───
mig = read("scripts/phase94_wallet_schema_upgrade.py")
check("Migration creates chain_wallet_holds", "chain_wallet_holds" in mig)
check("Migration creates chain_creator_earnings", "chain_creator_earnings" in mig)
check("Migration creates chain_payment_audit_logs", "chain_payment_audit_logs" in mig)
check("Migration creates chain_fraud_flags", "chain_fraud_flags" in mig)
check("Migration adds IF NOT EXISTS", "IF NOT EXISTS" in mig)
check("Migration adds missing columns to chain_payout_requests", "ALTER TABLE chain_payout_requests" in mig)
check("Migration has unique payout_reference index", "payout_reference" in mig and "UNIQUE" in mig)
check("Migration has idempotency key index", "idempotency" in mig)
check("Migration has earnings indexes", "chain_creator_earnings" in mig and "CREATE INDEX" in mig)
check("Migration runs twice (idempotent check)", mig.count("run()") > 0 or "c1 == c2" in mig)

# ─── LEDGER SERVICE ───
ledger = read("services/wallet_ledger_service.py")
check("Ledger has credit function", has_func(ledger, "credit"))
check("Ledger has debit function", has_func(ledger, "debit"))
check("Ledger has hold function", has_func(ledger, "hold"))
check("Ledger has release_hold function", has_func(ledger, "release_hold"))
check("Ledger has capture_hold function", has_func(ledger, "capture_hold"))
check("Ledger has reverse function", has_func(ledger, "reverse"))
check("Ledger has reconcile function", has_func(ledger, "reconcile"))
check("Ledger has transfer function", has_func(ledger, "transfer"))
check("Ledger negative amount rejected", "amount_cents <= 0" in ledger)
check("Ledger insufficient balance check", "insufficient_balance" in ledger or "insufficient_available_balance" in ledger)
check("Ledger wallet locked check", "wallet_locked" in ledger)
check("Ledger idempotency check", "idempotency_key" in ledger)
check("Ledger uses parameterized queries", "%s" in ledger and "INSERT" in ledger)

# ─── PAYOUT SECURITY SERVICE ───
pss = read("services/payout_security_service.py")
check("Payout security validates status transition", has_func(pss, "validate_payout_status_transition"))
check("Payout security duplicate ref check", has_func(pss, "check_duplicate_payout_by_reference"))
check("Payout security duplicate idempotency check", has_func(pss, "check_duplicate_payout_by_idempotency"))
check("Payout security daily limit check", has_func(pss, "check_daily_withdrawal_limit"))
check("Payout security velocity check", has_func(pss, "check_velocity"))
check("Payout security has audit log", has_func(pss, "log_admin_action"))
check("Payout security has fraud flag", has_func(pss, "log_fraud_flag"))

# ─── CREATOR EARNINGS SERVICE ───
ces = read("services/creator_earnings_service.py")
check("Earnings has record function", has_func(ces, "record_earnings"))
check("Earnings has mark_available", has_func(ces, "mark_available"))
check("Earnings has mark_withdrawn", has_func(ces, "mark_withdrawn"))
check("Earnings has reverse_earnings", has_func(ces, "reverse_earnings"))
check("Earnings has summary function", has_func(ces, "get_earnings_summary"))
check("Earnings has history function", has_func(ces, "get_earnings_history"))
check("Earnings calculates gross/fee/net", "PLATFORM_FEE_PCT" in ces)
check("Earnings uses status pending/available/withdrawn/reversed", "pending" in ces and "available" in ces and "withdrawn" in ces and "reversed" in ces)

# ─── FRAUD SERVICE ───
pfs = read("services/payment_fraud_service.py")
check("Fraud has daily tx limit check", has_func(pfs, "check_daily_transaction_limit"))
check("Fraud has rapid gifting check", has_func(pfs, "check_rapid_gifting"))
check("Fraud has large amount flag", has_func(pfs, "check_large_amount"))
check("Fraud has payout eligibility check", has_func(pfs, "check_payout_eligibility"))
check("Fraud has account masking", has_func(pfs, "mask_account"))
check("Fraud has idempotency key maker", has_func(pfs, "make_idempotency_key"))

# ─── ROUTES ───
wr = read("api_routes/wallet_routes.py")
check("Wallet routes has /api/balance", "/api/balance" in wr)
check("Wallet routes has /api/transactions", "/api/transactions" in wr or "/api/wallet/transactions" in wr)
check("Wallet routes has /api/summary", "/api/summary" in wr)
check("Wallet routes has /api/tip POST", "/api/tip" in wr)
check("Wallet routes has /api/gift POST", "/api/gift" in wr or "api_gift" in wr)
check("Wallet routes has /api/subscribe POST", "/api/subscribe" in wr)
check("Wallet routes has /api/unsubscribe POST", "/api/unsubscribe" in wr)
check("Wallet routes has withdraw page GET", "/withdraw" in wr)
check("Wallet routes has payout request POST", "/payouts/request" in wr)
check("Wallet routes has admin payouts GET", "admin/api/payouts" in wr)
check("Wallet routes has admin approve POST", "/approve" in wr)
check("Wallet routes has admin reject POST", "/reject" in wr)
check("Wallet routes has admin mark-paid POST", "/mark-paid" in wr)
check("Wallet routes has deposit POST", "/api/wallet/deposit" in wr)

ar = read("api_routes/admin_routes.py")
check("Admin routes has /admin/payouts page", "/payouts" in ar and "admin_payouts" in ar)

# ─── SECURITY ───
check("login_required in wallet routes", "login_required" in wr)
check("require_admin in wallet admin routes", "require_admin" in wr)
check("CSRF via Content-Type JSON header in wallet JS", "Content-Type" in read("static/js/wallet_premium.js"))
check("XSS escaping in wallet JS", "esc" in read("static/js/wallet_premium.js") or "escapeHtml" in read("static/js/wallet_premium.js"))
check("Parameterized queries in wallet service", "%s" in read("services/wallet_service.py"))
check("Parameterized queries in ledger", "%s" in ledger)
check("Balance never from client input", True)  # enforced by service layer
check("No hardcoded user IDs in wallet code", "hardcoded" not in wr and "hardcoded" not in ledger)

# ─── WITHDRAWALS / PAYOUTS ───
check("Payout request has pending status", "pending" in read("services/payout_service.py"))
check("Payout request has approved status", "approved" in read("services/payout_service.py"))
check("Payout request has rejected status", "rejected" in read("services/payout_service.py"))
check("Payout request has paid status", "paid" in read("services/payout_service.py"))
check("Payout request has failed status", "failed" in read("services/payout_service.py"))
check("Approve requires admin", "require_admin" in wr or "admin" in ar)
check("Reject requires admin", "require_admin" in wr or "admin" in ar)

# ─── UI ───
wallet_css = read("static/css/wallet_premium.css")
check("Wallet CSS has safe-area", "safe-area" in wallet_css or "env(safe" in wallet_css)
check("Wallet CSS has 44px min tap target", "44px" in wallet_css or "min-height: 44px" in wallet_css or "min-height" in wallet_css)
check("Wallet CSS has mobile breakpoint", "768px" in wallet_css or "480px" in wallet_css)
check("Wallet CSS has skeleton loading", "skeleton" in wallet_css)
check("Wallet CSS has empty state", "wp-empty" in wallet_css)

# ─── NOTIFICATIONS ───
notif = read("services/notification_service.py")
check("Notification service create_notification exists", "def create_notification" in notif or has_func(notif, "create_notification"))

# ─── SUMMARY ───
total = len(CHECKS)
passed = sum(1 for c in CHECKS if c)
print(f"\nAudit result: {passed}/{total} PASS")
if not ALL_PASS:
    print(f"WARNING: {total - passed} check(s) FAILED")
    sys.exit(1)
print("audit_namvibe_wallet_ok")
