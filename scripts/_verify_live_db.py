"""Verify live Neon DB data after migration."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_ENV"] = "testing"
from services.neon_service import fast_query

# 1. Verification distribution
rows = fast_query("""SELECT verification_type, COUNT(*) as cnt 
FROM chain_profiles WHERE deleted_at IS NULL 
GROUP BY verification_type ORDER BY cnt DESC""", timeout_ms=10000)
print('=== VERIFICATION ===')
for r in rows:
    print(f'  {r["verification_type"]:10s} {r["cnt"]} profiles')

# 2. Membership tiers
rows = fast_query("""SELECT premium_tier, COUNT(*) as cnt 
FROM chain_profiles WHERE deleted_at IS NULL 
GROUP BY premium_tier ORDER BY cnt DESC""", timeout_ms=10000)
print('\n=== MEMBERSHIP TIERS ===')
for r in rows:
    print(f'  {r["premium_tier"]:15s} {r["cnt"]} profiles')

# 3. Gold badge count
rows = fast_query("""SELECT gold_badge, COUNT(*) as cnt 
FROM chain_profiles WHERE deleted_at IS NULL 
GROUP BY gold_badge""", timeout_ms=10000)
print('\n=== GOLD BADGE ===')
for r in rows:
    print(f'  gold_badge={r["gold_badge"]}: {r["cnt"]} profiles')

# 4. Profile levels
rows = fast_query("""SELECT profile_level, COUNT(*) as cnt 
FROM chain_profiles WHERE deleted_at IS NULL 
GROUP BY profile_level ORDER BY cnt DESC""", timeout_ms=10000)
print('\n=== PROFILE LEVELS ===')
for r in rows:
    print(f'  {r["profile_level"]:10s} {r["cnt"]} profiles')

# 5. Wallet coin_value_nad
rows = fast_query("""SELECT coin_value_nad, COUNT(*) as cnt 
FROM chain_wallets GROUP BY coin_value_nad""", timeout_ms=10000)
print('\n=== WALLET COIN VALUE ===')
for r in rows:
    nad_val = r["coin_value_nad"]
    print(f'  1 NVC = N${nad_val}: {r["cnt"]} wallets')

# 6. Sample gold profiles with all fields
rows = fast_query("""SELECT id, username, display_name, premium_tier, 
  verification_type, gold_badge, profile_score, profile_level
FROM chain_profiles 
WHERE verification_type = 'gold' AND deleted_at IS NULL 
ORDER BY profile_score DESC LIMIT 5""", timeout_ms=10000)
print('\n=== GOLD VERIFIED PROFILES (TOP 5) ===')
for r in rows:
    print(f'  @{r["username"]:20s} tier={r["premium_tier"]:15s} score={r["profile_score"]} level={r["profile_level"]} verify={r["verification_type"]} badge={r["gold_badge"]}')

# 7. Wallet balances
rows = fast_query("""SELECT p.username, w.coin_balance, w.currency 
FROM chain_wallets w JOIN chain_profiles p ON p.id = w.profile_id::text 
WHERE w.coin_balance > 0 AND p.deleted_at IS NULL 
ORDER BY w.coin_balance DESC LIMIT 5""", timeout_ms=10000)
print('\n=== TOP WALLETS ===')
for r in rows:
    bal = r["coin_balance"] or 0
    print(f'  @{r["username"]:20s} balance={bal} {r["currency"]}')
