"""NamVibe Live — NVC Coin Gift Flow End-to-End Test"""
import os, sys, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"
os.environ["FLASK_ENV"] = "production"

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"
ok = lambda msg: print(f"  {GREEN}✓{RESET} {msg}")
fail = lambda msg: print(f"  {RED}✗{RESET} {msg}")
warn = lambda msg: print(f"  {YELLOW}⚠{RESET} {msg}")
header = lambda msg: print(f"\n{CYAN}{BOLD}{msg}{RESET}")

from services.neon_service import fetch_one, fetch_all, execute
from api_routes.live_routes import _get_balance, _credit_nvc, _deduct_nvc

errors = 0

# ── 1. Pick a real profile for testing ──
header("1. Setup: find test profile")
profile = fetch_one("SELECT id, display_name FROM chain_profiles LIMIT 1")
if not profile:
    fail("No profiles found in DB")
    sys.exit(1)
pid = profile["id"]
ok(f"Using profile {pid} ({profile.get('display_name', '?')})")

# ── 2. Ensure wallet exists ──
header("2. Test wallet & balance")
bal = _get_balance(pid)
ok(f"Initial balance: {bal} NVC")

# ── 3. Verify packages ──
header("3. Test purchase packages")
pkgs = fetch_all("SELECT * FROM chain_nvc_packages ORDER BY sort_order ASC")
if pkgs:
    ok(f"{len(pkgs)} packages loaded")
    for p in pkgs[:3]:
        ok(f"  {p['name']}: {p['coins']} NVC for ${p['price']}")
else:
    fail("No packages found")
    errors += 1

# ── 4. Test purchase (credit) ──
header("4. Test NVC purchase (credit)")
before = _get_balance(pid)
_credit_nvc(pid, 100, "purchase", "test", "", "Test purchase of 100 NVC")
after = _get_balance(pid)
if after == before + 100:
    ok(f"Credited 100 NVC: {before} → {after}")
else:
    fail(f"Credit failed: {before} → {after}")
    errors += 1

# ── 5. Check transactions ──
header("5. Test transaction history")
txs = fetch_all("SELECT * FROM chain_nvc_transactions WHERE profile_id = %s ORDER BY created_at DESC LIMIT 5", (pid,))
if txs:
    ok(f"{len(txs)} transactions found")
    for t in txs[:3]:
        ok(f"  {t['type']}: {t['amount']} (balance after: {t['balance_after']})")
else:
    fail("No transactions")
    errors += 1

# ── 6. Test deduct (gift send) ──
header("6. Test NVC deduction (send gift)")
bal_before = _get_balance(pid)
amt = 25
deduct_ok, new_bal = _deduct_nvc(pid, amt, "live_gift", "test_room", f"Test gift of {amt} NVC")
if deduct_ok and new_bal == bal_before - amt:
    ok(f"Deducted {amt} NVC: {bal_before} → {new_bal}")
else:
    fail(f"Deduction failed: ok={ok}, new_bal={new_bal}, expected {bal_before - amt}")
    errors += 1

# ── 7. Test insufficient balance ──
header("7. Test insufficient balance guard")
big_amt = 999999
deduct_ok2, _ = _deduct_nvc(pid, big_amt, "live_gift", "", "Test insufficient")
if deduct_ok2:
    fail(f"Should have failed for {big_amt} NVC")
    errors += 1
else:
    ok(f"Correctly rejected {big_amt} NVC deduction (balance: {_get_balance(pid)})")

# ── 8. Verify gift catalog ──
header("8. Test gift catalog")
catalog = fetch_all("SELECT * FROM chain_live_gift_catalog ORDER BY sort_order ASC")
if catalog:
    ok(f"{len(catalog)} gifts in catalog")
    tiers = {}
    for g in catalog:
        tiers.setdefault(g["tier"], 0)
        tiers[g["tier"]] += 1
    for tier, count in sorted(tiers.items()):
        ok(f"  {tier.title()}: {count} gifts")
else:
    fail("No gift catalog")
    errors += 1

# ── 9. Test direct DB record of gift transaction ──
header("9. Test gift transaction record in chain_live_gifts")
lid = "00000000-0000-0000-0000-000000000000"  # fake room UUID
execute(
    "INSERT INTO chain_live_gifts (room_id, sender_profile_id, gift_name, gift_icon, amount) VALUES (%s, %s, %s, %s, %s)",
    (lid, pid, "Heart", "❤️", 5)
)
gift_row = fetch_one("SELECT * FROM chain_live_gifts WHERE room_id = %s AND sender_profile_id = %s", (lid, pid))
if gift_row:
    ok(f"Gift recorded: {gift_row['gift_name']} ({gift_row['gift_icon']}) — {gift_row['amount']} NVC")
    execute("DELETE FROM chain_live_gifts WHERE id = %s", (gift_row["id"],))
else:
    fail("Gift not recorded")
    errors += 1

# ── 10. Check live_routes.py compiles cleanly ──
header("10. Verify live_routes.py integrity")
import py_compile
try:
    py_compile.compile(os.path.join(ROOT, "api_routes", "live_routes.py"), doraise=True)
    ok("live_routes.py compiles")
except py_compile.PyCompileError as e:
    fail(f"Compile error: {e}")
    errors += 1

# ── 11. Cleanup: reset test balance ──
header("11. Cleanup")
execute("UPDATE chain_nvc_wallet SET balance = 0 WHERE profile_id = %s", (pid,))
final = _get_balance(pid)
ok(f"Reset wallet balance to {final}")

# ── Summary ──
print(f"\n{BOLD}═══ Results: {errors} errors ═══{RESET}\n")
sys.exit(1 if errors else 0)
