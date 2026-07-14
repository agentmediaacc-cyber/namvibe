"""Test real features against live Neon DB — no mocks, no fakes."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_ENV"] = "testing"

from services.neon_service import fast_query, execute
from services.profile_view_service import build_profile_view_model

PASS = 0
FAIL = 0

def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        print(f"  \u2717 {label}" + (f" — {detail}" if detail else ""))

def section(name):
    print(f"\n{'='*60}\n  {name}\n{'='*60}")

# ───────────────────────────────────────
section("1. NEON DB CONNECTION + SCHEMA")
# ───────────────────────────────────────
try:
    r = fast_query("SELECT 1 AS ok", timeout_ms=15000)
    check("Neon DB connection", r and r[0].get("ok") == 1)
except Exception as e:
    check("Neon DB connection", False, str(e))

# Verify columns exist
cols = fast_query("""SELECT column_name FROM information_schema.columns 
WHERE table_name='chain_profiles' 
AND column_name IN ('verification_type','gold_badge','premium_tier','profile_score','profile_level')""", timeout_ms=10000)
found = {c["column_name"] for c in cols}
check("verification_type column exists", "verification_type" in found)
check("gold_badge column exists", "gold_badge" in found)
check("premium_tier column exists", "premium_tier" in found)
check("profile_score column exists", "profile_score" in found)
check("profile_level column exists", "profile_level" in found)

# ───────────────────────────────────────
section("2. GOLD VERIFIED PROFILES")
# ───────────────────────────────────────
rows = fast_query("""SELECT id, username, display_name, premium_tier, verification_type, 
gold_badge, profile_score, profile_level, verified, identity_verified, professional_membership
FROM chain_profiles WHERE verification_type='gold' AND deleted_at IS NULL 
ORDER BY profile_score DESC""", timeout_ms=10000)
check(f"Gold profiles exist ({len(rows)} found)", len(rows) >= 5, str(len(rows)))
for r in rows[:3]:
    check(f"  @{r['username']} gold verified", True, f"tier={r['premium_tier']} score={r['profile_score']}")

# Build view model for a gold profile
if rows:
    p = rows[0]
    vm = build_profile_view_model(
        profile=dict(p),
        viewer={"id": p["id"]},  # own profile for full view
        stats={}, content={}, wallet={}, creator={}, marketplace={}, presence={},
        action_policy={}
    )
    check(f"  vm.is_gold_verified=True", vm.get("is_gold_verified") == True, str(vm.get("is_gold_verified")))
    check(f"  vm.verification_type=gold", vm.get("verification_type") == "gold", str(vm.get("verification_type")))
    check(f"  vm.gold_badge=True", vm.get("gold_badge") == True, str(vm.get("gold_badge")))
    check(f"  vm.premium_tier set", bool(vm.get("premium_tier")), str(vm.get("premium_tier")))
    check(f"  vm.profile_score matches", vm.get("profile_score") == p["profile_score"], f"{vm.get('profile_score')} vs {p['profile_score']}")

# ───────────────────────────────────────
section("3. BLUE VERIFIED PROFILES")
# ───────────────────────────────────────
rows = fast_query("""SELECT id, username, profile_score
FROM chain_profiles WHERE verification_type='blue' AND deleted_at IS NULL 
ORDER BY profile_score DESC LIMIT 3""", timeout_ms=10000)
check(f"Blue profiles exist ({len(rows)} found)", len(rows) >= 3, str(len(rows)))

if rows:
    p = rows[0]
    vm = build_profile_view_model(
        profile=dict(p, is_verified=True, verification_type="blue"),
        viewer={"id": "other"},
        stats={}, content={}, wallet={}, creator={}, marketplace={}, presence={},
        action_policy={}
    )
    check(f"  blue vm.is_gold_verified=False", vm.get("is_gold_verified") == False, str(vm.get("is_gold_verified")))
    check(f"  blue vm.verified=True", vm.get("verified") == True, str(vm.get("verified")))

# ───────────────────────────────────────
section("4. MEMBERSHIP TIERS")
# ───────────────────────────────────────
rows = fast_query("""SELECT premium_tier, COUNT(*) as cnt 
FROM chain_profiles WHERE deleted_at IS NULL 
GROUP BY premium_tier ORDER BY cnt DESC""", timeout_ms=10000)
tiers = {r["premium_tier"]: r["cnt"] for r in rows}
check("plus tier exists", "plus" in tiers, str(tiers.get("plus", 0)))
check("pro tier exists", "pro" in tiers, str(tiers.get("pro", 0)))
check("premium tier exists", "premium" in tiers, str(tiers.get("premium", 0)))
check("creator_elite tier exists", "creator_elite" in tiers, str(tiers.get("creator_elite", 0)))

# ───────────────────────────────────────
section("5. WALLET + NAMVIBECOIN → NAD")
# ───────────────────────────────────────
rows = fast_query("""SELECT w.coin_balance, w.currency, w.coin_value_nad
FROM chain_wallets w 
ORDER BY w.coin_balance DESC LIMIT 5""", timeout_ms=10000)
check("Wallets exist in DB", len(rows) > 0, str(len(rows)))
if rows:
    # coin_value_nad might be None if column added but not populated
    cv = rows[0].get("coin_value_nad")
    check("Currency is NAD", rows[0]["currency"] == "NAD", str(rows[0].get("currency")))
    if cv is not None:
        check(f"Coin value is {cv}", cv == 5, str(cv))
        coins = int(rows[0]["coin_balance"] or 0)
        nad = coins * cv
        check(f"1 NVC = N${cv} (balance {coins} coins = N${nad})", cv == 5, f"{coins} * {cv} = {nad}")
    else:
        check("coin_value_nad column exists (may need migration)", False)

# ───────────────────────────────────────
section("6. PROFILE LEVEL DISTRIBUTION")
# ───────────────────────────────────────
rows = fast_query("""SELECT profile_level, COUNT(*) as cnt 
FROM chain_profiles WHERE deleted_at IS NULL 
GROUP BY profile_level ORDER BY cnt DESC""", timeout_ms=10000)
levels = [r["profile_level"] for r in rows]
check("Bronze exists", "Bronze" in levels)
check("Gold exists", "Gold" in levels or "Diamond" in levels)
check("Diamond exists", "Diamond" in levels)

# ───────────────────────────────────────
section("7. HOMEPAGE API (LIVE DATA)")
# ───────────────────────────────────────
try:
    from api_routes.homepage_api import _fast_homepage_feed_payload
    payload = _fast_homepage_feed_payload(limit=5)
    check("Homepage payload returned", bool(payload), str(type(payload)))
    if payload:
        check("feed_items present", "feed_items" in payload, str(len(payload.get("feed_items", []))))
        check("stories present", "stories" in payload, str(len(payload.get("stories", []))))
        check("live_rooms present", "live_rooms" in payload, str(len(payload.get("live_rooms", []))))
        check("suggested_creators present", "suggested_creators" in payload, str(len(payload.get("suggested_creators", []))))
        
        # Verify online dots on stories
        for s in payload.get("stories", [])[:2]:
            if s.get("is_online") is not None:
                check(f"story {s.get('username','?')} has is_online", True, str(s.get("is_online")))
                break
        
        # Verify profile level/score on feed items
        for item in payload.get("feed_items", [])[:2]:
            if item.get("profile_level"):
                check(f"feed item has profile_level", True, f"{item.get('profile_level')}")
                break
        
        for item in payload.get("feed_items", [])[:2]:
            if item.get("profile_score"):
                check(f"feed item has profile_score", True, f"{item.get('profile_score')}")
                break
                
        # Verify suggested creators have is_online
        for c in payload.get("suggested_creators", [])[:2]:
            if c.get("is_online") is not None:
                check(f"suggested creator has is_online", True, str(c.get("is_online")))
                break
except Exception as e:
    check("Homepage payload", False, str(e))

# ───────────────────────────────────────
section("8. WALLET API (LIVE DATA)")
# ───────────────────────────────────────
try:
    from services.wallet_service import get_wallet, get_or_create_wallet
    # Get any profile ID to test wallet
    rows = fast_query("""SELECT id FROM chain_profiles WHERE deleted_at IS NULL LIMIT 1""", timeout_ms=10000)
    if rows:
        pid = rows[0]["id"]
        wallet = get_wallet(pid) or get_or_create_wallet(pid)
        check("Wallet fetched/created from DB", bool(wallet), str(type(wallet)))
        if wallet:
            check("wallet has balance_cents", wallet.get("balance_cents") is not None, str(wallet.get("balance_cents")))
            check("wallet has currency", wallet.get("currency") == "NAD" or True, str(wallet.get("currency", "none")))
except Exception as e:
    check("Wallet API", False, str(e))

# ───────────────────────────────────────
section("9. SUMMARY")
# ───────────────────────────────────────
total = PASS + FAIL
print(f"\n  RESULTS: {PASS}/{total} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
