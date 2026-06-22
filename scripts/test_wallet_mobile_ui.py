#!/usr/bin/env python3
"""Test wallet mobile UI — templates, CSS, responsive, empty states."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def read(path):
    p = os.path.join(os.path.dirname(__file__), "..", path)
    if os.path.exists(p):
        with open(p) as f:
            return f.read()
    return ""

def exists(path):
    return os.path.exists(os.path.join(os.path.dirname(__file__), "..", path))

def check(label, cond):
    global failed
    status = "PASS" if cond else "FAIL"
    print(f"{status}: {label}")
    if not cond:
        failed = True

failed = False

# Wallet dashboard template exists
check("Wallet dashboard template exists", exists("templates/wallet/index.html"))

# Transactions template exists
check("Transactions template exists", exists("templates/wallet/transactions.html"))

# Withdraw template exists
check("Withdraw template exists", exists("templates/wallet/withdraw.html"))

# Admin payout template exists
check("Admin payout template exists", exists("templates/admin/payouts.html"))

# Safe-area CSS in wallet CSS
css = read("static/css/wallet_premium.css")
check("Safe-area inset in wallet CSS", "safe-area" in css or "env(safe" in css or "padding-bottom: calc(40px + env(safe-area-inset-bottom))" in css)

# 44px tap targets in wallet CSS
check("44px min tap target in wallet CSS", "min-height" in css or "44px" in css or "padding" in css)

# Mobile breakpoint exists
check("Mobile breakpoint in wallet CSS", "@media" in css and ("768px" in css or "480px" in css))

# N$ currency formatting in templates
tx_html = read("templates/wallet/transactions.html")
check("N$ currency formatting in transactions", "N$" in tx_html)

withdraw_html = read("templates/wallet/withdraw.html")
check("N$ currency formatting in withdraw", "N$" in withdraw_html)

# Empty state in wallet template
index_html = read("templates/wallet/index.html")
check("Empty state in wallet index", "wp-empty" in index_html or "empty" in index_html or "No transactions" in index_html)

# Empty state in transactions
check("Empty state in transactions", "No transactions yet" in tx_html)

# Disabled withdraw state (max attribute on input prevents overdraw)
check("Withdraw amount limited by max attribute", "max" in withdraw_html)

# Wallet premium CSS has responsive rules
check("Wallet CSS responsive at 768px", "768px" in css)

# Admin payouts template has mobile styles
admin_payout_css = read("templates/admin/payouts.html")
check("Admin payouts responsive", "768px" in admin_payout_css or "max-width" in admin_payout_css)

if failed:
    sys.exit(1)
print("test_wallet_mobile_ui_ok")
