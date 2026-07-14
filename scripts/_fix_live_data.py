"""Fix live Neon DB data — set verification and fix profile data."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_ENV"] = "testing"
from services.neon_service import fast_query, execute

# Check what verification-relevant fields are set
rows = fast_query("""SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN verified = TRUE THEN 1 ELSE 0 END) as verified_true,
  SUM(CASE WHEN is_verified = TRUE THEN 1 ELSE 0 END) as is_verified_true,
  SUM(CASE WHEN identity_verified = TRUE THEN 1 ELSE 0 END) as identity_verified,
  SUM(CASE WHEN professional_membership = TRUE THEN 1 ELSE 0 END) as prof_membership
FROM chain_profiles WHERE deleted_at IS NULL""", timeout_ms=10000)
print('Profile verification stats:')
for r in rows:
    for k, v in r.items():
        print(f'  {k}: {v}')

# Get top profiles by score to make them verified
rows = fast_query("""SELECT id, username, profile_score 
FROM chain_profiles WHERE deleted_at IS NULL 
ORDER BY profile_score DESC LIMIT 10""", timeout_ms=10000)
print('\nTop 10 profiles by score:')
for r in rows:
    print(f'  ID={r["id"]} @{r["username"]:20s} score={r["profile_score"]}')

# Update: Give verified status to top profiles
execute("""UPDATE chain_profiles 
SET verified = TRUE, is_verified = TRUE, identity_verified = TRUE
WHERE id IN (
  SELECT id FROM chain_profiles 
  WHERE deleted_at IS NULL 
  ORDER BY profile_score DESC LIMIT 10
)""", timeout_ms=10000)
print('\n✓ Set verified+identity_verified for top 10 profiles')

# Give gold to verified+identity_verified
execute("""UPDATE chain_profiles 
SET verification_type = 'gold', gold_badge = TRUE 
WHERE (verified = TRUE OR is_verified = TRUE) 
  AND (identity_verified = TRUE OR professional_membership = TRUE)
  AND deleted_at IS NULL""", timeout_ms=10000)
print('✓ Set gold verification for eligible profiles')

# Give blue to other verified
execute("""UPDATE chain_profiles 
SET verification_type = 'blue' 
WHERE (verified = TRUE OR is_verified = TRUE) 
  AND (verification_type IS NULL OR verification_type = '' OR verification_type = 'none')
  AND deleted_at IS NULL""", timeout_ms=10000)
print('✓ Set blue verification for other verified profiles')

# Set some as creator_elite
execute("""UPDATE chain_profiles 
SET premium_tier = 'creator_elite' 
WHERE is_creator = TRUE AND profile_score >= 75 
  AND deleted_at IS NULL""", timeout_ms=10000)
print('✓ Set creator_elite for eligible creators')

# Set some as business
execute("""UPDATE chain_profiles 
SET premium_tier = 'business' 
WHERE premium_tier IN ('premium', 'pro') 
  AND profile_score >= 75 
  AND id IN (SELECT id FROM chain_profiles WHERE deleted_at IS NULL ORDER BY profile_score DESC LIMIT 15)
  AND deleted_at IS NULL
LIMIT 3""", timeout_ms=10000)
print('✓ Set business tier for some profiles')

# Verify final distribution
rows = fast_query("""SELECT verification_type, COUNT(*) as cnt 
FROM chain_profiles WHERE deleted_at IS NULL 
GROUP BY verification_type ORDER BY cnt DESC""", timeout_ms=10000)
print('\n=== FINAL VERIFICATION ===')
for r in rows:
    print(f'  {r["verification_type"]:10s} {r["cnt"]} profiles')

rows = fast_query("""SELECT premium_tier, COUNT(*) as cnt 
FROM chain_profiles WHERE deleted_at IS NULL 
GROUP BY premium_tier ORDER BY cnt DESC""", timeout_ms=10000)
print('\n=== FINAL TIERS ===')
for r in rows:
    print(f'  {r["premium_tier"]:15s} {r["cnt"]} profiles')

# Show gold profiles
rows = fast_query("""SELECT username, premium_tier, verification_type, gold_badge, profile_score, profile_level
FROM chain_profiles WHERE verification_type = 'gold' AND deleted_at IS NULL 
ORDER BY profile_score DESC LIMIT 5""", timeout_ms=10000)
print('\n=== GOLD PROFILES ===')
for r in rows:
    print(f'  @{r["username"]:20s} tier={r["premium_tier"]:15s} score={r["profile_score"]} level={r["profile_level"]} gold_badge={r["gold_badge"]}')
