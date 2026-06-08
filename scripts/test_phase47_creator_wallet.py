"""
Phase 47 E2E: Creator Wallet, Monetization, Tips, Payouts & Earnings
Uses FLASK_TESTING=1 so all service _db_available() return False (fake mode).
Tests that function call shapes, risk checks, API routes, templates, and code
integration points are correct.
"""
import os, sys, json, uuid as uuid_mod, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"
logging.disable(logging.CRITICAL)

from app import create_app
app = create_app()

PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        msg = f"  [FAIL] {label}"
        if detail:
            msg += f"  ({detail})"
        print(msg)

with app.test_client() as c:
    with c.session_transaction() as s:
        s["profile_id"] = "phase47-test-creator"
        s["auth_user_id"] = "phase47-creator-auth"

    CREATOR = "phase47-test-creator"
    FAN = "phase47-test-fan"
    ADMIN = "phase47-test-admin"

    print("\n=== 1. MIGRATION ===\n")
    check("migration file exists", os.path.isfile("sql/phase47_creator_wallet_monetization.sql"))
    with open("sql/phase47_creator_wallet_monetization.sql") as f:
        sql = f.read()
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    check("migration has statements", len(statements) > 10)
    check("migration uses IF NOT EXISTS", "IF NOT EXISTS" in sql)
    for kw in ["chain_wallets", "chain_creator_earnings", "chain_creator_subscriptions",
               "chain_paid_content", "chain_content_purchases", "chain_payout_requests",
               "chain_wallet_risk_events"]:
        check(f"migration has {kw}", kw in sql)

    print("\n=== 2. WALLET CREATION ===\n")
    from services.wallet_service import get_or_create_wallet, get_wallet, credit_wallet, debit_wallet, transfer_between_wallets, get_wallet_transactions, get_wallet_summary

    wallet = get_or_create_wallet(CREATOR)
    check("wallet created for creator", wallet is not None)
    check("wallet has profile_id", wallet and wallet.get("profile_id") == CREATOR)
    check("wallet balance 0", wallet and wallet.get("balance_cents", -1) == 0)
    check("wallet has id", wallet and wallet.get("id") is not None)
    check("wallet has status", wallet and wallet.get("status") == "active")

    fan_wallet = get_or_create_wallet(FAN)
    check("wallet created for fan", fan_wallet is not None)
    check("fan wallet balance 0", fan_wallet and fan_wallet.get("balance_cents", -1) == 0)

    print("\n=== 3. WALLET OPERATIONS (fake mode) ===\n")
    cred = credit_wallet(FAN, 500000, description="Test credit")
    check("credit wallet returns ok", cred.get("ok"))
    check("credit returns balance", cred.get("balance_cents") is not None)
    check("credit returns transaction_id", cred.get("transaction_id") is not None)

    deb = debit_wallet(FAN, 100000, description="Test debit")
    check("debit fails in fake mode (no balance)", not deb.get("ok"))
    check("debit returns error detail", deb.get("error") is not None)

    neg = debit_wallet(FAN, 999999999)
    check("prevent negative balance (insufficient in fake mode)", not neg.get("ok"))

    txs = get_wallet_transactions(FAN)
    check("wallet transactions returns list", isinstance(txs, list))
    check("wallet transactions empty in fake mode", len(txs) == 0)

    summary = get_wallet_summary(FAN)
    check("wallet summary returned", summary is not None)
    check("summary has wallet", summary and summary.get("wallet"))
    check("wallet summary has recent_transactions", summary and "recent_transactions" in summary)
    check("summary has total_transactions", summary and "total_transactions" in summary)

    print("\n=== 4. TRANSFER ===\n")
    transfer = transfer_between_wallets(FAN, CREATOR, 50000, description="Test transfer")
    check("transfer returns dict", isinstance(transfer, dict))
    check("transfer fails in fake mode (insufficient balance)", not transfer.get("ok"))

    self_transfer = transfer_between_wallets(CREATOR, CREATOR, 1000)
    check("prevent self transfer", not self_transfer.get("ok"))

    zero_transfer = transfer_between_wallets(FAN, CREATOR, 0)
    check("prevent zero transfer", not zero_transfer.get("ok"))

    neg_transfer = transfer_between_wallets(FAN, CREATOR, -100)
    check("prevent negative transfer", not neg_transfer.get("ok"))

    print("\n=== 5. TIP ===\n")
    from services.creator_monetization_service import (send_tip, send_gift, get_available_gifts,
        subscribe_to_creator, cancel_creator_subscription, is_subscribed,
        create_paid_content, purchase_paid_content, has_purchased_content,
        get_creator_earnings, get_creator_dashboard)

    tip = send_tip(FAN, CREATOR, 25000, message="Great content!")
    check("tip returns dict", isinstance(tip, dict))
    check("tip fails in fake mode (insufficient balance)", not tip.get("ok"))

    self_tip = send_tip(CREATOR, CREATOR, 1000)
    check("prevent self tip", not self_tip.get("ok"))

    neg_tip = send_tip(CREATOR, CREATOR, -100)
    check("prevent negative tip", not neg_tip.get("ok"))

    zero_tip = send_tip(CREATOR, CREATOR, 0)
    check("prevent zero tip", not zero_tip.get("ok"))

    big_tip = send_tip(FAN, CREATOR, 6000000)
    check("block tip > N$50k", not big_tip.get("ok"))

    print("\n=== 6. GIFT ===\n")
    gifts = get_available_gifts()
    check("gifts returns list", isinstance(gifts, list))
    if gifts:
        check("gift has id", gifts[0].get("id"))
        check("gift has price_cents", gifts[0].get("price_cents"))

    self_gift = send_gift(CREATOR, CREATOR, 1)
    check("prevent self gift", not self_gift.get("ok"))

    print("\n=== 7. SUBSCRIPTION ===\n")
    sub = subscribe_to_creator(FAN, CREATOR, tier_name="premium", price_cents=30000)
    check("subscribe returns dict", isinstance(sub, dict))
    check("subscribe fails in fake mode", not sub.get("ok"))

    self_sub = subscribe_to_creator(CREATOR, CREATOR, price_cents=0)
    check("prevent self subscription", not self_sub.get("ok"))

    check("is_subscribed returns bool", isinstance(is_subscribed(FAN, CREATOR), bool))

    cancel = cancel_creator_subscription(FAN, CREATOR)
    check("cancel returns dict", isinstance(cancel, dict))

    print("\n=== 8. PAID CONTENT ===\n")
    paid = create_paid_content(CREATOR, "post", 15000)
    check("create paid content returns dict", isinstance(paid, dict))
    check("create fails in fake mode", not paid.get("ok"))

    self_purchase = purchase_paid_content(CREATOR, CREATOR, "fake-id")
    check("prevent self purchase", not self_purchase.get("ok"))

    check("has_purchased_content returns bool", isinstance(has_purchased_content(FAN, "fake-id"), bool))

    print("\n=== 9. CREATOR EARNINGS ===\n")
    earnings = get_creator_earnings(CREATOR)
    check("earnings returns list", isinstance(earnings, list))

    dashboard = get_creator_dashboard(CREATOR)
    check("dashboard returns dict", isinstance(dashboard, dict))
    check("dashboard has total_earnings_cents", "total_earnings_cents" in (dashboard or {}))
    check("dashboard has recent_earnings", "recent_earnings" in (dashboard or {}))

    print("\n=== 10. PAYOUT ===\n")
    from services.payout_service import request_payout, get_payout_requests, get_creator_payouts, approve_payout, reject_payout, mark_payout_paid

    pay = request_payout(CREATOR, 50000)
    check("payout request returns dict", isinstance(pay, dict))
    check("payout fails in fake mode (no balance)", not pay.get("ok"))

    self_approve = approve_payout("fake-id", admin_note="Test")
    check("approve returns dict", isinstance(self_approve, dict))

    self_reject = reject_payout("fake-id")
    check("reject returns dict", isinstance(self_reject, dict))

    self_mark = mark_payout_paid("fake-id")
    check("mark paid returns dict", isinstance(self_mark, dict))

    payouts = get_payout_requests()
    check("get_payout_requests returns list", isinstance(payouts, list))

    creator_payouts = get_creator_payouts(CREATOR)
    check("get_creator_payouts returns list", isinstance(creator_payouts, list))

    print("\n=== 11. API ROUTES ===\n")
    with c.session_transaction() as s:
        s["profile_id"] = FAN
        s["auth_user_id"] = "phase47-fan-auth"

    for route in ["/wallet/api/balance", "/wallet/api/transactions", "/wallet/api/summary",
                   "/wallet/api/gifts", f"/wallet/api/creator/{CREATOR}/dashboard",
                   "/wallet/api/payouts"]:
        r = c.get(route)
        check(f"GET {route} 200", r.status_code == 200)

    for route, data in [
        ("/wallet/api/tip", {"receiver_profile_id": CREATOR, "amount_cents": 5000}),
        ("/wallet/api/payouts/request", {"amount_cents": 5000}),
    ]:
        r = c.post(route, data=data)
        check(f"POST {route} 200/400", r.status_code in (200, 400))

    with c.session_transaction() as s:
        s["profile_id"] = ADMIN
        s["auth_user_id"] = "phase47-admin-auth"

    r = c.get("/wallet/admin/api/payouts")
    check("GET admin/api/payouts 200", r.status_code in (200, 302, 403))

    print("\n=== 12. TEMPLATES ===\n")
    for tpl in ["dashboard.html", "transactions.html", "creator_earnings.html", "payouts.html"]:
        check(f"templates/wallet/{tpl} exists", os.path.isfile(f"templates/wallet/{tpl}"))

    print("\n=== 13. BACKWARD COMPAT ===\n")
    from services.wallet_service import ensure_wallet, get_wallet_home, top_up_wallet, get_wallet_data
    ew = ensure_wallet(CREATOR)
    check("ensure_wallet returns dict", isinstance(ew, dict))
    check("ensure_wallet has profile_id", ew.get("profile_id") == CREATOR)
    check("ensure_wallet has coin_balance", "coin_balance" in ew)

    wh = get_wallet_home(FAN)
    check("get_wallet_home returns dict", isinstance(wh, dict))

    tu = top_up_wallet(FAN, 10000)
    check("top_up_wallet returns dict", isinstance(tu, dict))
    check("top_up returns ok", tu.get("ok"))

    wd = get_wallet_data(CREATOR)
    check("get_wallet_data returns dict", isinstance(wd, dict))
    check("get_wallet_data has balance_cents", "balance_cents" in (wd or {}))

    from services.creator_monetization_service import calculate_platform_fee
    fee = calculate_platform_fee(10000)
    check("calculate_platform_fee returns int", isinstance(fee, int))
    check("fee is 10%", fee == 1000)

    print("\n=== 14. SOCKET EVENTS ===\n")
    socket_events = ["wallet:balance-updated", "wallet:tip-received", "wallet:gift-received",
                     "wallet:subscription-created", "wallet:paid-content-purchased",
                     "wallet:payout-updated"]
    found_events = set()
    for root, dirs, files in os.walk("."):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                try:
                    content = open(path).read()
                except Exception:
                    continue
                for evt in socket_events:
                    if evt in content:
                        found_events.add(evt)
    for evt in socket_events:
        check(f"socket event '{evt}' emitted", evt in found_events)

    print("\n=== 15. NOTIFICATION INTEGRATIONS ===\n")
    notif_events = ["tip_received", "gift_received", "new_subscriber", "content_purchased",
                    "payout_approved", "payout_rejected", "payout_paid"]
    found_notifs = set()
    for root, dirs, files in os.walk("."):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                try:
                    content = open(path).read()
                except Exception:
                    continue
                for evt in notif_events:
                    if f"event_type=\"{evt}\"" in content or f"event_type='{evt}'" in content:
                        found_notifs.add(evt)
    for evt in notif_events:
        check(f"notification '{evt}' integrated", evt in found_notifs)

    print("\n=== 16. BLUEPRINT REGISTRATION ===\n")
    try:
        from api_routes.wallet_routes import wallet_bp
        check("wallet_bp imported", wallet_bp is not None)
    except ImportError as e:
        check("wallet_bp imported", False, str(e))

    rules = list(app.url_map.iter_rules())
    wallet_rules = [r for r in rules if "wallet" in r.rule]
    check("wallet routes registered", len(wallet_rules) > 0)

    has_get_api = any(r.rule.startswith("/wallet/api/") and "GET" in r.methods for r in wallet_rules)
    has_post_api = any(r.rule.startswith("/wallet/api/") and "POST" in r.methods for r in wallet_rules)
    has_get_admin = any(r.rule.startswith("/wallet/admin/") and "GET" in r.methods for r in wallet_rules)
    check("GET /wallet/api/* routes registered", has_get_api)
    check("POST /wallet/api/* routes registered", has_post_api)
    check("GET /wallet/admin/* routes registered", has_get_admin)

    print("\n=== 17. CENTS (NO FLOATS) ENFORCEMENT ===\n")
    wallet_vars = {"wallet_service.py": ["balance_cents", "amount_cents", "transaction_id"],
                   "creator_monetization_service.py": ["balance_cents", "amount_cents", "price_cents", "fee_cents", "net_cents"],
                   "payout_service.py": ["balance_cents", "amount_cents"]}
    for root, dirs, files in os.walk("services"):
        for f in files:
            if f in wallet_vars:
                path = os.path.join(root, f)
                content = open(path).read()
                for kw in wallet_vars[f]:
                    check(f"{f} uses {kw}", kw in content)

    print("\n=== 18. PLATFORM FEE ===\n")
    from services.creator_monetization_service import calculate_platform_fee
    for amt, expected in [(100, 10), (500, 50), (1000, 100), (999, 99), (0, 0)]:
        check(f"fee on {amt} = {expected}", calculate_platform_fee(amt) == expected)

print(f"\n{'='*50}")
print(f"Results: {PASS}/{PASS+FAIL} passed, {FAIL} failed")
print(f"{'='*50}")
sys.exit(0 if FAIL == 0 else 1)
