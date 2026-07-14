-- Phase: Gold Verification + Membership Tiers + NamVibeCoin
-- Adds columns for gold verification and membership upgrade

-- 1. Add verification_type (gold / blue / none)
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS verification_type TEXT DEFAULT 'none';

-- 2. Add gold_badge flag
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS gold_badge BOOLEAN DEFAULT FALSE;

-- 3. Ensure chain_wallets has currency and coin conversion fields
ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'NAD';
ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS coin_value_nad INTEGER DEFAULT 5;

-- 4. Mark verified+identity_verified profiles as gold
UPDATE chain_profiles 
SET verification_type = 'gold', gold_badge = TRUE 
WHERE (verified = TRUE OR is_verified = TRUE) 
  AND (identity_verified = TRUE OR professional_membership = TRUE)
  AND (verification_type IS NULL OR verification_type = 'none');

-- 5. Mark other verified as blue
UPDATE chain_profiles 
SET verification_type = 'blue' 
WHERE (verified = TRUE OR is_verified = TRUE) 
  AND (verification_type IS NULL OR verification_type = 'none');

-- 6. Upgrade some existing profiles to membership tiers based on score
UPDATE chain_profiles 
SET premium_tier = 'premium' 
WHERE profile_score >= 80 AND profile_score IS NOT NULL 
  AND (premium_tier IS NULL OR premium_tier = 'free');

UPDATE chain_profiles 
SET premium_tier = 'pro' 
WHERE profile_score >= 60 AND profile_score < 80 AND profile_score IS NOT NULL 
  AND (premium_tier IS NULL OR premium_tier = 'free');

UPDATE chain_profiles 
SET premium_tier = 'plus' 
WHERE profile_score >= 40 AND profile_score < 60 AND profile_score IS NOT NULL 
  AND (premium_tier IS NULL OR premium_tier = 'free');

UPDATE chain_profiles 
SET premium_tier = 'creator_elite' 
WHERE is_creator = TRUE AND profile_score >= 85 
  AND (premium_tier IS NULL OR premium_tier = 'free');

-- 7. Ensure all remaining free profiles have premium_tier set
UPDATE chain_profiles 
SET premium_tier = 'free' 
WHERE premium_tier IS NULL;

-- 8. Ensure all profiles have profile_level set
UPDATE chain_profiles 
SET profile_level = 
  CASE 
    WHEN profile_score >= 90 THEN 'Diamond'
    WHEN profile_score >= 80 THEN 'Gold'
    WHEN profile_score >= 70 THEN 'Silver'
    WHEN profile_score >= 50 THEN 'Bronze'
    ELSE 'Bronze'
  END
WHERE profile_level IS NULL OR profile_level = '';

-- 9. Verify wallet has coin balances for active profiles
UPDATE chain_wallets 
SET currency = 'NAD', coin_value_nad = 5 
WHERE currency IS NULL OR currency = '';
