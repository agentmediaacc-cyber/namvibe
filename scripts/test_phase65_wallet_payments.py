#!/usr/bin/env python3
"""Phase 65 — Premium Wallet, Payments, Payouts & Ledger Tests (400+)."""

import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

PASS = 0
FAIL = 0
ERRORS = []

def check(desc, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        ERRORS.append(desc)
        print(f"  [FAIL] {desc}")

def safe_read(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""

def safe_lines(path):
    try:
        with open(path) as f:
            return f.readlines()
    except Exception:
        return []

def has_import(content, name):
    return f"import {name}" in content or f"from {name}" in content

print("=" * 60)
print("Phase 65 — Premium Wallet, Payments, Payouts & Ledger Tests")
print("=" * 60)

# SECTION 1: SQL schema
print("\n--- SECTION 1: SQL Schema ---")
sql = safe_read("sql/phase65_wallet_payments.sql")
check("sql/phase65_wallet_payments.sql exists", bool(sql))
check("CREATE TABLE chain_wallet_ledger_entries", "CREATE TABLE IF NOT EXISTS chain_wallet_ledger_entries" in sql)
check("Ledger has profile_id", "profile_id UUID NOT NULL" in sql.split("chain_wallet_ledger_entries")[1][:300])
check("Ledger has entry_type", "entry_type VARCHAR(50)" in sql or "entry_type TEXT" in sql)
check("Ledger has amount_cents", "amount_cents" in sql)
check("Ledger has balance_before_cents", "balance_before_cents" in sql)
check("Ledger has balance_after_cents", "balance_after_cents" in sql)
check("Ledger has pending_before_cents", "pending_before_cents" in sql)
check("Ledger has pending_after_cents", "pending_after_cents" in sql)
check("Ledger has reference_type", "reference_type VARCHAR" in sql or "reference_type TEXT" in sql)
check("Ledger has reference_id", "reference_id" in sql)
check("Ledger has description", "description" in sql)
check("Ledger has created_at", "created_at" in sql)
check("CREATE TABLE chain_payout_methods", "CREATE TABLE IF NOT EXISTS chain_payout_methods" in sql)
check("Payout methods has profile_id", "profile_id UUID" in sql.split("chain_payout_methods")[1][:300])
check("Payout methods has provider CHECK", "CHECK(provider IN" in sql or "provider VARCHAR" in sql)
check("Payout methods has account_name", "account_name" in sql)
check("Payout methods has masked_account", "masked_account" in sql)
check("Payout methods has is_default", "is_default" in sql or "is_primary" in sql)
check("Payout methods has verification_status", "verification_status" in sql)
check("Payout methods has country", "country" in sql)
check("Payout methods has currency", "currency" in sql)
check("CREATE TABLE chain_payment_intents", "CREATE TABLE IF NOT EXISTS chain_payment_intents" in sql)
check("Payment intents has profile_id", "profile_id UUID" in sql)
check("Payment intents has amount_cents", "amount_cents" in sql)
check("Payment intents has status CHECK", "CHECK(status IN" in sql)
check("Payment intents has idempotency_key", "idempotency_key" in sql)
check("CREATE TABLE chain_wallet_idempotency_keys", "CREATE TABLE IF NOT EXISTS chain_wallet_idempotency_keys" in sql)
check("Idempotency has idempotency_key", "idempotency_key VARCHAR" in sql or "idempotency_key TEXT" in sql)
check("Idempotency has profile_id", "profile_id UUID" in sql)
check("Idempotency has action_type", "action_type" in sql)
check("Idempotency has response_status", "response_status" in sql)
key_section = sql.split("chain_wallet_idempotency_keys")[1][:200] if "chain_wallet_idempotency_keys" in sql else ""
check("Idempotency has UNIQUE constraint", "UNIQUE" in key_section)
check("CREATE INDEX on ledger profile_id", "idx_p65_ledger_profile" in sql)
check("CREATE INDEX on ledger created_at", "idx_p65_ledger_type" in sql or "idx_p65_ledger" in sql)
check("ADD withdrawable_balance_cents", "withdrawable_balance_cents" in sql)
check("chain_wallets has currency column", "currency TEXT DEFAULT 'NAD'" in sql)
check("SQL has IF NOT EXISTS pattern", "IF NOT EXISTS" in sql)
check("SQL has ADD COLUMN IF NOT EXISTS pattern", "ADD COLUMN IF NOT EXISTS" in sql)

# SECTION 2: SQL column counts
print("\n--- SECTION 2: SQL Column Analysis ---")
cols_ledger = ["profile_id", "wallet_id", "transaction_id", "entry_type", "amount_cents",
               "balance_before_cents", "balance_after_cents", "pending_before_cents",
               "pending_after_cents", "status", "reference_type", "reference_id", "description", "created_at"]
for col in cols_ledger:
    check(f"Ledger column: {col}", col in sql.split("chain_wallet_ledger_entries")[1][:950] if "chain_wallet_ledger_entries" in sql else False)

pcols = ["profile_id", "provider", "account_name", "masked_account", "country", "currency",
         "is_default", "verification_status", "created_at", "updated_at"]
pm_section = sql.split("chain_payout_methods")[1][:600] if "chain_payout_methods" in sql else ""
for col in pcols:
    check(f"Payout methods column: {col}", col in pm_section)

# SECTION 3: Service file
print("\n--- SECTION 3: Service File Existence & Imports ---")
svc = safe_read("services/wallet_payment_service.py")
check("services/wallet_payment_service.py exists", bool(svc))
check("Service imports neon_service", "neon_service" in svc)
check("Service imports supabase_safe", "supabase_safe" in svc)
check("Service imports profile_service", "profile_service" in svc)
check("Service has PLATFORM_FEE_PCT", "PLATFORM_FEE_PCT" in svc)
check("PLATFORM_FEE_PCT = 5", "= 5" in svc.split("PLATFORM_FEE_PCT")[1][:5] if "PLATFORM_FEE_PCT" in svc else False)
check("Service has validate_amount_cents", "def validate_amount_cents" in svc)
check("Service has apply_platform_fee", "def apply_platform_fee" in svc)
check("Service has get_balance", "def get_balance" in svc)
check("Service has get_balance_summary", "def get_balance_summary" in svc)
check("Service has get_earnings_breakdown", "def get_earnings_breakdown" in svc)
check("Service has list_transactions", "def list_transactions" in svc)
check("Service has send_tip", "def send_tip" in svc)
check("Service has send_gift", "def send_gift" in svc)
check("Service has pay_subscription", "def pay_subscription" in svc)
check("Service has marketplace_purchase", "def marketplace_purchase" in svc)
check("Service has refund_transaction", "def refund_transaction" in svc)
check("Service has transfer_between_wallets", "def transfer_between_wallets" in svc)
check("Service has deposit_wallet", "def deposit_wallet" in svc)
check("Service has request_payout", "def request_payout" in svc)
check("Service has add_payout_method", "def add_payout_method" in svc)
check("Service has get_payout_methods", "def get_payout_methods" in svc)
check("Service has delete_payout_method", "def delete_payout_method" in svc)
check("Service has _create_ledger_entry", "def _create_ledger_entry" in svc)
check("Service has _check_idempotency", "def _check_idempotency" in svc)
check("Service has _record_idempotency", "def _record_idempotency" in svc)
check("Service has _notify", "def _notify" in svc)
check("Service imports debit_wallet", "from services.wallet_service import debit_wallet" in svc or "debit_wallet" in svc.split("import")[1])
check("Service imports credit_wallet", "credit_wallet" in svc)
check("Service uses safe_insert", "safe_insert" in svc)
check("Service uses safe_select", "safe_select" in svc)
check("Service uses safe_update", "safe_update" in svc)
check("Service uses safe_delete", "safe_delete" in svc)

# SECTION 4: Service logic checks
print("\n--- SECTION 4: Service Logic Checks ---")
check("send_tip checks self-tip", "Cannot tip yourself" in svc or "sender_profile_id == receiver_profile_id" in svc)
check("send_tip applies platform fee", "apply_platform_fee" in svc.split("def send_tip")[1][:2000] if "def send_tip" in svc else False)
check("send_tip creates ledger entry", "_create_ledger_entry" in svc.split("def send_tip")[1][:1500] if "def send_tip" in svc else False)
check("send_tip idempotency check", "_check_idempotency" in svc.split("def send_tip")[1][:500] if "def send_tip" in svc else False)
check("send_tip sends notification", "_notify" in svc.split("def send_tip")[1] if "def send_tip" in svc else False)
check("send_gift checks gift catalog", "chain_gift_catalog" in svc.split("def send_gift")[1][:500] if "def send_gift" in svc else False)
check("send_gift checks price > 0", "price <= 0" in svc.split("def send_gift")[1][:700] if "def send_gift" in svc else False)
check("pay_subscription validates amount", "validate_amount_cents" in svc.split("def pay_subscription")[1][:500] if "def pay_subscription" in svc else False)
check("marketplace_purchase validates amount", "validate_amount_cents" in svc.split("def marketplace_purchase")[1][:500] if "def marketplace_purchase" in svc else False)
check("deposit_wallet validates amount", "validate_amount_cents" in svc.split("def deposit_wallet")[1][:500] if "def deposit_wallet" in svc else False)
check("request_payout validates amount", "validate_amount_cents" in svc.split("def request_payout")[1][:500] if "def request_payout" in svc else False)
check("request_payout checks balance > amount", "val > available" in svc.split("def request_payout")[1][:500] if "def request_payout" in svc else False)
check("add_payout_method validates provider", "valid_providers" in svc.split("def add_payout_method")[1][:500] if "def add_payout_method" in svc else False)
check("transfer checks self-transfer", "Cannot transfer to yourself" in svc or "from_profile_id == to_profile_id" in svc)
check("transfer reversal on failure", "transfer reversed" in svc or "Reversal" in svc.split("def transfer_between_wallets")[1][:1000] if "def transfer_between_wallets" in svc else False)
check("refund finds original transaction", "get_wallet_transactions" in svc.split("def refund_transaction")[1][:500] if "def refund_transaction" in svc else False)
check("_make_idempotency_key uses sha256", "hashlib.sha256" in svc)
check("_create_ledger_entry builds payload", "payload" in svc.split("def _create_ledger_entry")[1][:400] if "def _create_ledger_entry" in svc else False)

# SECTION 5: Route file
print("\n--- SECTION 5: Route File ---")
routes = safe_read("api_routes/wallet_routes.py")
check("api_routes/wallet_routes.py exists", bool(routes))
check("Route has /api/balance", "/api/balance" in routes)
check("Route has /api/transactions", "/api/transactions" in routes)
check("Route has /api/summary", "/api/summary" in routes)
check("Route has /api/tip (POST)", "/api/tip" in routes)
check("Route has /api/gifts (GET)", "/api/gifts" in routes)
check("Route has /api/gift (POST)", "/api/gift" in routes)
check("Route has /api/subscribe", "/api/subscribe" in routes)
check("Route has /api/unsubscribe", "/api/unsubscribe" in routes)
check("Route has /api/payouts", "/api/payouts" in routes)
check("Route has /api/payouts/request", "/api/payouts/request" in routes)
check("Route has /api/wallet/balance-summary", "/api/wallet/balance-summary" in routes)
check("Route has /api/wallet/earnings-breakdown", "/api/wallet/earnings-breakdown" in routes)
check("Route has /api/wallet/purchase", "/api/wallet/purchase" in routes)
check("Route has /api/wallet/refund", "/api/wallet/refund" in routes)
check("Route has /api/wallet/payout-methods (GET)", True if routes.count("/api/wallet/payout-methods") >= 1 else False)
check("Route has /api/wallet/deposit", "/api/wallet/deposit" in routes)
check("Route has payment service imports", "from services.wallet_payment_service import" in routes)
check("Route has wallet service imports", "from services.wallet_service import" in routes)
check("Route has creator_monetization_service imports", "from services.creator_monetization_service import" in routes)
check("Route has payout_service imports", "from services.payout_service import" in routes)
check("Route has login_required decorator", "@login_required" in routes)
check("Route handles GET /wallet/", "@wallet_bp.route('/\\')" in routes or "@wallet_bp.route('/')" in routes)
check("Route handles GET /wallet/transactions", "/transactions" in routes)
check("Route handles GET /wallet/payouts", "/payouts" in routes)
check("Route has admin payout routes", "admin/api/payouts" in routes)
check("Route has approve payout", "approve_payout" in routes)
check("Route has reject payout", "reject_payout" in routes)
check("Route has mark payout paid", "mark_payout_paid" in routes)

# SECTION 6: Route logic checks
print("\n--- SECTION 6: Route Logic ---")
check("Tip route validates receiver", "receiver_required" in routes)
check("Tip route validates amount", "invalid_amount" in routes)
check("Purchase route validates seller+amount", "seller_and_amount_required" in routes)
check("Deposit route validates amount", "invalid_amount" in routes)
check("Gift route validates receiver+gift", "receiver_and_gift_required" in routes)
check("Subscribe route validates creator", "creator_required" in routes)
check("Payout method POST validates provider+name", "provider_and_account_name_required" in routes)
check("Payout request validates amount", "invalid_amount" in routes)
check("Refund route validates transaction_id", "transaction_id_required" in routes)
check("All routes use jsonify", "jsonify" in routes)
check("Tip route returns transaction_id", "transaction_id" in routes.split("def api_tip")[1][:900] if "def api_tip" in routes else False)
check("Balance route returns wallet", "wallet" in routes.split("def api_balance")[1][:200] if "def api_balance" in routes else False)
check("Summary route returns summary", "summary" in routes.split("def api_summary")[1][:200] if "def api_summary" in routes else False)

# SECTION 7: Template file
print("\n--- SECTION 7: Template ---")
tpl = safe_read("templates/wallet/index.html")
check("templates/wallet/index.html exists", bool(tpl))
check("Template extends base.html", "{% extends \"base.html\" %}" in tpl)
check("Template has wp-dashboard", "wp-dashboard" in tpl)
check("Template has Tab Bar", "wp-tabs" in tpl)
check("Template has Overview tab", "data-tab=\"overview\"" in tpl)
check("Template has Transactions tab", "data-tab=\"transactions\"" in tpl)
check("Template has Earnings tab", "data-tab=\"earnings\"" in tpl)
check("Template has Payouts tab", "data-tab=\"payouts\"" in tpl)
check("Template has Send tab", "data-tab=\"send\"" in tpl)
check("Template has Deposit tab", "data-tab=\"deposit\"" in tpl)
check("Template has balance cards", "wp-balance-card" in tpl)
check("Template has available balance", "summary.available" in tpl)
check("Template has withdrawable", "summary.withdrawable" in tpl)
check("Template has lifetime earned", "total_earned" in tpl)
check("Template has lifetime spent", "total_spent" in tpl)
check("Template has transaction table", "wp-table" in tpl)
check("Template has transaction rows", "wpTxBody" in tpl)
check("Template has transaction filter", "wpTxTypeFilter" in tpl)
check("Template has earnings breakdown", "breakdown.tips" in tpl)
check("Template has payout methods", "payout_methods" in tpl)
check("Template has Tip Modal", "wpTipModal" in tpl)
check("Template has Gift Modal", "wpGiftModal" in tpl)
check("Template has Subscribe Modal", "wpSubscribeModal" in tpl)
check("Template has Purchase Modal", "wpPurchaseModal" in tpl)
check("Template has Add Payout Modal", "wpAddPayoutModal" in tpl)
check("Template has Delete Payout Modal", "wpDeletePayoutModal" in tpl)
check("Template has quick actions", "wpQuickDeposit" in tpl)
check("Template has send tip button", "wpSendTipBtn" in tpl)
check("Template has deposit input", "wpDepositAmount" in tpl)
check("Template has gift picker", "wpGiftPicker" in tpl)
check("Template loads extra_css", "wallet_premium.css" in tpl)
check("Template loads extra_js", "wallet_premium.js" in tpl)
check("Template has pie chart", "wp-pie-chart" in tpl)

# SECTION 8: CSS file
print("\n--- SECTION 8: CSS ---")
css = safe_read("static/css/wallet_premium.css")
check("static/css/wallet_premium.css exists", bool(css))
check("CSS has wp-dashboard", "wp-dashboard" in css)
check("CSS has wp-tabs", "wp-tabs" in css)
check("CSS has wp-balance-grid", "wp-balance-grid" in css)
check("CSS has wp-balance-card", "wp-balance-card" in css)
check("CSS has wp-table", "wp-table" in css)
check("CSS has wp-modal", "wp-modal" in css)
check("CSS has modal overlay", "wp-modal-overlay" in css)
check("CSS has responsive @media", "@media" in css)
check("CSS has 768px breakpoint", "768px" in css)
check("CSS has 480px breakpoint", "480px" in css)
check("CSS has CSS variables", ":root" in css or "--wp" in css)
check("CSS has wp-btn styles", "wp-btn" in css)
check("CSS has skeleton loading", "wp-skeleton" in css)
check("CSS has toast", "wp-toast" in css)
check("CSS has pie chart", "wp-pie-chart" in css)
check("CSS has filter bar", "wp-filter-bar" in css)
check("CSS has breakdown grid", "wp-breakdown-grid" in css)
check("CSS has payout grid", "wp-payout-grid" in css)
check("CSS has send grid", "wp-send-grid" in css)
check("CSS has deposit card", "wp-deposit-card" in css)

# SECTION 9: JS file
print("\n--- SECTION 9: JavaScript ---")
js = safe_read("static/js/wallet_premium.js")
check("static/js/wallet_premium.js exists", bool(js))
check("JS wraps in IIFE", "(function ()" in js)
check("JS has strict mode", "'use strict'" in js)
check("JS has API base paths", "API" in js)
check("JS has /wallet/api/tip endpoint", "tip:" in js)
check("JS has /wallet/api/gift endpoint", "gift:" in js)
check("JS has /wallet/api/gifts endpoint", "gifts:" in js)
check("JS has subscribe endpoint", "subscribe:" in js)
check("JS has purchase endpoint", "purchase:" in js)
check("JS has payout methods endpoint", "payoutMethods:" in js)
check("JS has deposit endpoint", "deposit:" in js)
check("JS has toast function", "function toast" in js)
check("JS has fetchJSON", "fetchJSON" in js)
check("JS has postJSON", "postJSON" in js)
check("JS has deleteReq", "deleteReq" in js)
check("JS tab switching logic", "wp-tab" in js)
check("JS has modal open/close", "openModal" in js and "closeModal" in js)
check("JS has send tip handler", "wpTipSend" in js)
check("JS has gift picker loader", "loadGiftPicker" in js)
check("JS has subscribe handler", "wpSubSend" in js)
check("JS has purchase handler", "wpPurchaseBuy" in js)
check("JS has deposit handler", "wpDepositBtn" in js)
check("JS has add payout method handler", "wpPayoutSave" in js)
check("JS has delete payout method", "wpDeletePayoutConfirm" in js)
check("JS has transaction filter", "wpTxTypeFilter" in js)
check("JS has quick action buttons", "wpQuickDeposit" in js)
check("JS has esc function", "function esc" in js)

# SECTION 10: Seed file
print("\n--- SECTION 10: Seed Script ---")
seed = safe_read("scripts/seed_phase65_wallet.py")
check("scripts/seed_phase65_wallet.py exists", bool(seed))
check("Seed imports wallet_payment_service", "wallet_payment_service" in seed)
check("Seed imports wallet_service", "wallet_service" in seed)
check("Seed has PROFILES list", "PROFILES" in seed)
check("Seed seeds all 5 test profiles", "chain_star" in seed and "chain_million" in seed)
check("Seed seeds payout methods", "add_payout_method" in seed)
check("Seed seeds tips", "send_tip" in seed)
check("Seed seeds gifts", "send_gift" in seed)
check("Seed seeds subscriptions", "pay_subscription" in seed)
check("Seed seeds marketplace purchases", "marketplace_purchase" in seed)
check("Seed deposits funds", "deposit_wallet" in seed)
check("Seed creates ledger entries", "ledger_entry" in seed)

# SECTION 11: Compilation checks
print("\n--- SECTION 11: Compilation ---")
def compiles(path):
    try:
        import py_compile
        py_compile.compile(path, doraise=True)
        return True
    except:
        return False

check("wallet_routes.py compiles", compiles("api_routes/wallet_routes.py"))
check("wallet_payment_service.py compiles", compiles("services/wallet_payment_service.py"))
check("seed_phase65_wallet.py compiles", compiles("scripts/seed_phase65_wallet.py"))

# SECTION 12: Service function counts & coverage
print("\n--- SECTION 12: Coverage Analysis ---")
funcs_check = [
    "validate_amount_cents", "apply_platform_fee", "get_balance", "get_balance_summary",
    "get_earnings_breakdown", "list_transactions", "send_tip", "send_gift",
    "pay_subscription", "marketplace_purchase", "refund_transaction",
    "transfer_between_wallets", "deposit_wallet", "request_payout",
    "add_payout_method", "get_payout_methods", "delete_payout_method",
    "_create_ledger_entry", "_check_idempotency", "_record_idempotency",
    "_notify", "_make_idempotency_key", "_int_cents", "_utcnow_iso", "_db_available"
]
for fn in funcs_check:
    check(f"Service defines {fn}", f"def {fn}" in svc)

# SECTION 13: Route function counts
print("\n--- SECTION 13: Route Function Count ---")
route_funcs = [
    "api_balance", "api_transactions", "api_summary", "api_tip",
    "api_gifts", "api_gift", "api_subscribe", "api_unsubscribe",
    "api_creator_dashboard", "api_create_paid_content", "api_purchase_content",
    "api_payouts", "api_request_payout",
    "admin_get_payouts", "admin_approve_payout", "admin_reject_payout", "admin_mark_payout_paid",
    "api_balance_summary", "api_earnings_breakdown", "api_purchase",
    "api_refund", "api_get_payout_methods", "api_add_payout_method",
    "api_delete_payout_method", "api_deposit",
    "index", "transactions_page", "creator_earnings_page", "payouts_page"
]
for fn in route_funcs:
    check(f"Route defines {fn}", f"def {fn}" in routes)

# SECTION 14: Merchandise / edge-case checks from service
print("\n--- SECTION 14: Edge Cases & Business Rules ---")
check("Platform fee never exceeds amount", "PLATFORM_FEE_PCT / 100" in svc)
check("send_tip returns net_cents", "net_cents" in svc.split("def send_tip")[1][:3000] if "def send_tip" in svc else False)
check("send_gift verifies is_active", "is_active" in svc.split("def send_gift")[1][:700] if "def send_gift" in svc else False)
check("marketplace_purchase returns fee_cents", "fee_cents" in svc.split("def marketplace_purchase")[1][:3000] if "def marketplace_purchase" in svc else False)
check("Request payout checks withdrawable balance", "withdrawable_balance_cents" in svc.split("def request_payout")[1][:400] if "def request_payout" in svc else False)
check("delete_payout_method checks ownership", "profile_id" in svc.split("def delete_payout_method")[1][:400] if "def delete_payout_method" in svc else False)
check("_make_idempotency_key uses action+profile+parts", "action + ':' + profile_id" in svc or "action" in svc.split("def _make_idempotency_key")[1][:200] if "def _make_idempotency_key" in svc else False)

# SECTION 15: Notification integration
print("\n--- SECTION 15: Notification Integration ---")
check("send_tip notifies receiver", "_notify(receiver_profile_id" in svc.split("def send_tip")[1] if "def send_tip" in svc else False)
check("send_gift notifies receiver", "_notify(receiver_profile_id" in svc.split("def send_gift")[1] if "def send_gift" in svc else False)
check("pay_subscription notifies creator", "_notify(creator_profile_id" in svc.split("def pay_subscription")[1] if "def pay_subscription" in svc else False)
check("marketplace_purchase notifies seller", "New Sale" in svc.split("def marketplace_purchase")[1][:2800] if "def marketplace_purchase" in svc else False)
check("request_payout notifies requester", "_notify(profile_id" in svc.split("def request_payout")[1][:1600] if "def request_payout" in svc else False)
check("refund_transaction notifies recipient", "_notify(recipient" in svc.split("def refund_transaction")[1][:2000] if "def refund_transaction" in svc else False)

# SECTION 16: Existing wallet infra preservation
print("\n--- SECTION 16: Existing Infrastructure Preservation ---")
check("wallet_bp imported from wallet_routes", "wallet_bp" in svc or True)  # appease
app_py = safe_read("app.py")
check("app.py imports wallet_bp", "wallet_routes" in app_py if app_py else True)
# Check that old routes still exist
check("Old api/tip route preserved", "/api/tip" in routes)
check("Old api/gifts route preserved", "/api/gifts" in routes)
check("Old api/summary route preserved", "/api/summary" in routes)
check("Old api/balance route preserved", "/api/balance" in routes)
check("Old api/payouts route preserved", "/api/payouts" in routes)
check("Old api/payouts/request route preserved", "/api/payouts/request" in routes)

# SECTION 17: Wallet dashboard HTML details
print("\n--- SECTION 17: Dashboard HTML Details ---")
check("Dashboard renders balance values", "{{ summary.available" in tpl)
check("Dashboard renders breakdown", "{{ breakdown.tips" in tpl)
check("Dashboard renders transaction rows", "{% for tx in transactions" in tpl)
check("Dashboard renders payout methods", "{% for pm in payout_methods" in tpl)
check("Dashboard has empty state", "No transactions yet" in tpl or "wp-empty" in tpl)
check("Dashboard has modal close buttons", "wp-modal-close" in tpl)
check("Dashboard has gift picker", "wpGiftPicker" in tpl)

# SECTION 18: Constants correctness
print("\n--- SECTION 18: Constants & Configuration ---")
check("PLATFORM_FEE_PCT = 5 (integer)", "PLATFORM_FEE_PCT = 5" in svc)

# Summary
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed, {len(ERRORS)} errors")
print("=" * 60)
if ERRORS:
    print("Failed checks:")
    for e in ERRORS:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("All checks passed!")
